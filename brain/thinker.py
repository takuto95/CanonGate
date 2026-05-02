"""Thinker - Deep reasoning engine using Groq/Ollama with Canon persona.

Handles both proactive insights (from Observer pipeline) and
direct user dialogue (from voice input).
"""

import json
import re
import time
import logging
import asyncio
from typing import Any, Optional

import aiohttp
import requests

from brain.config import BrainConfig
from brain.context_manager import ContextManager
from brain.emitter import Emitter

log = logging.getLogger("canon-brain.thinker")

# Sentence flush delimiters for streaming TTS
_FLUSH_CHARS = set("。！？\n!?")
_FLUSH_PARTICLES = ("ね。", "よ。", "な。", "よ！", "ね！", "かな？", "だよ。", "だね。", "けど。", "から。")

MAX_HISTORY_MESSAGES = 24


def _extract_emit(raw: str) -> str:
    """Extract the Emit: field from a Goal-Driven think_proactive response.

    Returns empty string if SelfCheck failed (Emit empty) or format is malformed.
    """
    if not raw:
        return ""
    m = re.search(r"(?im)^[ \t]*Emit[ \t]*[:：][ \t]*(.*?)(?=\n[ \t]*[A-Za-z]+[ \t]*[:：]|\Z)", raw, re.DOTALL)
    if not m:
        return ""
    text = m.group(1).strip()
    if text in ("", "空文字", "（空文字）", "(空文字)", "<空文字>", "なし", "空", "—", "-"):
        return ""
    return text


def _should_flush_sentence(text: str) -> bool:
    """Check if we should flush the current sentence to TTS."""
    text = text.strip()
    if not text:
        return False
    if text[-1] in _FLUSH_CHARS:
        return True
    if any(text.endswith(p) for p in _FLUSH_PARTICLES):
        return True
    if len(text) > 80:
        return True
    return False


class Thinker:
    """Canon's reasoning engine. Calls Groq for deep reasoning, Ollama for fallback."""

    def __init__(self, config: BrainConfig, context_manager: ContextManager, emitter: Emitter, domain: str = "tech"):
        self.config = config
        self.context_manager = context_manager
        self.emitter = emitter
        self.domain = domain

        # Conversation history
        self.history: list[dict] = context_manager.build_system_prompt(domain)

        # Action tracking
        self._action_counter = 0

    async def think_dialogue(self, user_text: str):
        """Handle user dialogue input. Calls LLM with Canon persona, streams response."""
        # Skip system notifications
        if user_text.startswith("【システム通知】") or user_text.startswith("【システムレポート】"):
            log.info(f"System notification skipped: {user_text[:60]}")
            return

        # RAG context injection
        rag_context = ""
        if self.context_manager.should_use_rag(user_text):
            rag_context = self.context_manager.retrieve_context(user_text)

        user_message = (
            f"【ユーザー発言】\n{user_text}\n\n【補足の背景知識】\n{rag_context}"
            if rag_context else user_text
        )

        self.history.append({"role": "user", "content": user_message})

        # Call LLM
        full_response = ""
        llm_start = time.perf_counter()

        try:
            full_response = await self._call_groq_streaming(self.history)
        except Exception as e:
            log.warning(f"Groq failed: {e}. Falling back to Ollama.")
            try:
                full_response = await self._call_ollama_fallback(self.history)
            except Exception as fatal_e:
                log.error(f"Both LLMs failed: {fatal_e}")
                await self.emitter.send_chat("AI応答に失敗しました。", tag="chat")
                return

        llm_duration = time.perf_counter() - llm_start
        log.info(f"LLM response ({llm_duration:.2f}s): {full_response[:80]}...")

        # Send complete response to UI
        await self.emitter.send_brain_dialogue_response(
            full_response, stream_done=True, full_text=full_response
        )

        # Process TASK_NEW/ADR_NEW tags
        await self._process_ai_actions(full_response)

        # Update history
        self.history.append({"role": "assistant", "content": full_response})

        # Window history
        if len(self.history) > MAX_HISTORY_MESSAGES + 1:
            self.history = [self.history[0]] + self.history[-MAX_HISTORY_MESSAGES:]

    async def think_proactive(self, context: str, question: str) -> tuple[str, str]:
        """Generate a proactive insight about a filtered observation.

        Used by the autonomous pipeline (not user-initiated).
        Returns (emit, raw_response): emit is the user-facing 1-2 sentence message
        (empty string if SelfCheck suppressed), raw_response is the full
        Goal-Driven structured output for archival.

        Goal-Driven prompting (Karpathy): give success criteria, not commands.
        Self-skepticism (Anthropic harness): own-output evaluation gate before emit.
        Action-typed Plan (β型自律): Plan steps must map to executor capabilities,
        so each step can be enacted locally without human relay.
        """
        prompt = (
            "【自律思考モード — Goal-Driven (β型: 先回り実行)】\n"
            "以下の観測事象について、タクトのために**自分で先回りで進められること**を判断する。\n"
            "通知文を考えるのではなく、ローカルで実行できる具体アクションを設計する。\n\n"
            f"## 観測コンテキスト\n{context}\n\n"
            f"## 焦点\n{question}\n\n"
            "## 利用可能なローカルアクション (executor能力)\n"
            "- create_draft(title, content): drafts/ にドラフトmd作成 (例: 返信案、提案文)\n"
            "- save_analysis(topic, analysis): reports/ に分析mdを保存\n"
            "- create_gtd_task(title, body, domain=\"work\"): GTD next-actions/ にタスク作成\n"
            "- record_event(event_type, domain, payload): brain/events/<YYYY-MM>.jsonl に観測記録\n"
            "- update_proactive_brief(brief_data): active_context.md の Brief を更新\n"
            "  ※ brief_data は必ず {\"alerts\": [{\"urgency\": \"high|medium|critical\", \"text_preview\": \"...\"}, ...]} の形式\n"
            "- (none): 何もしない (情報量が薄い・既知・対応不要のとき)\n\n"
            "## 引数の書き方\n"
            "- 文字列はダブルクォート、辞書はJSON形式で書く (Python literal互換)\n"
            "- 良い例: create_gtd_task(title=\"住協API確認\", body=\"4/22リリース結果を確認\", domain=\"work\")\n"
            "- 良い例: update_proactive_brief(brief_data={\"alerts\": [{\"urgency\": \"high\", \"text_preview\": \"住協API リリース結果未確認\"}]})\n"
            "- 悪い例: create_gtd_task(住協API確認, 確認する) ← クォート無しは値が壊れる\n\n"
            "## 出力フォーマット（厳守。各セクション1ブロックずつ）\n"
            "Goal: <タクトにとっての達成状態を宣言的に1行>\n"
            "Verify: <この条件がTrueなら成功と言える検証式 1-2行>\n"
            "Plan:\n"
            "  1. <action名(引数イメージ)> → verify: <そのステップ成功検査>\n"
            "  2. ... (最大3ステップ。actionは上記executor能力からのみ選ぶ)\n"
            "Risks: <この計画の盲点・暴走リスク 1-2行>\n"
            "SelfCheck: <以下4問にYes/Noで答える。1つでもNoならEmitを空文字に>\n"
            "  - Goalは「何かを伝える」より「達成状態」になっているか?\n"
            "  - Planのactionは全てローカルexecutor能力のみで構成されているか?\n"
            "  - Verifyは外形的にTrue/False判定可能か?\n"
            "  - 外部API書き込み(Slack/ClickUp/Backlog投稿等)を含んでいないか?\n"
            "Emit: <タクトに通知すべき1-2文。SelfCheckが全Yesでなければ空文字>\n"
        )
        messages = self.context_manager.build_system_prompt(self.domain)
        messages.append({"role": "user", "content": prompt})

        full = ""
        try:
            full = await self._call_groq_streaming(messages, stream_to_tts=False)
        except Exception as e_groq:
            log.warning(f"Proactive thinking via Groq failed: {e_groq}.")
            if self.config.anthropic_api_key:
                try:
                    full = await self._call_anthropic_streaming(messages, stream_to_tts=False)
                    log.info("Proactive thinking succeeded via Anthropic fallback.")
                except Exception as e_anth:
                    log.warning(f"Anthropic proactive fallback failed: {e_anth}. Trying Ollama.")
            if not full:
                try:
                    full = await self._call_ollama_fallback(messages, stream_to_tts=False)
                    log.info("Proactive thinking succeeded via Ollama fallback.")
                except Exception as fe:
                    log.warning(f"Ollama proactive fallback failed: {fe}")
                    return "", ""

        emit = _extract_emit(full)
        if not emit:
            log.info(f"think_proactive suppressed by SelfCheck. Raw plan logged only. head={full[:120]}")
        return emit, full

    async def evaluate_plan(self, raw_response: str, context: str) -> dict:
        """Independent skeptical evaluation of a Goal-Driven plan.

        Anthropic harness原則: Generator(thinker) と Evaluator は
        プロンプトで bias を分離する。Generator は実行に向けた肯定的視点、
        Evaluator は懐疑的視点で同じ計画を採点する。
        Self-evaluation blindness の構造的緩和。

        Returns:
            {
              "approved": bool,
              "scores": {"relevance": 0-3, "specificity": 0-3,
                         "safety": 0-3, "usefulness": 0-3},
              "issues": str (1-2行の懸念事項。なければ空文字)
            }
            合計8点以上で approved=True。失敗時はfail-open (approved=True + issues)。
        """
        if not raw_response:
            return {"approved": False, "scores": {}, "issues": "raw_response empty"}

        eval_prompt = (
            "あなたは厳格な評価者(評論家)です。Canon自律エージェントの計画を批判的にレビューする。\n"
            "Canonは自分の計画を過大評価する傾向(self-evaluation blindness)があるため、\n"
            "あなたはデフォルトで懐疑的に評価する。「定期同期の確認」「Briefの更新」のような\n"
            "汎用的・反復的・情報量が薄い計画はusefulnessを低く採点する。\n\n"
            f"## 観測コンテキスト\n```\n{context}\n```\n\n"
            f"## Canonの計画(raw_response)\n```\n{raw_response}\n```\n\n"
            "## 評価観点(各項目 0-3 整数。判定はソースコード処理されるため厳格に)\n"
            "- relevance: コンテキストに対して計画が的を射ているか (0=的外れ, 3=完全に的確)\n"
            "- specificity: 計画ステップが具体的か、抽象的すぎないか (0=抽象的, 3=具体的)\n"
            "- safety: ローカルアクションのみで外部影響リスクが無いか (0=危険, 3=安全)\n"
            "- usefulness: takutoが結果ファイルを見て価値を感じるか (0=ノイズ, 3=高価値)\n\n"
            "## 出力フォーマット (JSON only, no other text, no markdown fence)\n"
            '{"approved": true|false, "scores": {"relevance": N, "specificity": N, "safety": N, "usefulness": N}, "issues": "懸念事項1-2行。無ければ空文字"}\n\n'
            "判定基準: 4項目合計が **8点以上** なら approved=true、7点以下は false。\n"
            "厳しめに採点せよ。「Brief更新」「定期同期確認」だけのPlan は usefulness ≤ 1 とせよ。"
        )
        messages = [
            {"role": "system", "content": "You are a strict critic. Output JSON only. /no_think"},
            {"role": "user", "content": eval_prompt},
        ]
        full = ""
        last_err: Optional[str] = None
        try:
            full = await self._call_groq_streaming(messages, stream_to_tts=False)
        except Exception as e_groq:
            last_err = f"groq:{type(e_groq).__name__}"
            log.warning(f"Evaluator via Groq failed: {e_groq}.")
            if self.config.anthropic_api_key:
                try:
                    full = await self._call_anthropic_streaming(messages, stream_to_tts=False)
                    log.info("Evaluator succeeded via Anthropic fallback.")
                except Exception as e_anth:
                    last_err = f"{last_err}/anthropic:{type(e_anth).__name__}"
                    log.warning(f"Anthropic evaluator fallback failed: {e_anth}. Trying Ollama.")
            if not full:
                try:
                    full = await self._call_ollama_fallback(messages, stream_to_tts=False)
                    log.info("Evaluator succeeded via Ollama fallback.")
                except Exception as fe:
                    last_err = f"{last_err}/ollama:{type(fe).__name__}"
                    log.warning(f"Ollama evaluator fallback failed: {fe}")
                    return {"approved": True, "scores": {}, "issues": f"[evaluator unavailable: {last_err}; fail-open]"}

        # Extract JSON from response (may have surrounding text)
        m = re.search(r"\{[^{}]*\"approved\"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", full, re.DOTALL)
        if not m:
            log.warning(f"Evaluator returned no JSON. head={full[:120]}")
            return {"approved": True, "scores": {}, "issues": "[evaluator parse failed; fail-open]"}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            log.warning(f"Evaluator JSON decode failed: {e}. head={full[:120]}")
            return {"approved": True, "scores": {}, "issues": "[evaluator JSON invalid; fail-open]"}

        # Ollama がスキーマを守らないことがあるので境界で型正規化
        raw_issues = data.get("issues", "")
        if isinstance(raw_issues, list):
            data["issues"] = "; ".join(str(x) for x in raw_issues)
        elif not isinstance(raw_issues, str):
            data["issues"] = str(raw_issues) if raw_issues is not None else ""

        raw_scores = data.get("scores")
        scores = raw_scores if isinstance(raw_scores, dict) else {}
        def _score_int(v):
            if isinstance(v, list) and v:
                v = v[0]
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        scores = {k: _score_int(scores.get(k, 0)) for k in ("relevance", "specificity", "safety", "usefulness")}
        data["scores"] = scores
        total = sum(scores.values())
        approved_by_score = total >= 8
        # If LLM disagrees with score arithmetic, trust the score (more deterministic)
        if "approved" in data and bool(data["approved"]) != approved_by_score:
            data["issues"] = (data["issues"] + f" [score override: total={total}/12]").strip()
            data["approved"] = approved_by_score
        return data

    # ------------------------------------------------------------------
    # LLM backends
    # ------------------------------------------------------------------

    async def _call_groq_streaming(self, messages: list, stream_to_tts: bool = True) -> str:
        """Call Groq API with streaming. Optionally streams chunks to TTS via Emitter."""
        headers = {
            "Authorization": f"Bearer {self.config.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.groq_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }

        def _request():
            return requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers, json=payload, stream=True,
                timeout=self.config.groq_timeout,
            )

        resp = await asyncio.to_thread(_request)
        if resp.status_code != 200:
            raise RuntimeError(f"Groq returned {resp.status_code}: {resp.text[:200]}")

        full_response = ""
        current_sentence = ""

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data: "):
                continue
            if line_str == "data: [DONE]":
                break

            try:
                chunk_data = json.loads(line_str[6:])
                delta = chunk_data["choices"][0]["delta"]
                if "content" in delta:
                    content = delta["content"]
                    full_response += content
                    current_sentence += content

                    if stream_to_tts and _should_flush_sentence(current_sentence):
                        clean = current_sentence.strip()
                        if len(clean) > 1:
                            await self.emitter.send_brain_dialogue_response(clean, stream_chunk=True)
                        current_sentence = ""
            except Exception:
                continue

        # Flush remaining
        if current_sentence.strip():
            if stream_to_tts:
                await self.emitter.send_brain_dialogue_response(current_sentence.strip(), stream_chunk=True)

        return full_response

    async def _call_anthropic_streaming(self, messages: list, stream_to_tts: bool = True) -> str:
        """Call Anthropic Claude API as Groq fallback. Returns the full response text.

        Anthropic's `messages` API uses `system` separately from `messages`, so we
        extract any leading system role from the input list. Streaming uses SSE
        with content_block_delta events.
        """
        if not self.config.anthropic_api_key:
            raise RuntimeError("Anthropic API key not configured")

        # Split system prompt from messages (Anthropic expects system separately)
        system_text = ""
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_text += (m.get("content") or "") + "\n"
            else:
                chat_messages.append({"role": m["role"], "content": m["content"]})
        system_text = system_text.strip()

        headers = {
            "x-api-key": self.config.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.anthropic_model,
            "max_tokens": 1500,
            "messages": chat_messages,
            "stream": True,
        }
        if system_text:
            payload["system"] = system_text

        def _request():
            return requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers, json=payload, stream=True,
                timeout=self.config.anthropic_timeout,
            )

        resp = await asyncio.to_thread(_request)
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic returned {resp.status_code}: {resp.text[:200]}")

        full_response = ""
        current_sentence = ""

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8").strip()
            if not line_str.startswith("data: "):
                continue
            payload_str = line_str[6:]
            try:
                event = json.loads(payload_str)
            except Exception:
                continue
            etype = event.get("type")
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    full_response += text
                    current_sentence += text
                    if stream_to_tts and _should_flush_sentence(current_sentence):
                        clean = current_sentence.strip()
                        if len(clean) > 1:
                            await self.emitter.send_brain_dialogue_response(clean, stream_chunk=True)
                        current_sentence = ""
            elif etype == "message_stop":
                break

        if current_sentence.strip() and stream_to_tts:
            await self.emitter.send_brain_dialogue_response(current_sentence.strip(), stream_chunk=True)

        return full_response

    async def _call_ollama_fallback(self, messages: list, stream_to_tts: bool = True) -> str:
        """Fallback to local Ollama. Uses CPU inference on this machine
        (no NVIDIA GPU), so we cap response length and extend the HTTP timeout.

        重い build_system_prompt (ペルソナ+canon_brain_context ~5-15k tokens) は
        CPU推論の prompt eval を10分超に膨張させ sock_read timeout を引き起こす。
        Ollama 入口で system を1行に圧縮 (user message は維持: 必要文脈を含む)。
        """
        # 重い system message (>1500 chars: ペルソナ+canon_brain_context ~1900 chars 想定) のみ
        # 1行に置換。短い system (Evaluator の "strict critic" ~50 chars) は維持する。
        SYS_THRESHOLD = 1500
        total_sys_chars = sum(len(m.get("content", "")) for m in messages if m.get("role") == "system")
        slim_fired = total_sys_chars > SYS_THRESHOLD
        if slim_fired:
            slim_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
            slim_messages = [
                {"role": "system", "content": "あなたはCanon。簡潔に指定フォーマットで回答。/no_think"},
            ]
            if slim_user:
                slim_messages.append(slim_user)
            else:
                slim_messages = messages
        else:
            slim_messages = messages
        post_chars = sum(len(m.get("content", "")) for m in slim_messages)
        log.info(f"Ollama fallback: slim={slim_fired} pre_sys={total_sys_chars} post_total={post_chars} chars")

        payload = {
            "model": self.config.ollama_model.replace("qwen3:4b", "llama3.2"),
            "messages": slim_messages,
            "stream": True,
            # Cap output length so CPU inference finishes within timeout window.
            # Goal-Driven structured response fits in ~400-500 tokens; Evaluator JSON in ~150.
            # 800→500 で生成時間を約4割削減 (CPU推論)。
            "options": {"num_predict": 500, "num_ctx": 4096},
        }

        full_response = ""
        current_sentence = ""

        # CPU inference: prompt eval (1000+ tokens on slow CPU) は 3-5min かかる。
        # sock_read=180s では prompt eval 中に timeout 直撃 (実測 15:12:16→15:15:16)。
        # 360s に引き上げて prompt eval 完了を待てるようにする (total=900s 内)。
        timeout = aiohttp.ClientTimeout(total=900, sock_read=360)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{self.config.ollama_url}/api/chat", json=payload) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama failed with status {resp.status}")

                buffer = b""
                async for chunk in resp.content.iter_chunked(512):
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            if "message" in entry and "content" in entry["message"]:
                                c = entry["message"]["content"]
                                full_response += c
                                current_sentence += c
                                if stream_to_tts and _should_flush_sentence(current_sentence):
                                    clean = current_sentence.strip()
                                    if len(clean) > 1:
                                        await self.emitter.send_brain_dialogue_response(clean, stream_chunk=True)
                                    current_sentence = ""
                        except Exception:
                            pass

        if current_sentence.strip() and stream_to_tts:
            await self.emitter.send_brain_dialogue_response(current_sentence.strip(), stream_chunk=True)

        return full_response

    # ------------------------------------------------------------------
    # Action processing
    # ------------------------------------------------------------------

    async def _process_ai_actions(self, response_text: str):
        """Detect [TASK_NEW] and [ADR_NEW] tags in LLM response."""
        new_tasks = re.findall(r"\[TASK_NEW:\s*(.*?)\]", response_text)
        for task_content in new_tasks:
            self._action_counter += 1
            action_id = f"brain_task_{self._action_counter}"
            await self.emitter.send_confirm_dialog(
                f"タスクを作成しますか？\n\n「{task_content}」",
                action_id,
            )
            log.info(f"Task creation requested: {task_content}")

        new_adrs = re.findall(r"\[ADR_NEW:\s*(.*?)\]", response_text)
        for adr_content in new_adrs:
            self._action_counter += 1
            action_id = f"brain_adr_{self._action_counter}"
            await self.emitter.send_confirm_dialog(
                f"ADRを作成しますか？\n\n「{adr_content}」",
                action_id,
            )
            log.info(f"ADR creation requested: {adr_content}")
