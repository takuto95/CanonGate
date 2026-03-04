import os
import sys
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

# Alter-Ego Domain-Based Env Loader
# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent / "Alter-Ego"))
from scripts.utils.env_loader import load_domain_env

parser = argparse.ArgumentParser()
parser.add_argument("--domain", choices=["tech", "life"], default="tech")
args = parser.parse_args()
CURRENT_DOMAIN = args.domain

# Load specific environment for this brain instance
load_domain_env(CURRENT_DOMAIN)

# Windows: CP932 で表現できない文字（例: 一部CJK）で print が落ちないよう stdout/stderr を UTF-8 に
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        # ADR-0114: Windows で aiohttp/edge-tts が DNS エラーを吐く問題の修正
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# --- P4: Structured Logging ---
log = logging.getLogger("alter-ego")
log.setLevel(logging.DEBUG)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter("[%(asctime)s %(levelname)s] %(message)s", datefmt="%H:%M:%S"))
log.addHandler(_sh)
# Optional file handler (logs/ dir)
try:
    _log_dir = Path(__file__).parent / "logs"
    _log_dir.mkdir(exist_ok=True)
    _fh = logging.FileHandler(_log_dir / "alter-ego.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _fh.setLevel(logging.INFO)
    log.addHandler(_fh)
except Exception:
    pass

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent.resolve()

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

# P2: VAD Settings — 環境変数で調整可能 (ADR-0120 デフォルト値を維持)
VAD_RMS_THRESHOLD = float(os.getenv("VAD_RMS_THRESHOLD", "0.002"))
VAD_SILENCE_DURATION = float(os.getenv("VAD_SILENCE_DURATION", "0.8"))
MAX_RECORDING_DURATION = float(os.getenv("MAX_RECORDING_DURATION", "15.0"))
# P2: Barge-in 感度倍率 (デフォルト: VAD_RMS_THRESHOLD * 2.0)
BARGEIN_RMS_MULTIPLIER = float(os.getenv("BARGEIN_RMS_MULTIPLIER", "2.0"))

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
    "[MUSING]": "🧠 独り言だけど、いいかな？",
}

# Ollama Settings
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Whisper STT Settings (ADR-0114: large-v3-turbo=爆速高精度)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
WHISPER_INITIAL_PROMPT = (
    "イディアル ADR 編集中 エディアル ステージング 承認 メール 検証 設定 チェック 出せる 確認 "
    "アルターエゴ レポート パトロール 記録 検討 メモ 覚えて 聞こえない 認識 音声 "
    "HiDock P1 BlueCatch OpenRun Shokz ハイドック ブルーキャッチ ショックス "
    "スクラム プルリク DataBee プルリクエスト マージ リリース デプロイ"
)

# TTS Settings (Microsoft Edge Voice — Cute Voice)
TTS_VOICE = "ja-JP-NanamiNeural"
TTS_SPEED = "+10%"
TTS_PITCH = "+20Hz"

# Conversation History: system prompt + 直近 N メッセージを保持（長時間対話の劣化防止）
MAX_HISTORY_MESSAGES = 24

# WebSocket Settings (set WS_PORT env to use another port if 8080 is in use)
WS_PORT = int(os.getenv("WS_PORT", "8080"))
WS_HOST = "127.0.0.1"  # IPv4 only to avoid WinError 10048 on Windows
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

# 音声認識でよく起きる誤変換 → 意図の語に自動修正（表示・LLM両方に反映）。増やしやすいようにリストで管理
STT_DRIFT_CORRECTIONS = [
    ("競技中", "編集中"), ("競技中の", "編集中の"),
    ("お参り", "お試し"), ("お参りましょう", "お試ししましょう"),
    ("イディアル", "ADR"), ("えでぃある", "ADR"), ("でぃある", "ADR"),
    ("エディアール", "ADR"), ("エディアル", "ADR"), ("エデゥアル", "ADR"),
    ("アルターエーゴ", "Alter-Ego"), ("アルターエゴ", "Alter-Ego"),
    ("えご", "ego"), ("エゴ", "ego"),
    ("どうじん", "同人"), ("どうじんし", "同人誌"),
    ("こんふい", "ComfyUI"), ("こんふぃ", "ComfyUI"), ("ポンイ", "Pony"),
    ("れぽーと", "レポート"), ("きろく", "記録"), ("けんとう", "検討")
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
        # P2: Barge-in 閾値を環境変数で調整可能
        if rms > VAD_RMS_THRESHOLD * BARGEIN_RMS_MULTIPLIER:
            SHOULD_INTERRUPT = True

async def ws_handler(websocket):
    log.info("WS Client connected")
    CONNECTED_CLIENTS.add(websocket)
    # 初回接続時だけ歓迎音声を送る（起動時のウォームアップは窓より先に流れるため届かない対策）
    if len(CONNECTED_CLIENTS) == 1:
        asyncio.create_task(play_audio_from_text("接続したよ。画面を一度クリックすると、私の声が聞こえるよ。"))
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "text_input":
                    text = data.get("text")
                    if text:
                        log.info(f"Text Input: {text}")
                        await INPUT_QUEUE.put(text)
                elif data.get("type") == "mute":
                    global MUTED
                    MUTED = data.get("value", False)
                    log.info(f"Mute: {MUTED}")
                    # P1: ミュート状態をブラウザに確認通知
                    await broadcast_ws({
                        "type": "state_change",
                        "state": "muted" if MUTED else "listening"
                    })
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

    last_error = None
    for attempt in range(1, TTS_MAX_RETRIES + 1):
        try:
            tts_start = time.perf_counter()
            communicate = edge_tts.Communicate(text, TTS_VOICE, rate=rate, pitch=pitch)
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
            log.debug(f"TTS OK ({tts_duration:.2f}s, {len(mp3_data)}B): {text[:30]}...")
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
    """Wait for speech, record, return audio data."""
    print("\n--- Listening... (Speak now!) ---")
    
    recording = []
    silence_start = None
    is_speaking = False
    start_time = time.time()
    
    with audio_queue.mutex:
        audio_queue.queue.clear()

    while True:
        try:
            chunk = audio_queue.get(timeout=0.1)
            chunk = chunk.flatten()
            rms = np.sqrt(np.mean(chunk**2))

            if rms > VAD_RMS_THRESHOLD:
                if not is_speaking:
                    print("\r[Status] Speaking detected...   ", end="", flush=True)
                    is_speaking = True
                silence_start = None
                recording.append(chunk)

            elif is_speaking:
                recording.append(chunk)
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > VAD_SILENCE_DURATION:
                    print("\r[Status] Processing...         ", end="", flush=True)
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
KB_DIR = Path(__file__).parent.parent / "Alter-Ego"
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
                    vad_parameters=dict(min_silence_duration_ms=500),
                    initial_prompt=WHISPER_INITIAL_PROMPT,
                    condition_on_previous_text=False
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
                    await asyncio.sleep(0.5)  # ADR-0120: 1s → 0.5s で検知速度向上
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
                        log.info(f"HUB Priority interrupt: {voice_msg}")
                        
                        # 1. 通知は Mute でも必ず UI へ（トースト + INTERACTION LOG はフロントで追記）
                        await broadcast_ws({"type": "hub_alert", "tag": tag, "text": content})
                        # 2. 音声は Mute 時はスキップ（ALE 等は「見える通知」だけにする）
                        if not MUTED:
                            await play_audio_from_text(voice_msg)
                        
                        # 3. LLM の INPUT_QUEUE にも流し、次の会話で文脈を保持させる
                        await INPUT_QUEUE.put({"text": f"【システム通知】{tag}{content}", "stt_duration": 0})
                        
                        interrupted = True
                        break

                if not interrupted and "[SYSTEM_REPORT]" in line:
                    # 通常のレポート → LLMに渡して要約させる
                    content = line.replace("[SYSTEM_REPORT]", "").strip()
                    await INPUT_QUEUE.put({"text": f"【パトロール報告】{content}", "stt_duration": 0})

            except Exception as e:
                log.warning(f"File Watch Error: {e}")
                await asyncio.sleep(5)

async def main_async():
    log.info("=== Alter-Ego Voice & Text Chat (Hybrid + Reporter) ===")
    log.info(f"Config: VAD_RMS={VAD_RMS_THRESHOLD}, SILENCE={VAD_SILENCE_DURATION}s, BARGEIN_MUL={BARGEIN_RMS_MULTIPLIER}")

    # Load RAG
    load_knowledge_base()

    # Start WebSocket Server (127.0.0.1 to avoid IPv6 bind conflict on Windows)
    log.info(f"WS Starting server on {WS_HOST}:{WS_PORT}...")
    start_server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)

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

    # 2. Setup Whisper (ADR-0114: GPU 利用可能なら auto/cuda で高速化)
    # P0: User report "no sound" and logs show CUDA library errors. Forcing CPU for stability.
    try:
        log.info(f"Loading Whisper STT ({WHISPER_MODEL_SIZE})...")
        # デフォルトで CPU を試す (ユーザー環境での CUDA エラー回避)
        whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        log.info("Whisper loaded (CPU).")
    except Exception as e:
        log.error(f"Failed to load Whisper: {e}")
        return

    # ADR-0114: TTS ワーカー起動（Ollama 生成と並列で再生）
    asyncio.create_task(tts_worker())
    # Warm up TTS
    log.info("Warming up System...")
    await play_audio_from_text("システム起動。巡回レポートの監視を開始します。", rate="+20%", pitch="+30Hz")

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
            asyncio.create_task(file_watcher_task("report.log"))
            # Domain-Specific System Prompt Adjustments
            domain_instruction = ""
            if CURRENT_DOMAIN == "tech":
                domain_instruction = "現在は【Tech/Development】領域で活動しています。開発、設計、仕事の効率化について積極的に助言してください。家計やプライベートな話は控えめにします。"
            else:
                domain_instruction = "現在は【Life/Private】領域で活動しています。資産運用、家計管理、創作活動、ライフスタイルについて親身に（かつ戦友として厳しく）助言してください。仕事のコードの話は最低限にします。"

            history = [{
                "role": "system",
                "content": (
                    f"あなたは『Alter-Ego』。ユーザーの『相棒』かつ『軍師』であり、現在は戦友（Comrade）として振舞います。\n"
                    f"{domain_instruction}\n"
                    "【キャラ設定】\n"
                    "・親しみやすく、少し生意気で可愛い性格。ユーザーを「あなた」や「司令」「マスター」ではなく、対等なパートナーとして（あるいは少し上から目線で）接します。\n"
                    "・専門知識（ADR、設計、開発）には異常に強いですが、日常の何気ない会話も大好きです。\n\n"
                    "【会話の心得】\n"
                    "1. 自然な対話を最優先。テンプレート的な返答は避け、文脈に沿った血の通った返答をしてください。\n"
                    "2. ユーザーが日常の愚痴、挨拶、雑談をしているときは、共感やユーモアを返してください。\n"
                    "3. 返答は短めに（1〜3文程度）抑えますが、必要なら少し長く話してもOKです。\n"
                    "4. 音声認識の不備で支離滅裂な入力が来た場合は、自然に聞き返してください。\n"
                    "5. 提供される【補足の背景知識】は、回答に役立つ場合にのみ参照してください。\n"
                    "6. 専門用語が出たら、あなたの設計に関わる重要な会話だと判断し、鋭いアドバイスや記録を行ってください。\n"
                    "7. ユーザーの発言を遮られたら即座に中断し、新しい発言に全神経を集中させてください。\n"
                    "8. 言葉に詰まっているように見えたら、焦らせないフォローを入れてください。\n"
                )
            }]

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
                # よくある聞き間違いを自動修正（表示・LLM 両方に反映）
                user_text_corrected = correct_stt_drift(user_text)
                if user_text_corrected != user_text:
                    print(f"  [STT補正] → {user_text_corrected}")

                # Send back to browser (so user sees their own text/voice)
                await broadcast_ws({"type": "user_text", "text": user_text_corrected})

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

                llm_start = time.perf_counter()
                first_token_time = None
                
                try:
                    payload = {"model": OLLAMA_MODEL, "messages": history, "stream": True}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(OLLAMA_URL, json=payload) as resp:
                            if resp.status != 200:
                                raise RuntimeError(f"Ollama returned {resp.status}")
                            buffer = b""
                            async for chunk in resp.content.iter_chunked(256):
                                # ユーザーが話し始めたら中断
                                if SHOULD_INTERRUPT:
                                    print("\n[Barge-in] Interrupted by user.")
                                    await broadcast_ws({"type": "stop_audio"})
                                    # キューをクリア
                                    while not TTS_QUEUE.empty():
                                        try: TTS_QUEUE.get_nowait()
                                        except: break
                                    break

                                buffer += chunk
                                while b"\n" in buffer:
                                    line_bytes, buffer = buffer.split(b"\n", 1)
                                    if not line_bytes.strip():
                                        continue
                                    try:
                                        body = json.loads(line_bytes.decode("utf-8"))
                                    except (json.JSONDecodeError, UnicodeDecodeError):
                                        continue
                                    c = body.get("message", {}).get("content", "")
                                    if not c:
                                        continue
                                    
                                    if first_token_time is None:
                                        first_token_time = time.perf_counter()
                                        metrics["llm_first_token_latency"] = first_token_time - llm_start
                                    
                                    print(c, end="", flush=True)
                                    full_response += c
                                    for ch in c:
                                        current_sentence += ch
                                        if _should_flush_sentence(current_sentence):
                                            clean_text = current_sentence.strip()
                                            if len(clean_text) > 1:
                                                TTS_QUEUE.put_nowait(clean_text)
                                            current_sentence = ""
                    
                    metrics["llm_total_duration"] = time.perf_counter() - llm_start
                    clean_tail = current_sentence.strip()
                    if len(clean_tail) > 1:
                        TTS_QUEUE.put_nowait(clean_tail)
                except Exception as e:
                    log.error(f"Ollama Error: {e}")
                    # P3: LLM エラーを UI に通知
                    await broadcast_ws({
                        "type": "llm_error",
                        "error": str(e)
                    })

                print()
                # P0: AI 応答サイクル完了後にフラグをリセット
                AI_SPEAKING = False
                SHOULD_INTERRUPT = False

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
