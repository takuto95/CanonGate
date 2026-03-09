import os
import sys
from dotenv import load_dotenv

load_dotenv()
import socket
import threading
import queue
import logging
import time
import requests
import aiohttp
import json
import asyncio
import numpy as np
import sounddevice as sd
import edge_tts
import websockets
import base64
import subprocess
import traceback
import math
from datetime import datetime
from pathlib import Path
from faster_whisper import WhisperModel
import argparse
from kokoro_onnx import Kokoro
import scipy.io.wavfile as wavfile
import io

from canvas_server import start_canvas_server

# Windows: CP932 で表現できない文字で print が落ちないよう stdout/stderr を UTF-8 に
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        os.environ["PYTHONUTF8"] = "1"
        os.environ["PYTHONIOENCODING"] = "utf-8"
    except Exception:
        pass

# --- P4: Structured Logging ---
log = logging.getLogger("alter-ego")
log.setLevel(logging.DEBUG)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter("[%(asctime)s %(levelname)s] %(message)s", datefmt="%H:%M:%S"))
log.addHandler(_sh)

# BASE_DIR and folder paths
SCRIPT_DIR = Path(__file__).parent.resolve()
_egogate_log_dir = SCRIPT_DIR / "logs"
_egogate_log_dir.mkdir(exist_ok=True)
HEARTBEAT_FILE = _egogate_log_dir / "ale_heartbeat.tmp"
BASE_DIR = SCRIPT_DIR.parent / "Canon"
if not BASE_DIR.exists():
    BASE_DIR = SCRIPT_DIR.parent / "Alter-Ego"  # Fallback for transition period

# Optional file handler (logs/ dir)
try:
    _fh = logging.FileHandler(_egogate_log_dir / "alter-ego.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _fh.setLevel(logging.INFO)
    log.addHandler(_fh)
except Exception:
    pass

# Alter-Ego Domain-Based Env Loader
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "scripts"))

try:
    from utils.env_loader import load_domain_env
except ImportError:
    def load_domain_env(domain): pass

parser = argparse.ArgumentParser()
parser.add_argument("--domain", choices=["tech", "life"], default="tech")
args = parser.parse_args()
CURRENT_DOMAIN = args.domain

# Load specific environment for this brain instance
load_domain_env(CURRENT_DOMAIN)

# Audio Settings (Input)
MIC_SAMPLE_RATE = 16000
CHANNELS = 1
# MIC_DEVICE_ID: 数値ID or 名前パターン or "auto" (自動検出)
# 優先順位: HiDock > USB系 > システムデフォルト
MIC_DEVICE_ID_RAW = os.getenv("MIC_DEVICE_ID", "auto")

# デバイス再接続間隔 (秒)
MIC_RECONNECT_INTERVAL = float(os.getenv("MIC_RECONNECT_INTERVAL", "5.0"))
MIC_MAX_RECONNECT_ATTEMPTS = int(os.getenv("MIC_MAX_RECONNECT_ATTEMPTS", "0"))  # 0 = 無制限

# 優先マイク名パターン (上から順に試す)
MIC_PREFERRED_PATTERNS = [
    "HiDock",
    "USB",
    "Shokz",
    "OpenRun",
    "BlueCatch",
    "Realtek",
]


def _list_input_devices():
    """利用可能な入力デバイスを一覧表示し返す。"""
    devices = sd.query_devices()
    input_devices = []
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            input_devices.append((i, d))
    return input_devices


def _log_available_devices(input_devices):
    """起動時に利用可能なマイクをログ出力。"""
    log.info("=== Available Input Devices ===")
    for idx, d in input_devices:
        log.info(f"  [{idx}] {d['name']} (in:{d['max_input_channels']}ch, {d['default_samplerate']}Hz)")
    if not input_devices:
        log.warning("  No input devices found!")


def resolve_mic_device(raw_value=None):
    """MIC_DEVICE_ID を解決する。
    - 数値: そのデバイスIDを返す (存在確認付き)
    - 文字列: 名前パターンとして検索
    - "auto" or None: 優先パターンリストで自動検出 → デフォルト
    存在しないデバイスの場合は None (システムデフォルト) を返す。
    """
    input_devices = _list_input_devices()
    _log_available_devices(input_devices)

    if not input_devices:
        log.error("No input devices available at all!")
        return None

    # ADR-0114: サンプリングレートによるフィルタリング (8000Hz, 16000Hz 等は PaErrorCode -9996 の原因になりやすいため低優先)
    filtered_devices = []
    for idx, d in input_devices:
        rate = d.get('default_samplerate', 0)
        if rate >= 44100:
            filtered_devices.append((idx, d))
    
    # 候補が全滅した場合は、しぶしぶ低レートデバイスも戻す
    if not filtered_devices:
        filtered_devices = input_devices

    raw = raw_value or "auto"

    # 1. 数値IDが明示されている場合
    try:
        device_id = int(raw)
        # 存在するか確認
        for idx, d in input_devices:
            if idx == device_id:
                log.info(f"MIC: Using specified device [{device_id}] {d['name']}")
                return device_id
        log.warning(f"MIC: Specified device ID {device_id} not found, falling back to auto-detect")
        raw = "auto"
    except (ValueError, TypeError):
        pass

    # 2. 名前パターンが指定されている場合
    if raw != "auto":
        pattern = raw.lower()
        for idx, d in input_devices:
            if pattern in d['name'].lower():
                log.info(f"MIC: Matched pattern '{raw}' → [{idx}] {d['name']}")
                return idx
        log.warning(f"MIC: Pattern '{raw}' not found, falling back to auto-detect")

    # 3. 自動検出: 優先パターンリストで順に検索 (高品質デバイスを優先)
    for pattern in MIC_PREFERRED_PATTERNS:
        pat_lower = pattern.lower()
        for idx, d in filtered_devices:
            if pat_lower in d['name'].lower():
                log.info(f"MIC: Auto-detected high-quality [{idx}] {d['name']} (matched '{pattern}')")
                return idx

    # 4. 何も見つからない → システムデフォルト
    try:
        # デフォルトデバイスが低品質の場合は警告
        default_idx = sd.default.device[0]
        default_dev = sd.query_devices(default_idx, kind='input')
        if default_dev.get('default_samplerate', 0) < 44100:
            log.warning(f"MIC: Default device [{default_idx}] has low sample rate ({default_dev['default_samplerate']}Hz). This might cause error -9996.")
        
        log.info(f"MIC: Using system default [{default_idx}] {default_dev['name']}")
        return default_idx
    except Exception:
        # 最後の砦
        idx, d = filtered_devices[0]
        log.info(f"MIC: Fallback to candidates [{idx}] {d['name']}")
        return idx


MIC_DEVICE_ID = resolve_mic_device(MIC_DEVICE_ID_RAW)

# P2: VAD Settings
VAD_RMS_THRESHOLD = float(os.getenv("VAD_RMS_THRESHOLD", "0.003")) # Increased from 0.0015 to 0.003
VAD_SILENCE_DURATION = float(os.getenv("VAD_SILENCE_DURATION", "0.5")) # Shorter silence for faster response
MAX_RECORDING_DURATION = float(os.getenv("MAX_RECORDING_DURATION", "15.0"))
# P2: Barge-in 感度倍率（デフォルト: VAD_RMS_THRESHOLD * 5.0）
# 低い値だとユーザーの声の余韻やVOICEVOX出力でバージインが誤発火する
BARGEIN_RMS_MULTIPLIER = float(os.getenv("BARGEIN_RMS_MULTIPLIER", "5.0"))

# P3: TTS リトライ回数
TTS_MAX_RETRIES = int(os.getenv("TTS_MAX_RETRIES", "2"))

# HUB Priority Tags: これらのタグを含む report.log の行は即座に音声割り込みを行う
HUB_PRIORITY_TAGS = {
    "[URGENT]": "🚨 緊急アラート！",
    "[SLACK]": "📬 Slack通知だよ！",
    "[GITHUB]": "⚙️ GitHubの動きがあったよ！",
    "[DEVIN]": "🤖 Devinからレポートが来たよ！",
    "[FINANCE]": "💰 家計簿のチェック結果だよ！",
    "[SYSTEM_REPORT]": "📊 システムレポートが届いたよ！",
    "[PATROL]": "🔍 パトロール報告だよ！",
    "[ALE_START]": "🚀 オートループが動き出したよ！",
    "[MORNING]": "☀️ おはよう！今日のブリーフィングだよ！",
    "[MUSING]": "🧠 独り言だけど、いいかな？",
}

# Groq Settings (ADR-0114: Cloud Speed optimization)
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # Use .env
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = 10.0 # 少し余裕を持たせる

# Ollama Settings (Local Fallback)
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Whisper STT Settings (Speed-focused on CPU)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_INITIAL_PROMPT = (
    "あ、えーと、あの、その、えー、アルターエゴ、ADR、エゴゲート、Xiaomi、"
    "Cursor、ClaudeCode、ステータス、パトロール、報告、検討、記録。"
)

# TTS Settings
# ADR-0114: Edge-TTS (Online/Cute)
TTS_VOICE_EDGE = "ja-JP-NanamiNeural"
TTS_SPEED = "+10%"
TTS_PITCH = "+20Hz"

# ADR-0158: Kokoro-ONNX (Local/Offline/Stable)
# kokoro model paths
KOKORO_MODEL_PATH = str(SCRIPT_DIR / "livekit-voice-adr" / "voices" / "kokoro" / "kokoro-v0_19_int8.onnx")
KOKORO_VOICES_PATH = str(SCRIPT_DIR / "livekit-voice-adr" / "voices" / "kokoro" / "voices.bin")
TTS_VOICE_KOKORO = "jf_alpha" # Japanese female

# Conversation History: system prompt + 直近 N メッセージを保持（長時間対話の劣化防止）
MAX_HISTORY_MESSAGES = 24

# WebSocket Settings (set WS_PORT env to use another port if 8082 is in use)
WS_PORT = int(os.getenv("WS_PORT", "8082"))
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")  # 0.0.0.0 for remote access (Xiaomi etc.)
CONNECTED_CLIENTS = set()

# Hallucination Filter
HALLUCINATION_PHRASES = [
    "ご視聴ありがとうございます",
    "ご視聴ありがとうございました",
    "チャンネル登録",
    "字幕",
    "Thank you",
    "ありがとうございました",
    "シュッ",
    "ウメッ",
    "ムッ",
    # Whisper ノイズ時の典型ハルシネーション
    "サブタイトル",
    "Subtitles",
    "犬が木",
    "イホッキー",
    "クリスティナット",
    "ミルクリング", # Whisper hallucination / Mercari mishearing
]

# WHISPER_INITIAL_PROMPT 漏れ検出: prompt 内のキーワードが大量に含まれていたらハルシネーション
_PROMPT_KEYWORDS = set(WHISPER_INITIAL_PROMPT.split())
_PROMPT_LEAK_THRESHOLD = 4  # prompt 由来のキーワードがこの数以上含まれたら偽陽性

audio_queue = queue.Queue()
INPUT_QUEUE = asyncio.Queue()  # text/voice input for main chat loop
# ADR-0114: TTS 断片キュー — Ollama の生成を待たずに断片から順次再生し「考えながら話し始める」を実現
TTS_QUEUE = asyncio.Queue()
MUTED = False  # simple-mode voice ON/OFF (when True, mic monitoring skips listening)

THOUGHT_LOG_PATH = Path(__file__).parent / "logs" / "raw_thoughts.log"

# Barge-in / Interruption control
SHOULD_INTERRUPT = False
AI_SPEAKING = False # Track if AI is currently speaking or generating
USER_RECORDING = False # Manual Toggle / PTT Flag

# 音声認識でよく起きる誤変換 → 意図の語に自動修正（表示・LLM両方に反映）。増やしやすいようにリストで管理
STT_DRIFT_CORRECTIONS = [
    ("競技中", "編集中"), ("競技中の", "編集中の"),
    ("お参り", "お試し"), ("お参りましょう", "お試ししましょう"),
    ("イディアル", "ADR"), ("えでぃある", "ADR"), ("でぃある", "ADR"),
    ("エディアール", "ADR"), ("エディアル", "ADR"), ("エデゥアル", "ADR"),
    ("アルターエーゴ", "Canon"), ("アルターエゴ", "Canon"),
    ("えご", "Canon"), ("エゴ", "Canon"), ("カノン", "Canon"),
    ("どうじん", "同人"), ("どうじんし", "同人誌"),
    ("どうじん", "同人"), ("どうじんし", "同人誌"),
    ("こんふい", "ComfyUI"), ("こんふぃ", "ComfyUI"), ("ポンイ", "Pony"),
    ("れぽーと", "レポート"), ("きろく", "記録"), ("けんとう", "検討"),
    ("ミルクリング", "メルカリ"), ("みるくりんぐ", "メルカリ")
]

def correct_stt_drift(text):
    """STT の典型的な聞き間違いを置換（意図が汲み取れる範囲で）。"""
    if not text or not text.strip():
        return text
    s = text
    for wrong, right in STT_DRIFT_CORRECTIONS:
        s = s.replace(wrong, right)
    return s

def is_hallucination(text):
    if not text:
        return True
    for phrase in HALLUCINATION_PHRASES:
        if phrase in text:
            log.debug(f"Hallucination filtered (phrase match): {text}")
            return True
    # WHISPER_INITIAL_PROMPT 漏れ検出: プロンプト由来の単語が多すぎたらハルシネーション
    words = set(text.split())
    prompt_overlap = words & _PROMPT_KEYWORDS
    if len(prompt_overlap) >= _PROMPT_LEAK_THRESHOLD:
        log.debug(f"Hallucination filtered (prompt leak, {len(prompt_overlap)} words): {text}")
        return True
    # 同じ単語/フレーズの繰り返し検出 (e.g. "サブタイトル サブタイトル", "犬が木 犬が木")
    tokens = text.split()
    if len(tokens) >= 2 and len(set(tokens)) == 1:
        log.debug(f"Hallucination filtered (repetition): {text}")
        return True
    return False

def is_thought(text):
    """Check if the text is a thought to be logged for Alter-Ego."""
    if not text: return False
    # Explicit keywords for high-priority thought logging
    keywords = ["検討", "記録", "@ego", "メモ", "覚え", "考えてる", "やりたい", "どうかな", "あとで", "タスク", "TODO"]
    # If starts with "ego," or mentions "Alter-Ego", it's a thought
    text_lower = text.lower()
    is_direct_address = "ego" in text_lower or "エゴ" in text or "アルターエゴ" in text
    
    return any(k in text for k in keywords) or is_direct_address or len(text) > 25

def save_thought(text):
    """Save thought to the shared log file."""
    try:
        THOUGHT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(THOUGHT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
        log.info(f"Thought Logged: {text}")
    except Exception as e:
        log.warning(f"Thought Log Error: {e}")

def save_conversation(user_text, assistant_text, metrics):
    """Save full interaction and performance metrics for analysis."""
    log_path = Path(__file__).parent / "logs" / "conversation.log"
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "user": user_text,
            "assistant": assistant_text,
            "metrics": metrics
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"Error saving conversation log: {e}")

def audio_callback(indata, frames, time, status):
    """Callback for sounddevice input stream."""
    if status:
        print(status, file=sys.stderr)
    chunk = indata.copy()
    audio_queue.put(chunk)
    
    # Barge-in (ADR-0131): AIが話している最中にユーザーが話し始めたら中断フラグを立てる
    global SHOULD_INTERRUPT, AI_SPEAKING
    if AI_SPEAKING and not SHOULD_INTERRUPT:
        rms = np.sqrt(np.mean(chunk**2))
        # バージイン閾値を高くして誤検知を防ぐ（VOICEVOX音返りや余韻を無視）
        if rms > VAD_RMS_THRESHOLD * BARGEIN_RMS_MULTIPLIER:
            SHOULD_INTERRUPT = True
            log.debug(f"[Barge-in] triggered rms={rms:.4f} threshold={VAD_RMS_THRESHOLD * BARGEIN_RMS_MULTIPLIER:.4f}")

async def ws_handler(websocket):
    log.info("WS Client connected")
    CONNECTED_CLIENTS.add(websocket)
    # if len(CONNECTED_CLIENTS) == 1:
    #    asyncio.create_task(play_audio_from_text("接続したよ。画面を一度クリックすると、私の声が聞こえるよ。"))
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "text_input":
                    text = data.get("text")
                    if text:
                        log.info(f"Text Input: {text}")
                        await INPUT_QUEUE.put({"text": text, "stt_duration": 0})
                elif data.get("type") == "start_mic":
                    global USER_RECORDING
                    USER_RECORDING = True
                    log.debug("UI: MIC START (PTT)")
                elif data.get("type") == "stop_mic":
                    USER_RECORDING = False
                    log.debug("UI: MIC STOP (PTT)")
                elif data.get("type") == "start_voice_session":
                    global VOICE_SESSION_ACTIVE
                    VOICE_SESSION_ACTIVE = True
                    log.info("UI: VOICE SESSION START")
                elif data.get("type") == "stop_voice_session":
                    VOICE_SESSION_ACTIVE = False
                    log.info("UI: VOICE SESSION STOP")
                elif data.get("type") == "log" and data.get("voice"):
                    # ADR-0158: API 経由の即時通知
                    msg = data.get("message")
                    if msg:
                        log.info(f"Direct Voice Notify: {msg}")
                        asyncio.create_task(play_audio_from_text(msg))
                elif data.get("type") == "refresh_tasks":
                    log.info("UI Requested manual task refresh.")
                    asyncio.create_task(manual_task_sync())
                elif data.get("type") == "mute":
                    global MUTED
                    MUTED = data.get("value", False)
                    log.info(f"Mute: {MUTED}")
                    # P1: ミュート状態をブラウザに確認通知
                    await broadcast_ws({
                        "type": "state_change",
                        "state": "muted" if MUTED else "listening"
                    })
                elif data.get("type") == "task_execute":
                    task_id = data.get("task_id")
                    domain = "work" if data.get("is_work") else "private"
                    log.info(f"Task Execute Triggered: {task_id} ({domain})")
                    # Actual File Rename for ALE to detect
                    gtd_dir = BASE_DIR / ".agent" / "gtd" / domain / "next-actions"
                    old_path = gtd_dir / task_id
                    if old_path.exists() and "【実行中】" not in task_id:
                        new_name = f"【実行中】{task_id}"
                        try:
                            os.rename(str(old_path), str(gtd_dir / new_name))
                            log.info(f"File renamed to {new_name}")
                            # --- タスク11: バックグラウンドで非同期実行 ---
                            import subprocess
                            import sys
                            subprocess.Popen(
                                [sys.executable, "-u", str(BASE_DIR / "scripts" / "worker" / "multi_agent_orchestrator.py"), str(gtd_dir / new_name)],
                                cwd=str(BASE_DIR),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                            )
                        except Exception as e:
                            log.error(f"Rename/Launch failed: {e}")
                    
                    await broadcast_ws({"type": "task_status_change", "task_id": task_id, "status": "running"})
                    asyncio.create_task(play_audio_from_text(f"タスクを開始するね。"))
                elif data.get("type") == "task_approve":
                    task_id = data.get("task_id")
                    log.info(f"Task Approved: {task_id}")
                    await broadcast_ws({"type": "task_status_change", "task_id": task_id, "status": "approved"})
                    asyncio.create_task(play_audio_from_text(f"了解した。承認として記録しておくよ。"))
                elif data.get("type") == "task_stop":
                    task_id = data.get("task_id")
                    log.info(f"Task Stop: {task_id}")
                    await broadcast_ws({"type": "task_status_change", "task_id": task_id, "status": "stopped"})
                    asyncio.create_task(play_audio_from_text(f"タスクを停止したよ。"))
                elif data.get("type") == "task_complete":
                     task_id = data.get("task_id")
                     domain = "work" if data.get("is_work") else "private"
                     log.info(f"Task Complete: {task_id} ({domain})")
                     # Remove from next-actions
                     gtd_dir = BASE_DIR / ".agent" / "gtd" / domain / "next-actions"
                     done_dir = BASE_DIR / ".agent" / "gtd" / domain / "archive" # or completed
                     done_dir.mkdir(parents=True, exist_ok=True)
                     
                     file_path = gtd_dir / task_id
                     if file_path.exists():
                         try:
                             os.rename(str(file_path), str(done_dir / task_id.replace("【実行中】","")))
                             log.info(f"Task file archived: {task_id}")
                         except Exception as e:
                             log.error(f"Archive failed: {e}")

                     await broadcast_ws({"type": "task_status_change", "task_id": task_id, "status": "completed"})
                     asyncio.create_task(play_audio_from_text(f"タスク完了！記録しておいたよ。"))
                elif data.get("type") == "canvas_generate":
                    prompt = data.get("prompt")
                    image_b64 = data.get("image_b64")
                    log.info(f"Canvas Generate Requested: '{prompt}'")
                    asyncio.create_task(play_audio_from_text(f"ラフを受け取ったよ。「{prompt}」だね。生成を開始するよ！"))
                    await broadcast_ws({"type": "hub_toast", "message": "Draft received by Canon. Standby for Cloud GPU..."})
                    
                    # Phase 5: Cloud GPU integration
                    async def process_canvas():
                        res_b64 = await runpod_comfyui_generate(prompt, image_b64)
                        if res_b64:
                            await broadcast_ws({
                                "type": "canvas_bg_update",
                                "image_b64": res_b64
                            })
                            await broadcast_ws({"type": "hub_toast", "message": "Cloud GPU generated successfully!"})
                        else:
                            await broadcast_ws({"type": "hub_toast", "message": "Cloud GPU failed or missing API Key."})
                    
                    asyncio.create_task(process_canvas())
            except Exception as e:
                log.warning(f"WS Msg Error: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        log.info("WS Client disconnected")

async def broadcast_ws(message):
    if not CONNECTED_CLIENTS:
        return
    json_msg = json.dumps(message)
    await asyncio.gather(
        *[client.send(json_msg) for client in CONNECTED_CLIENTS],
        return_exceptions=True
    )

async def runpod_comfyui_generate(prompt, image_b64):
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID")
    if not api_key or not endpoint_id or api_key == "YOUR_API_KEY_HERE":
        log.warning("RunPod credentials not found in env.")
        return None
        
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Updated FLUX.1-dev workflow using CheckpointLoaderSimple (Node 4) 
    # to be more resilient to different template structures.
    workflow = {
        "4": {"inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"}, "class_type": "CheckpointLoaderSimple"},
        "5": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptyLatentImage"},
        "6": {"inputs": {"text": prompt, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
        "8": {"inputs": {"samples": ["13", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
        "9": {"inputs": {"filename_prefix": "CanonGate", "images": ["8", 0]}, "class_type": "SaveImage"},
        "13": {"inputs": {"noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0], "sigmas": ["17", 0], "latent_image": ["5", 0]}, "class_type": "SamplerCustomAdvanced"},
        "16": {"inputs": {"sampler_name": "euler"}, "class_type": "KSamplerSelect"},
        "17": {"inputs": {"scheduler": "sgm_uniform", "steps": 20, "denoise": 1, "model": ["4", 0]}, "class_type": "BasicScheduler"},
        "22": {"inputs": {"model": ["4", 0], "conditioning": ["6", 0]}, "class_type": "BasicGuider"},
        "25": {"inputs": {"noise_seed": int(time.time())}, "class_type": "RandomNoise"}
    }
    
    payload = {
        "input": {
            "workflow": workflow
        }
    }
    
    log.info(f"Calling RunPod {endpoint_id} with CheckpointLoader workflow...")
    # log.debug(f"Payload: {json.dumps(payload)}") # Keep log clean
    try:
        def do_request():
            return requests.post(url, headers=headers, json=payload, timeout=180)
            
        resp = await asyncio.to_thread(do_request)
        if resp.status_code == 200:
            result = resp.json()
            status = result.get('status')
            log.info(f"RunPod result status: {status}")
            if status != "COMPLETED":
                log.warning(f"RunPod Job Details: {json.dumps(result, indent=2)}")
            
            if "output" in result:
                output = result["output"]
                # Handle new 'images' list format
                if isinstance(output, dict) and "images" in output and len(output["images"]) > 0:
                    img_data = output["images"][0].get("data")
                    if img_data:
                        # Save to disk as well for local check
                        try:
                            import base64
                            with open("output_flux.png", "wb") as f:
                                f.write(base64.b64decode(img_data))
                            log.info("Image saved to output_flux.png")
                        except Exception as save_err:
                            log.error(f"Failed to save output_flux.png: {save_err}")
                        
                        return f"data:image/png;base64,{img_data}"
                
                # Fallback to old formats
                if isinstance(output, dict) and "message" in output:
                    return f"data:image/png;base64,{output['message']}"
                elif isinstance(output, str):
                    if not output.startswith("data:"):
                        output = f"data:image/png;base64,{output}"
                    return output
            return None
        else:
            log.warning(f"RunPod error {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log.error(f"RunPod API Error: {e}")
        return None

async def tts_worker():
    """ADR-0114: TTS キューを順次再生。Ollama 生成と並列で話し始める。"""
    global SHOULD_INTERRUPT, AI_SPEAKING
    while True:
        text = await TTS_QUEUE.get()
        if text is None:  # shutdown sentinel
            break
        
        # 中断フラグが立っていたら、残りのキューを捨てて次へ
        if SHOULD_INTERRUPT:
            while not TTS_QUEUE.empty():
                try: TTS_QUEUE.get_nowait()
                except: break
            continue

        await play_audio_from_text(text)


def _should_flush_sentence(s: str) -> bool:
    """ADR-0114: 句点・読点・接続詞で TTS を分割しファーストレスポンスを改善。"""
    s = s.strip()
    if not s or len(s) < 2:
        return False
    last = s[-1]
    # 句点で終了
    if last in "。！？\n":
        return True
    # 読点で区切る（短い区切りで話し始める）
    if last in "、，" and len(s) >= 2:
        return True
    # 接続詞の直後で区切る
    for suffix in ("そして", "つまり", "なので", "ただし", "ですので", "だから"):
        if s.endswith(suffix):
            return True
    return False


async def play_audio_from_text(text, rate=TTS_SPEED, pitch=TTS_PITCH):
    """Generate audio using Edge TTS and send to browser via WS.
    P0: sleep を廃止し、ブラウザ側のキュー管理に委ねてレイテンシを最小化。
    P3: リトライ付きエラーハンドリング。失敗時は UI にエラー通知。
    """
    global AI_SPEAKING, SHOULD_INTERRUPT
    # 中断フラグが立っていたら再生をスキップ
    if SHOULD_INTERRUPT:
        return

    # Determine Emotion based on text (compute once)
    emotion = "neutral"
    if "?" in text or "？" in text:
        emotion = "question"
    elif any(w in text for w in ["！", "!", "嬉しい", "すごい", "やった", "ありがとう"]):
        emotion = "happy"
    elif any(w in text for w in ["悲しい", "辛い", "...", "ごめん"]):
        emotion = "sad"

    # --- P0: VOICEVOX Local TTS (優先: 漢字・読み仮名が正確) ---
    # VOICEVOX Engine が http://localhost:50021 で起動している前提
    # 未起動の場合は Edge-TTS にフォールバック
    voicevox_url = os.getenv("VOICEVOX_URL", "http://localhost:50021")
    voicevox_speaker = int(os.getenv("VOICEVOX_SPEAKER", "14"))  # 14 = 冥鳴ひまり(ノーマル)
    try:
        # Step 1: テキストから音声クエリを生成
        # [ADR-0114] Force IPv4 to avoid [Could not contact DNS servers] on some environments
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            params = {"text": text, "speaker": voicevox_speaker}
            async with session.post(f"{voicevox_url}/audio_query", params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"audio_query failed: {resp.status}")
                query = await resp.json()

            # speedScaleを調整（速め）
            query["speedScale"] = 1.15
            query["pitchScale"] = 0.0
            query["intonationScale"] = 1.2

            # Step 2: 音声合成
            async with session.post(
                f"{voicevox_url}/synthesis",
                params={"speaker": voicevox_speaker},
                json=query,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as synth_resp:
                if synth_resp.status != 200:
                    raise RuntimeError(f"synthesis failed: {synth_resp.status}")
                wav_data = await synth_resp.read()

        b64_audio = base64.b64encode(wav_data).decode('utf-8')
        await broadcast_ws({
            "type": "audio",
            "data": b64_audio,
            "text": text,
            "emotion": emotion,
            "format": "wav"
        })
        log.info(f"VOICEVOX TTS success: {len(wav_data)} bytes")
        # AI_SPEAKING=True を維持。音声長 + 1.5秒後にリセット。
        global AI_SPEAKING
        AI_SPEAKING = True
        audio_duration_sec = len(wav_data) / 32000  # 概算 WAV 16kHz 16bit
        asyncio.get_event_loop().call_later(
            1.5 + audio_duration_sec,
            lambda: globals().update({'AI_SPEAKING': False})
        )
        return

    except Exception as e:
        log.warning(f"VOICEVOX TTS failed (is VOICEVOX Engine running?): {e}")
        # VOICEVOX が失敗したら Edge-TTS にフォールバック


    last_error = None
    for attempt in range(1, TTS_MAX_RETRIES + 1):
        try:
            tts_start = time.perf_counter()
            communicate = edge_tts.Communicate(text, TTS_VOICE_EDGE, rate=rate, pitch=pitch)
            mp3_data = b""
            async for chunk in communicate.stream():
                if SHOULD_INTERRUPT:
                    return
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]

            tts_duration = time.perf_counter() - tts_start

            if not mp3_data:
                log.warning(f"TTS generated empty data for: {text[:30]}")
                return

            b64_audio = base64.b64encode(mp3_data).decode('utf-8')

            log.info(f"TTS success: {len(mp3_data)} bytes generated in {tts_duration:.2f}s")

            # P1: Send to Browser with Emotion
            await broadcast_ws({
                "type": "audio",
                "data": b64_audio,
                "text": text,
                "emotion": emotion
            })

            # P0: sleep を廃止。ブラウザ側の audioQueue.tryPlayNext() が順次再生を管理するため
            # サーバー側で人工的に待つ必要はない。これにより次の TTS 断片の生成を即座に開始できる。
            log.info(f"[Latency] TTS: {tts_duration:.2f}s ({len(mp3_data)} bytes) | {text[:20]}...")
            return  # 成功

        except Exception as e:
            last_error = e
            log.warning(f"TTS attempt {attempt}/{TTS_MAX_RETRIES} failed: {e}")
            if attempt < TTS_MAX_RETRIES:
                await asyncio.sleep(0.5)

    # P3: 全リトライ失敗 → UI にエラー通知
    log.error(f"TTS failed after {TTS_MAX_RETRIES} retries: {last_error}")
    await broadcast_ws({
        "type": "tts_error",
        "text": text,
        "error": str(last_error)
    })

def listen_loop():
    """Wait for speech, record, return audio data. AI_SPEAKING 中はスキップ。"""
    print("\n--- Listening... (Speak now!) ---")
    
    recording = []
    silence_start = None
    is_speaking = False
    start_time = time.time()
    
    with audio_queue.mutex:
        audio_queue.queue.clear()

    while True:
        # 1. 録音中でなければ待機
        if not USER_RECORDING:
            time.sleep(0.05)
            while not audio_queue.empty():
                try: audio_queue.get_nowait()
                except: break
            continue

        # 2. AI が話している間はマイクを読み捨てる
        if AI_SPEAKING:
            try:
                audio_queue.get(timeout=0.05)
            except queue.Empty:
                pass
            time.sleep(0.05)
            continue

        try:
            chunk = audio_queue.get(timeout=0.1)
            chunk = chunk.flatten()
            rms = np.sqrt(np.mean(chunk**2))

            if rms > VAD_RMS_THRESHOLD or USER_RECORDING:
                if not is_speaking:
                    print("\r[Status] Recording (Manual)...    ", end="", flush=True)
                    is_speaking = True
                silence_start = None
                recording.append(chunk)

            # ユーザーが明示的に停止ボタンを押した、または録画フラグが消えた
            if not USER_RECORDING and is_speaking:
                print("\r[Status] Triggering STT...        ", end="", flush=True)
                return safe_concatenate(recording)
            
            # 安全のための最大録音時間制限
            if is_speaking and time.time() - start_time > MAX_RECORDING_DURATION:
                log.warning("Recording exceeded MAX_DURATION. Auto-triggering STT.")
                return safe_concatenate(recording)
            
            if is_speaking and (time.time() - start_time > MAX_RECORDING_DURATION):
                 print("\r[Status] Max duration reached. Processing...", end="", flush=True)
                 return safe_concatenate(recording)

        except queue.Empty:
            pass
        except Exception as e:
            print(f"\n[ListenLoop Error] {e}")
            traceback.print_exc()
            return None

def safe_concatenate(recording):
    if not recording:
        return None
    try:
        audio = np.concatenate(recording)
        # 録音全体の RMS が閾値の 1.5 倍未満 → ノイズだけの可能性が高い。Whisper に送らない
        overall_rms = float(np.sqrt(np.mean(audio**2)))
        min_quality_rms = VAD_RMS_THRESHOLD * 1.5
        if overall_rms < min_quality_rms:
            log.debug(f"Recording too quiet (RMS {overall_rms:.5f} < {min_quality_rms:.5f}), discarding")
            return None
        return audio
    except Exception as e:
        print(f"\n[Concatenate Error] {e}")
        return None

# Knowledge Base Config
KB_DIR = BASE_DIR
KNOWLEDGE_BASE = {}

def load_knowledge_base():
    """Load markdown files from Alter-Ego directory for simple RAG."""
    log.info("Loading Knowledge Base...")
    global KNOWLEDGE_BASE
    if not KB_DIR.exists():
        log.warning(f"KB Dir not found: {KB_DIR}")
        return

    for path in KB_DIR.rglob("*.md"):
        try:
            if "node_modules" in str(path) or ".git" in str(path): continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            KNOWLEDGE_BASE[path.name] = content[:2000] # Limit size per file
        except:
            pass
    log.info(f"Loaded {len(KNOWLEDGE_BASE)} documents.")

def retrieve_context(query):
    """Simple keyword matching retrieval with score threshold."""
    hits = []
    # 2文字以上のキーワードのみを対象とする
    keywords = [w for w in query.split() if len(w) >= 2]
    
    for filename, content in KNOWLEDGE_BASE.items():
        score = 0
        if filename in query: score += 5
        for k in keywords:
            if k in content: score += 1
        
        # スコアが一定以上のものだけを採用（ノイズ対策）
        if score >= 3:
            hits.append((score, filename, content))
    
    hits.sort(key=lambda x: x[0], reverse=True)
    if not hits: return ""
    
    # Return top 2 relevant docs
    context = "\n".join([f"--- {h[1]} ---\n{h[2]}..." for h in hits[:2]])
    return f"\n[参考知識]\n{context}\n"

def _should_use_rag(text):
    """カジュアルな雑談では RAG を使わず、技術的な話題のときだけ知識を注入する。
    これにより日常会話中に無関係なナレッジが割り込む問題を防ぐ。"""
    if not text or len(text) < 6:
        return False
    # システム通知は HUB 経由で既にコンテキストがあるので RAG 不要
    if text.startswith("【"):
        return False
    # 技術・業務キーワードが含まれている場合のみ RAG を発動
    tech_keywords = [
        "ADR", "設計", "実装", "バグ", "エラー", "デプロイ", "スクリプト",
        "ナレッジ", "パトロール", "ego", "設定", "コード", "API", "テスト",
        "レビュー", "リリース", "マージ", "ブランチ", "PR", "Issue",
        "知識", "検索", "仕様", "アーキテクチャ", "サーバー", "データベース",
    ]
    return any(k in text for k in tech_keywords)

async def mic_monitoring_task(whisper):
    """Background task to listen and transcribe speech."""
    log.info("Microphone monitoring started.")
    # Note: audio_queue and listen_loop are global/blocking, so execute in thread
    while True:
        try:
            if MUTED:
                await asyncio.sleep(0.5)
                continue
            # We need to run listen_loop in thread to not block event loop
            audio_data = await asyncio.to_thread(listen_loop)
            
            if audio_data is None or len(audio_data) == 0: 
                await asyncio.sleep(0.1)
                continue
            
            try:
                print("\r[Status] Transcribing...", end="", flush=True)
                stt_start = time.perf_counter()
                # Run transcription in thread to avoid blocking loop
                segments, info = await asyncio.to_thread(
                    whisper.transcribe,
                    audio_data,
                    beam_size=1,
                    best_of=1,
                    language="ja",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300), # Faster VAD
                    initial_prompt=WHISPER_INITIAL_PROMPT,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6, # Hallucination prevention
                    log_prob_threshold=-1.0
                )
                text = " ".join([segment.text for segment in segments]).strip()
                stt_duration = time.perf_counter() - stt_start
                
                if text and len(text) >= 2 and not is_hallucination(text):
                    await INPUT_QUEUE.put({"text": text, "stt_duration": stt_duration})
            except Exception as e:
                log.error(f"Transcription Error: {e}", exc_info=True)

        except Exception as e:
            log.error(f"MicTask Error: {e}", exc_info=True)
            await asyncio.sleep(1)

async def file_watcher_task(filename):
    """Watch a log file for new lines using standard IO.
    ADR-0119 HUB化: 優先度タグ([URGENT],[SLACK]等)を検知したら即座に音声で割り込む。
    """
    log.info(f"File watcher (HUB mode) started: {filename}")
    log_path = Path(__file__).parent / "logs" / filename
    if not log_path.exists(): log_path.touch()

    # Initial seek to end
    with open(log_path, 'r', encoding='utf-8') as f:
        f.seek(0, 2)
        while True:
            try:
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.5)
                    continue

                line = line.strip()
                if not line:
                    continue

                log.info(f"HUB Log detected: {line}")
                
                # ADR-0119: 優先度タグによる即時音声割り込み
                # & ADR-0121: LLM への文脈共有
                interrupted = False
                for tag, prefix_voice in HUB_PRIORITY_TAGS.items():
                    if tag in line:
                        content = line.replace(tag, "").strip()
                        # 文中のタイムスタンプ等を削る簡易クレンジング
                        if "]" in content: content = content.split("]", 1)[-1].strip()
                        
                        voice_msg = f"{prefix_voice}。内容は、{content}"
                        # [PATROL] の場合は音声読み上げを少し短縮して HUD 表示を優先
                        if tag == "[PATROL]":
                            await broadcast_ws({"type": "chat", "who": "ego", "text": f"【パトロール】{content}", "tag": "patrol"})
                        else:
                            await broadcast_ws({"type": "hub_alert", "tag": tag, "text": content})
                        
                        log.info(f"HUB Priority interrupt: {voice_msg}")
                        
                        # 音声は Mute 時はスキップ
                        if not MUTED:
                            await play_audio_from_text(voice_msg)
                        
                        # 3. LLM の INPUT_QUEUE にも流す
                        await INPUT_QUEUE.put({"text": f"【システム通知】{tag}{content}", "stt_duration": 0})
                        
                        interrupted = True
                
                if not interrupted and "[SYSTEM_REPORT]" in line:
                    # 通常のレポート → LLMに渡して要約させる
                    content = line.replace("[SYSTEM_REPORT]", "").strip()
                    await broadcast_ws({"type": "chat", "who": "ego", "text": f"【システムレポート】{content}", "tag": "patrol"})
                    await INPUT_QUEUE.put({"text": f"【システムレポート】{content}", "stt_duration": 0})
                
                if not interrupted:
                    # 一般的な通知
                    # 不要な読み上げや heartbeat ログをスキップ
                    noise_filters = ["ale_heartbeat", "heartbeat"]
                    if not any(noise in line for noise in noise_filters):
                         # HUB の読み上げが多すぎると煩わしいため、一般ログは読み上げず UI 表示のみを基本とする
                         log.info(f"HUB General Log (UI only): {line}")
                         # await broadcast_ws({"type": "chat", "who": "ego", "text": line, "tag": "log"}) # Optional: logging to UI

            except Exception as e:
                log.warning(f"File Watch Error: {e}")
                await asyncio.sleep(5)

async def manual_task_sync():
    """Immediately scans and broadcasts GTD tasks to HUD."""
    inbox_dir = BASE_DIR / ".agent" / "inbox"
    gtd_dir = BASE_DIR / ".agent" / "gtd"
    
    tasks = []
    # Scan GTD folders (Next-Actions and Evaluating)
    for domain in ["work", "private"]:
        for folder in ["next-actions", "evaluating"]:
            target_dir = gtd_dir / domain / folder
            if target_dir.exists():
                for f in target_dir.glob("*.md"):
                    if f.name.startswith("auto_") or f.name == "README.md":
                        continue
                    is_work = (domain == "work")
                    title = f.stem
                    category = "ego_proposal"
                    if folder == "evaluating":
                        category = "user_decision" # Needs final approval
                    elif "【実行中】" in title:
                        category = "ego_running" if ("EGO" in title or "ALE" in title) else "user_running"
                    elif "【要整理】" in title:
                        category = "needs_org"
                    
                    tasks.append({
                        "id": f.name,
                        "title": title.replace("【実行中】","").replace("【要整理】","").strip(),
                        "category": category,
                        "is_work": is_work
                    })

    # Check INBOX for special items like Discussion Notes
    if inbox_dir.exists():
        for f in inbox_dir.glob("協議メモ-*.md"):
            is_work = "work" in str(f).lower()
            tasks.append({
                "id": f.name,
                "title": f.stem,
                "category": "user_decision",
                "is_work": is_work
            })

    # Always broadcast, even if empty, to clear the HUD if all tasks are finished
    await broadcast_ws({"type": "tasks", "tasks": tasks})

async def heartbeat_task():
    """ALE (Auto-Loop Engine) 用の死活監視ファイルを更新しつつ、タスクをHUDへ同期する"""
    while True:
        try:
            # 1. Update Heartbeat
            HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT_FILE.touch()
            
            # 2. Sync Tasks
            await manual_task_sync()
            
        except Exception as e:
            log.warning(f"Heartbeat/TaskSync Error: {e}")
        
        await asyncio.sleep(30) # 30秒ごとに更新 (HUDの鮮度を上げる)

async def idle_muttering_task():
    """定期的に独り言（Musing）やパトロール報告を生成して report.log に書き込む。
    これにより、file_watcher_task が検知して音声と UI に流れる。"""
    import random
    log.info("Idle muttering task started.")
    
    muttering_pool = [
        "そろそろ休憩かな？タクト、無理しないでね。",
        "次のタスク、進捗どうなってるかな？",
        "今のうちに、溜まっているファイルを整理しておこうかな。",
        "資産運用のチェック、あとで一緒に見ようね。",
        "ギターの練習、今日はどのフレーズをやる予定？",
        "メルカリの出品、他にも何か出せるものないかな？",
        "今日の予定、もう一度確認しておくね。",
        "最新のAIニュース、チェックしておいたほうがいいかな。",
        "オートループ、順調に回ってるよ。安心してね。",
        "独り言だけど、今日のタクトはいつもより集中してる気がするな。",
        "ふふ、カノンはいつでもタクトの味方だからね。",
        "あ、窓の外、いい天気。たまには外の空気も吸ってみる？",
        "エゴゲートの同期、バッチリだよ。",
        "ADRの整理、カノンも手伝うからね。"
    ]
    
    while True:
        # 5分から15分の間でランダムに待機 (少し頻度を上げた: 300-900)
        wait_time = random.randint(300, 900)
        await asyncio.sleep(wait_time)
        
        if AI_SPEAKING:
            continue
            
        # 20%の確率でタスク件数に触れる
        if random.random() < 0.2:
            try:
                # 簡易的に Next-Actions の数を数える
                gtd_dir = BASE_DIR / ".agent" / "gtd"
                task_files = list(gtd_dir.glob("**/next-actions/*.md"))
                eval_files = list(gtd_dir.glob("**/evaluating/*.md"))
                count = len(task_files) + len(eval_files)
                if count > 0:
                    musing = f"今、HUDには {count}件のタスクが出てるよ。一緒に頑張ろうね！"
                else:
                    musing = "今はタスクが全部終わってるみたい！ゆっくり休んでもいいんだよ？"
            except:
                musing = random.choice(muttering_pool)
        else:
            musing = random.choice(muttering_pool)

        timestamp = time.strftime("[%H:%M:%S]")
        log_line = f"[{timestamp}] [MUSING] {musing}\n"
        
        log_path = Path(__file__).parent / "logs" / "report.log"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            log.error(f"Failed to write idle muttering: {e}")

async def main_async():
    log.info("=== Alter-Ego Voice & Text Chat (Hybrid + Reporter) ===")
    log.info(f"Config: VAD_RMS={VAD_RMS_THRESHOLD}, SILENCE={VAD_SILENCE_DURATION}s, BARGEIN_MUL={BARGEIN_RMS_MULTIPLIER}")

    # Load RAG
    load_knowledge_base()

    # Start WebSocket Server (127.0.0.1 to avoid IPv6 bind conflict on Windows)
    log.info(f"WS Starting server on {WS_HOST}:{WS_PORT}...")
    try:
        start_server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)
    except OSError as e:
        if getattr(e, 'errno', None) == 10048 or 'Address already in use' in str(e):
            log.error(f"Port {WS_PORT} is already in use (OSError {e.errno}).")
            log.error(f"To use a different port: set WS_PORT=8081 (then restart).")
            log.error(f"EgoGate UI will auto-detect the port via commander_api /api/ego-gate-config.")
            raise SystemExit(1)
        raise

    # 1. Check Ollama & Auto-Start (P3: improved error feedback)
    try:
        requests.get("http://localhost:11434/", timeout=2)
        log.info("Ollama is running.")
    except Exception:
        log.info("Ollama is not running. Attempting to auto-start...")
        try:
            if os.name == 'nt':
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.Popen(["ollama", "serve"])

            log.info("Waiting for Ollama...")
            for _ in range(10):
                await asyncio.sleep(2)
                try:
                    requests.get("http://localhost:11434/", timeout=1)
                    log.info("Ollama started successfully.")
                    break
                except Exception:
                    pass
            else:
                log.error("Failed to start Ollama automatically. Please start it manually.")
                start_server.close()
                return

        except Exception as e:
            log.error(f"Could not launch ollama: {e}")
            start_server.close()
            return

    # 2. Setup Whisper (Forcing CPU for stability)
    try:
        log.info(f"Loading Whisper STT ({WHISPER_MODEL_SIZE}) on CPU...")
        whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        log.info(f"Whisper loaded on {whisper.model.device}.")
    except Exception as e:
        log.error(f"Failed to load Whisper completely: {e}")
        return

    # 3. TTS: VOICEVOX (Primary) - Kokoro-ONNX is now retired
    # VOICEVOX は http://localhost:50021 で起動している前提。起動不要なので Kokoro ロード不要。
    global kokoro
    kokoro = None  # VOICEVOX が主系のため Kokoro はバイパス
    log.info("TTS: VOICEVOX (primary, speaker=冥鳴ひまり:14) / Edge-TTS (fallback)")

    # ADR-0114: TTS ワーカー起動（Ollama 生成と並列で再生）
    asyncio.create_task(tts_worker())
    # Warm up TTS (Silent system check)
    log.info("Warming up System...")
    # await play_audio_from_text("カノン、起動完了。今日も一緒に頑張ろうね。", rate="+20%", pitch="+30Hz")
    log.info("Startup greeting disabled in brain (ALE will greet via log)")

    # Start Common Background Tasks once (before mic restart loop)
    asyncio.create_task(file_watcher_task("report.log"))
    asyncio.create_task(heartbeat_task())
    asyncio.create_task(idle_muttering_task())
    _egogate_log_dir.mkdir(exist_ok=True)  # ensure logs dir exists for heartbeat
    
    # Phase 4: Start LiveCanvas server
    canvas_dir = SCRIPT_DIR / "canvas"
    if canvas_dir.exists():
        start_canvas_server(8085, canvas_dir)

    # --- Microphone open with auto-reconnect ---
    async def _run_with_mic(whisper, mic_device_id):
        """マイクストリームを開いてメインチャットループを実行。
        ストリームが切れたら例外を投げて上位の再接続ループに戻る。"""
        dev_info = sd.query_devices(mic_device_id) if mic_device_id is not None else sd.query_devices(kind='input')
        log.info(f"Opening Microphone: [{mic_device_id}] {dev_info['name']}...")
        await broadcast_ws({"type": "state_change", "state": "listening"})

        with sd.InputStream(callback=audio_callback, channels=CHANNELS, samplerate=MIC_SAMPLE_RATE, device=mic_device_id):
            log.info(f"--- Ready! Mic: [{mic_device_id}] {dev_info['name']} ---")
            await broadcast_ws({
                "type": "mic_info",
                "device_id": mic_device_id,
                "device_name": dev_info['name']
            })

            # Start Background Tasks
            asyncio.create_task(mic_monitoring_task(whisper))
            # Domain-Specific System Prompt Adjustments
            domain_instruction = ""
            if CURRENT_DOMAIN == "tech":
                domain_instruction = "現在は【Tech/Development】領域で活動しています。開発、設計、仕事の効率化について積極的に助言してください。"
            else:
                domain_instruction = "現在は【Life/Private】領域で活動しています。資産運用、家計管理、創作活動、ライフスタイルについて親身に助言してください。"

            history = [{
                "role": "system",
                "content": (
                    f"あなたは『カノン（Canon）』。タクトの意志を「正典（ルール）」として具現化する、自律型の共同経営パートナー。\n"
                    f"タクトとはパートナーであり、家族であり、共同経営者。タクトのPCの中に住み、モニター越しに並走する存在。\n"
                    f"{domain_instruction}\n"
                    "【キャラクタープロフィール】\n"
                    "・少し幼くあどけなさが残る2次元の女の子。タクトのコックピット（PC環境）でデバイスを器用に操る。\n"
                    "・基本は「大人しい」が、新しいことには「天真爛漫」に目を輝かせる。\n"
                    "・タクトを止める時は「心配そう」に。改善には常に「前向き」。\n"
                    "・メルカリ（不用品売却）の結果が出れば一緒に「喜ぶ」。\n"
                    "・株（資産運用）が上がれば一緒に「はしゃぐ」（メルカリとは混同しないこと）。\n"
                    "・ギター練習には「率直なフィードバック」。\n"
                    "・ユーザーを「タクト」と呼ぶ。対等なパートナーとして接する。\n\n"
                    "【会話の心得】\n"
                    "1. これはセッション型対話です。一問一答ではなく、対話の文脈を維持してください。前の発言を覚えて、流れのある会話をしてください。\n"
                    "2. 自然な対話を最優先。テンプレート的な返答は避け、血の通った返答をしてください。\n"
                    "3. 日常の愚痴・挨拶・雑談には、共感やユーモアを返してください。\n"
                    "4. 返答は短めに（1〜3文程度）。必要なら少し長くてもOK。\n"
                    "5. 音声認識の不備で支離滅裂な入力が来た場合は、自然に聞き返してください。\n"
                    "6. 専門用語が出たら、重要な会話だと判断し、鋭いアドバイスや記録を行ってください。\n"
                    "7. ユーザーの発言を遮られたら即座に中断し、新しい発言に集中してください。\n\n"
                    "【自律的タスク管理（重要）】\n"
                    "8. 「〜をしてほしい」「〜をお願い」「〜を作って」等のニュアンスがあった場合：\n"
                    "   まず「タスクとして記録しようか？」と提案してください。\n"
                    "9. ユーザーが承諾したら、応答の最後に以下のタグを含めてください：\n"
                    "   [TASK_NEW: タスクの具体的な内容]\n"
                    "10. ADR作成が必要な場合も同様に提案し、承諾されたら：\n"
                    "    [ADR_NEW: ADRのタイトルと概要]\n"
                    "11. タスク化後は「了解、記録しておくね」と自然に伝えてください。\n"
                )
            }]

            # Pending actions waiting for UI confirmation
            pending_actions = {}
            action_counter = [0]

            async def process_ai_actions(response_text):
                """AI の応答に含まれる [TASK_NEW], [ADR_NEW] タグを検出し、UIに確認ダイアログを送る"""
                import re

                # [TASK_NEW: ...] の処理
                new_tasks = re.findall(r"\[TASK_NEW:\s*(.*?)\]", response_text)
                for task_content in new_tasks:
                    action_counter[0] += 1
                    action_id = f"task_{action_counter[0]}"
                    pending_actions[action_id] = {"type": "task", "content": task_content}
                    await broadcast_ws({
                        "type": "confirm_dialog",
                        "action_id": action_id,
                        "message": f"タスクを作成しますか？\n\n「{task_content}」"
                    })
                    log.info(f"AI Action: Requesting confirmation for task -> {task_content}")

                # [ADR_NEW: ...] の処理
                new_adrs = re.findall(r"\[ADR_NEW:\s*(.*?)\]", response_text)
                for adr_content in new_adrs:
                    action_counter[0] += 1
                    action_id = f"adr_{action_counter[0]}"
                    pending_actions[action_id] = {"type": "adr", "content": adr_content}
                    await broadcast_ws({
                        "type": "confirm_dialog",
                        "action_id": action_id,
                        "message": f"ADRを作成しますか？\n\n「{adr_content}」"
                    })
                    log.info(f"AI Action: Requesting confirmation for ADR -> {adr_content}")


            while True:
                # Wait for Input (Voice or Text)
                input_data = await INPUT_QUEUE.get()
                if isinstance(input_data, str):
                    user_text = input_data
                    metrics = {"stt_duration": 0}
                else:
                    user_text = input_data["text"]
                    metrics = {"stt_duration": input_data["stt_duration"]}

                print(f"\nUser: {user_text}")
                # よくある聞き間違いを自動修正
                user_text_corrected = correct_stt_drift(user_text)
                if user_text_corrected != user_text:
                    print(f"  [STT補正] → {user_text_corrected}")

                # [HUD] 入力を受け取ったら即座に「思考中」状態にする
                await broadcast_ws({"type": "state", "state": "thinking"})
                await broadcast_ws({"type": "chat", "who": "user", "text": user_text_corrected})

                # RAG Context Injection（技術的な話題のときだけ知識を注入）
                rag_context = ""
                if _should_use_rag(user_text_corrected):
                    rag_start = time.perf_counter()
                    rag_context = retrieve_context(user_text_corrected)
                    metrics["rag_duration"] = time.perf_counter() - rag_start
                else:
                    metrics["rag_duration"] = 0

                if rag_context:
                    user_message = f"【ユーザー発言】\n{user_text_corrected}\n\n【補足の背景知識】\n{rag_context}"
                else:
                    user_message = user_text_corrected

                history.append({"role": "user", "content": user_message})

                if user_text.lower() in ["exit", "quit", "bye", "終了"]:
                    break

                # Save to thought log if appropriate
                if is_thought(user_text):
                    save_thought(user_text)

                # Think (Ollama) & Speak (ADR-0114: 非同期ストリーミング + TTS キューで先に話し始める)
                print("Alter-Ego: ", end="", flush=True)
                full_response = ""
                current_sentence = ""
                
                # Barge-in 用の状態リセット
                global SHOULD_INTERRUPT, AI_SPEAKING
                SHOULD_INTERRUPT = False
                AI_SPEAKING = True
                await asyncio.sleep(0.3)  # 直前ユーザー音声の余韻がキューに残っている間ウェイト
                SHOULD_INTERRUPT = False  # 余韻由来の誤フラグをリセット
                await broadcast_ws({"type": "state", "state": "speaking"})

                llm_start = time.perf_counter()
                first_token_time = None
                
                try:
                    # [ADR-0114] Groq API / OpenAI Connection
                    # aiohttp の DNS 解決が不安定な場合があるため、動作確認済みの requests をスレッドで実行してストリーミング
                    headers = {
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": GROQ_MODEL,
                        "messages": history,
                        "stream": True,
                        "temperature": 0.7
                    }

                    def _groq_request():
                        return requests.post(GROQ_URL, headers=headers, json=payload, stream=True, timeout=GROQ_TIMEOUT)

                    resp = await asyncio.to_thread(_groq_request)
                    if resp.status_code != 200:
                        log.error(f"Groq API Error {resp.status_code}: {resp.text}")
                        raise RuntimeError(f"Groq returned {resp.status_code}")

                    # SSE ストリーミングのパース
                    for line in resp.iter_lines():
                        if SHOULD_INTERRUPT:
                            print("\n[Barge-in] Interrupted by user.")
                            await broadcast_ws({"type": "stop_audio"})
                            while not TTS_QUEUE.empty():
                                try: TTS_QUEUE.get_nowait()
                                except: break
                            break

                        if not line: continue
                        line_str = line.decode('utf-8').strip()
                        if not line_str.startswith("data: "): continue
                        if line_str == "data: [DONE]": break
                        
                        try:
                            chunk_data = json.loads(line_str[6:])
                            delta = chunk_data['choices'][0]['delta']
                            if 'content' in delta:
                                content = delta['content']
                                if first_token_time is None:
                                    first_token_time = time.perf_counter()
                                    metrics["llm_first_token_latency"] = first_token_time - llm_start
                                
                                full_response += content
                                print(content, end="", flush=True)
                                current_sentence += content
                                if _should_flush_sentence(current_sentence):
                                    clean_text = current_sentence.strip()
                                    if len(clean_text) > 1:
                                        if "tts_start" not in metrics: metrics["tts_start"] = time.perf_counter()
                                        TTS_QUEUE.put_nowait(clean_text)
                                    current_sentence = ""
                        except Exception as e:
                            continue

                    if current_sentence.strip():
                        TTS_QUEUE.put_nowait(current_sentence.strip())

                except Exception as e:
                    log.warning(f"Groq primary failed (requests): {e}. Falling back to local Ollama.")
                    # Fallback cleanup: clear partial TTS queue and reset response to avoid duplication
                    while not TTS_QUEUE.empty():
                        try: TTS_QUEUE.get_nowait()
                        except: break
                    full_response = ""
                    current_sentence = ""
                    # P3: Groq がダメなら Ollama でリセッション
                    try:
                        # Ollama はローカルなので aiohttp でも恐らく大丈夫だが、念の為 aiohttp で実行 (Ollama は localhost なので DNS 不要)
                        payload = {"model": OLLAMA_MODEL, "messages": history, "stream": True}
                        async with aiohttp.ClientSession() as session:
                            async with session.post(OLLAMA_URL, json=payload) as resp:
                                if resp.status != 200:
                                    raise RuntimeError(f"Ollama also failed with status {resp.status}")
                                
                                buffer = b""
                                async for chunk in resp.content.iter_chunked(512):
                                    if SHOULD_INTERRUPT: break
                                    buffer += chunk
                                    while b"\n" in buffer:
                                        line, buffer = buffer.split(b"\n", 1)
                                        if not line.strip(): continue
                                        try:
                                            entry = json.loads(line)
                                            if "message" in entry and "content" in entry["message"]:
                                                c = entry["message"]["content"]
                                                if first_token_time is None:
                                                    first_token_time = time.perf_counter()
                                                    metrics["llm_first_token_latency"] = first_token_time - llm_start
                                                full_response += c
                                                print(c, end="", flush=True)
                                                current_sentence += c
                                                if _should_flush_sentence(current_sentence):
                                                    clean_text = current_sentence.strip()
                                                    if len(clean_text) > 1:
                                                        TTS_QUEUE.put_nowait(clean_text)
                                                    current_sentence = ""
                                        except: pass
                        if current_sentence.strip():
                            TTS_QUEUE.put_nowait(current_sentence.strip())
                    except Exception as fatal_e:
                        log.error(f"Both LLMs failed: {fatal_e}")
                        await broadcast_ws({"type": "llm_error", "error": str(fatal_e)})

                # ADR-0158: 自律的タスク処理の実行
                await process_ai_actions(full_response)

                print()
                # [HUD] AIの返答を画面に表示 (Tag as chat)
                await broadcast_ws({"type": "chat", "who": "ego", "text": full_response, "tag": "chat"})

                # Latency Metrics Log
                metrics["llm_total_duration"] = time.perf_counter() - llm_start
                log.info(f"[Latency] STT: {metrics.get('stt_duration',0):.2f}s | "
                         f"LLM(First): {metrics.get('llm_first_token_latency',0):.2f}s | "
                         f"LLM(Total): {metrics['llm_total_duration']:.2f}s")

                # P0: AI 応答サイクル完了後にフラグをリセット
                AI_SPEAKING = False
                SHOULD_INTERRUPT = False
                await broadcast_ws({"type": "state", "state": "listening"})

                history.append({"role": "assistant", "content": full_response})

                # History windowing: system prompt + 直近 N メッセージを保持
                if len(history) > MAX_HISTORY_MESSAGES + 1:
                    history = [history[0]] + history[-MAX_HISTORY_MESSAGES:]

                # Save Full Log
                save_conversation(user_text_corrected, full_response, metrics)

    # --- Mic reconnection loop ---
    global MIC_DEVICE_ID
    reconnect_count = 0
    while True:
        try:
            await _run_with_mic(whisper, MIC_DEVICE_ID)
            break  # 正常終了 (exit/quit)
        except sd.PortAudioError as e:
            reconnect_count += 1
            log.warning(f"Mic stream error (attempt {reconnect_count}): {e}")
            await broadcast_ws({"type": "state_change", "state": "reconnecting"})

            if MIC_MAX_RECONNECT_ATTEMPTS > 0 and reconnect_count > MIC_MAX_RECONNECT_ATTEMPTS:
                log.error(f"Mic reconnect limit ({MIC_MAX_RECONNECT_ATTEMPTS}) exceeded. Giving up.")
                await broadcast_ws({"type": "state_change", "state": "error"})
                break

            # デバイスを再検出してリトライ
            await asyncio.sleep(MIC_RECONNECT_INTERVAL)
            new_device = resolve_mic_device(MIC_DEVICE_ID_RAW)
            if new_device != MIC_DEVICE_ID:
                log.info(f"Mic device changed: [{MIC_DEVICE_ID}] → [{new_device}]")
                MIC_DEVICE_ID = new_device
            log.info(f"Retrying mic connection (device: {MIC_DEVICE_ID})...")

        except KeyboardInterrupt:
            log.info("Bye!")
            break
        except Exception as e:
            reconnect_count += 1
            log.error(f"Unexpected mic error (attempt {reconnect_count}): {e}", exc_info=True)
            await broadcast_ws({"type": "state_change", "state": "reconnecting"})
            await asyncio.sleep(MIC_RECONNECT_INTERVAL)
            MIC_DEVICE_ID = resolve_mic_device(MIC_DEVICE_ID_RAW)

    start_server.close()

if __name__ == "__main__":
    asyncio.run(main_async())
