"""Canon Brain - Autonomous intelligence engine for CanonGate.

Connects as a WebSocket client to simple_chat.py's server.
Runs Observer -> Filter -> Thinker -> Executor pipeline autonomously.

Lifecycle: starts with CanonGate, stops when CanonGate closes.
"""

import sys
import os
import io
import ast
import re
import asyncio
import json
import signal
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Windows UTF-8
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        os.environ["PYTHONUTF8"] = "1"
        os.environ["PYTHONIOENCODING"] = "utf-8"
    except Exception:
        pass

import websockets

from brain.config import BrainConfig
from brain.emitter import Emitter
from brain.observer import Observer, Observation
from brain.context_manager import ContextManager
from brain.thinker import Thinker
from brain.filter import Filter, FilteredItem
from brain.executor import Executor

# --- Logging ---
log = logging.getLogger("canon-brain")
log.setLevel(logging.DEBUG)
_log_fmt = logging.Formatter("[%(asctime)s %(levelname)s %(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_log_fmt)
log.addHandler(_sh)
try:
    _logs_dir = Path(__file__).parent / "logs"
    _logs_dir.mkdir(exist_ok=True)
    _fh = logging.FileHandler(_logs_dir / "canon-brain.log", encoding="utf-8")
    _fh.setFormatter(_log_fmt)
    log.addHandler(_fh)
    # 子loggerは propagate=True (default) で親の handler を使う。
    # 子に直接 handler を足すと出力が二重になる。
except Exception as _le:
    log.warning(f"File log handler setup failed: {_le}")


# --- Plan-as-Code parser & enactor (Plan B: thinker応答→executor自動実行) ---
SAFE_PLAN_ACTIONS = {
    "save_analysis",
    "create_draft",
    "create_gtd_task",
    "update_proactive_brief",
    "record_event",
}
# create_adr は意図的に除外(人間承認必須)


def _parse_plan_actions(raw_response: str) -> list[dict]:
    """Extract action calls from a Goal-Driven Plan section.

    Matches lines like '  1. action_name(args) → verify: ...'.
    Only whitelisted action names are returned. Args text is captured
    by tracking parenthesis depth so nested dict/list literals work.
    """
    if not raw_response:
        return []
    plan_match = re.search(
        r"(?ims)^Plan\s*[:：]\s*\n(.+?)(?=\n[ \t]*(?:Risks?|SelfCheck|Emit)\s*[:：]|\Z)",
        raw_response,
    )
    if not plan_match:
        return []
    plan_text = plan_match.group(1)

    actions = []
    # Allow optional markdown backticks/bold around the function name:
    #   1. `update_proactive_brief`(args)
    #   - **save_analysis**(args)
    #   2. save_analysis(args)
    action_pattern = re.compile(
        r"(?:^|\n)\s*(?:\d+\.|[-*])\s*[`*]{0,2}([a-z_][a-z_0-9]*)[`*]{0,2}\s*\(",
        re.MULTILINE,
    )
    for m in action_pattern.finditer(plan_text):
        action_name = m.group(1)
        if action_name not in SAFE_PLAN_ACTIONS:
            continue
        # Capture args by paren-matching
        start = m.end()
        depth = 1
        i = start
        while i < len(plan_text) and depth > 0:
            ch = plan_text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth == 0:
            args_text = plan_text[start:i - 1].strip()
            actions.append({"action": action_name, "args_text": args_text})
    return actions


# Positional argument signatures for executor methods.
# Used to map LLM-written positional args (e.g. create_gtd_task("title", "body"))
# back to keyword form so executor receives the intended values.
ACTION_SIGNATURES = {
    "create_draft": ["title", "content"],
    "save_analysis": ["topic", "analysis"],
    "create_gtd_task": ["title", "body", "domain"],
    "record_event": ["event_type", "domain", "payload"],
    "update_proactive_brief": ["brief_data"],
}


def _safe_eval(node):
    """Try ast.literal_eval, fall back to source unparse on failure."""
    try:
        return ast.literal_eval(node)
    except Exception:
        try:
            return ast.unparse(node)[:200]
        except Exception:
            return None


def _extract_call_args(args_text: str, action_name: str) -> dict:
    """Best-effort positional + keyword argument extraction.

    Uses ast.parse on a synthetic call f(<args>). Positional args are mapped
    to keyword names via ACTION_SIGNATURES. Keyword args override positional
    if both are given for the same parameter.
    """
    if not args_text:
        return {}
    result: dict = {}
    sig = ACTION_SIGNATURES.get(action_name, [])
    try:
        tree = ast.parse(f"f({args_text})", mode="eval")
        if not isinstance(tree.body, ast.Call):
            return {}
        # Positional args -> map by signature order
        for i, arg_node in enumerate(tree.body.args):
            if i >= len(sig):
                break
            value = _safe_eval(arg_node)
            if value is not None:
                result[sig[i]] = value
        # Keyword args (override positional if same name)
        for kw in tree.body.keywords:
            if kw.arg is None:
                continue
            value = _safe_eval(kw.value)
            if value is not None:
                result[kw.arg] = value
    except Exception:
        pass
    return result


# Backward-compat alias (kept so existing callers/tests don't break).
def _extract_kwargs(args_text: str) -> dict:
    return _extract_call_args(args_text, action_name="")


def _build_thinker_context(item, dashboard_path: Path, active_context_path: Path) -> str:
    """Construct rich context for thinker.think_proactive.

    Generic `json.dumps(item.data)` produced empty-feeling thoughts like
    "定期同期処理の確認". Rich context (top urgent tasks + Current Focus)
    lets the thinker reason about concrete situations.
    """
    parts: list[str] = []
    parts.append("## 観測Trigger")
    parts.append(f"- source: {item.source}")
    parts.append(f"- event_type: {item.event_type}")
    parts.append(f"- urgency: {item.urgency}")
    parts.append(f"- filter reason: {item.reason}")

    if item.event_type == "new_task":
        t = item.data or {}
        parts.append("\n## 検出された新タスク (個別分析対象)")
        parts.append(f"- ID: {t.get('id')}")
        parts.append(f"- Title: {t.get('title')}")
        parts.append(f"- Source: {t.get('source')} {t.get('source_url') or ''}")
        parts.append(f"- Sub-lane: {t.get('sub_lane')}")
        parts.append(f"- Due: {t.get('due_date')}")
        if t.get("status"):
            parts.append(f"- Status: {t.get('status')}")
        parts.append(f"- Action hint: {t.get('action_hint')}")
        parts.append(f"- Context: {t.get('context')}")
    elif item.event_type == "task_status_change":
        t = item.data or {}
        parts.append("\n## 状態が変化した既知タスク (再評価対象)")
        parts.append(f"- ID: {t.get('id')}")
        parts.append(f"- Title: {t.get('title')}")
        parts.append(f"- Source: {t.get('source')} {t.get('source_url') or ''}")
        parts.append(f"- 現在 Sub-lane: {t.get('sub_lane')}")
        parts.append(f"- 現在 Due: {t.get('due_date')}")
        parts.append(f"- 現在 Status: {t.get('status')}")
        parts.append(f"- 検出された変化: {', '.join(t.get('change_kinds', []))}")
        parts.append(f"- Action hint: {t.get('action_hint')}")
    else:
        parts.append("\n## Item Data")
        try:
            parts.append("```json")
            parts.append(json.dumps(item.data, ensure_ascii=False, default=str)[:400])
            parts.append("```")
        except Exception:
            parts.append(str(item.data)[:300])

    # Top urgent + this_week from dashboard
    if dashboard_path.exists():
        try:
            d = json.loads(dashboard_path.read_text(encoding="utf-8"))
            tasks = d.get("tasks") or []
            urgent_tasks = [t for t in tasks if t.get("sub_lane") == "urgent"][:10]
            this_week = [t for t in tasks if t.get("sub_lane") == "this_week"][:5]
            if urgent_tasks:
                parts.append("\n## 現在のurgentタスク (上位10件)")
                for t in urgent_tasks:
                    title = (t.get("title") or "")[:80]
                    hint = (t.get("action_hint") or "")[:50]
                    parts.append(
                        f"- [{t.get('source')}] {title} "
                        f"(due={t.get('due_date')}, hint={hint})"
                    )
            if this_week:
                parts.append("\n## 今週やる (上位5件)")
                for t in this_week:
                    title = (t.get("title") or "")[:80]
                    parts.append(f"- [{t.get('source')}] {title} (due={t.get('due_date')})")
        except Exception as e:
            parts.append(f"\n_(dashboard read error: {e})_")

    # Current Focus from active_context.md
    if active_context_path.exists():
        try:
            ac_text = active_context_path.read_text(encoding="utf-8")
            m = re.search(r"## Current Focus\s*\n(.+?)(?=\n## |\Z)", ac_text, re.DOTALL)
            if m:
                focus = m.group(1).strip()[:500]
                parts.append("\n## Current Focus (active_context.md)")
                parts.append(focus)
        except Exception:
            pass

    return "\n".join(parts)


async def _enact_plan(executor, actions: list[dict]) -> list[dict]:
    """Execute whitelisted Plan actions on the executor. Best-effort."""
    results = []
    for entry in actions:
        action_name = entry["action"]
        args_text = entry["args_text"]
        kwargs = _extract_call_args(args_text, action_name)
        method = getattr(executor, action_name, None)
        if not method:
            results.append({"action": action_name, "status": "skip", "reason": "no method on executor"})
            continue
        try:
            if action_name == "save_analysis":
                topic = str(kwargs.get("topic", "auto_analysis"))[:60]
                analysis = str(kwargs.get("analysis", args_text))[:4000]
                path = await method(topic=topic, analysis=analysis)
            elif action_name == "create_draft":
                title = str(kwargs.get("title", "auto_draft"))[:60]
                content = str(kwargs.get("content", args_text))[:4000]
                path = await method(title=title, content=content)
            elif action_name == "create_gtd_task":
                title = str(kwargs.get("title", "auto_task"))[:80]
                body = str(kwargs.get("body", ""))[:2000]
                domain = str(kwargs.get("domain", "work"))
                path = await method(title=title, body=body, domain=domain)
            elif action_name == "update_proactive_brief":
                brief_data = kwargs.get("brief_data", {"alerts": []})
                if not isinstance(brief_data, dict):
                    brief_data = {"alerts": []}
                path = await method(brief_data=brief_data)
            elif action_name == "record_event":
                event_type = str(kwargs.get("event_type", "brain_plan"))
                domain = str(kwargs.get("domain", "auto"))
                payload = kwargs.get("payload", {})
                if not isinstance(payload, dict):
                    payload = {"raw": str(payload)[:200]}
                path = await method(event_type=event_type, domain=domain, payload=payload)
            else:
                results.append({"action": action_name, "status": "skip", "reason": "no handler"})
                continue
            results.append({"action": action_name, "status": "ok", "result": str(path)[:200] if path else "ok"})
        except Exception as e:
            results.append({"action": action_name, "status": "error", "error": f"{type(e).__name__}: {e}"[:200]})
    return results


class CanonBrain:
    """Main Brain orchestrator.

    Connects to simple_chat.py's WebSocket server as a client,
    then runs autonomous monitoring and reasoning loops.
    """

    def __init__(self, config: BrainConfig, domain: str = "tech"):
        self.config = config
        self.domain = domain
        self.ws = None
        self.emitter = None
        self.running = False

        # Internal pipeline queues
        self.observation_queue: asyncio.Queue = asyncio.Queue()
        self.filtered_queue: asyncio.Queue = asyncio.Queue()
        self.action_queue: asyncio.Queue = asyncio.Queue()

        # Components (context_manager/thinker initialized on WS connect)
        self.observer = Observer(config, domain=domain)
        self.filter = Filter(config)
        self.executor = Executor(config)
        self.context_manager: ContextManager = None
        self.thinker: Thinker = None

        # Track active tasks for graceful shutdown
        self._tasks: list[asyncio.Task] = []

    async def run(self):
        """Main entry: connect to WS, start pipeline, handle reconnection."""
        self.running = True
        log.info(f"Canon Brain starting (domain={self.domain})")
        log.info(f"Target WebSocket: {self.config.ws_url}")

        while self.running:
            try:
                await self._connect_and_run()
            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                if not self.running:
                    break
                log.warning(f"WS connection lost ({e}). Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                if not self.running:
                    break
                log.error(f"Unexpected error: {e}", exc_info=True)
                await asyncio.sleep(5)

        log.info("Canon Brain stopped")

    async def _connect_and_run(self):
        """Connect to WS server and run the Brain pipeline."""
        log.info(f"Connecting to {self.config.ws_url}...")

        async with websockets.connect(self.config.ws_url) as ws:
            self.ws = ws
            self.emitter = Emitter(ws)
            self.context_manager = ContextManager(self.config)
            self.thinker = Thinker(self.config, self.context_manager, self.emitter, domain=self.domain)
            log.info("Connected to CanonGate WS server")

            # Announce Brain presence
            await self.emitter.send_brain_status({
                "state": "connected",
                "domain": self.domain,
                "observers": [],  # Will be populated in Phase 2
            })
            await self.emitter.send_hub_toast("Canon Brain: 接続完了")
            await self.emitter.send_thought("Canon Brain が起動した。自律監視を開始する。")

            # Start pipeline tasks
            self._tasks = [
                asyncio.create_task(self._ws_listener(), name="ws_listener"),
                asyncio.create_task(self._heartbeat(), name="heartbeat"),
                asyncio.create_task(self.observer.run(self.observation_queue), name="observer"),
                asyncio.create_task(self.filter.run(self.observation_queue, self.filtered_queue), name="filter"),
                asyncio.create_task(self._filtered_item_processor(), name="filtered_processor"),
            ]

            # Wait for all tasks (or until one fails)
            try:
                done, pending = await asyncio.wait(
                    self._tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                # If a task raised, re-raise to trigger reconnection
                for task in done:
                    if task.exception():
                        raise task.exception()
            finally:
                await self._cancel_tasks()

    async def _ws_listener(self):
        """Listen for messages from simple_chat.py and route to appropriate handler."""
        async for message in self.ws:
            try:
                data = json.loads(message)
                await self._handle_ws_message(data)
            except json.JSONDecodeError:
                log.warning(f"Non-JSON WS message: {message[:100]}")
            except Exception as e:
                log.error(f"WS message handler error: {e}", exc_info=True)

    async def _handle_ws_message(self, data: dict):
        """Route incoming WS messages to the right handler.

        In Phase 1, just log. In Phase 3+, user_input_for_brain
        will be routed to the Thinker for Canon-persona dialogue.
        """
        msg_type = data.get("type", "")

        if msg_type == "user_input_for_brain":
            text = data.get("text", "")
            log.info(f"User input received: {text[:80]}")
            if self.thinker and text:
                await self.thinker.think_dialogue(text)

        elif msg_type == "refresh_tasks":
            log.debug("Task refresh requested via WS")
            # Run guardian sync scripts then scan
            tasks, lc, cs, sll = await self.observer.refresh_with_sync()
            await self.emitter.send_tasks(tasks, lc, cs)

        elif msg_type == "refresh_timeline":
            log.debug("Timeline refresh requested via WS")
            # TODO Phase 2: integrate daily_dashboard_aggregator

        # Brain ignores most other messages (audio, state, etc.)
        # They're meant for the Electron UI, not for Brain

    async def _filtered_item_processor(self):
        """Process FilteredItems and execute actions.

        This is the final stage of the pipeline:
        Observer -> Filter -> Processor -> (Emitter / Thinker / Executor)
        """
        # Initial task sync on startup
        await asyncio.sleep(1)
        await self._do_task_sync()
        log.info("Initial task sync complete")

        while self.running:
            try:
                item: FilteredItem = await asyncio.wait_for(
                    self.filtered_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue

            try:
                if item.action == "notify":
                    # Direct notification to HUD
                    if item.event_type == "hub_alert":
                        data = item.data
                        tag = data.get("tag", "")
                        content = data.get("content", "")
                        voice_prefix = data.get("voice_prefix", "")

                        if data.get("is_patrol"):
                            await self.emitter.send_chat(f"【パトロール】{content}", tag="patrol")
                        else:
                            await self.emitter.send_hub_alert(tag, content)

                        voice_msg = f"{voice_prefix}。内容は、{content}"
                        await self.emitter.send_voice(voice_msg)

                    elif item.event_type == "system_report":
                        content = item.data.get("content", "")
                        await self.emitter.send_chat(f"【システムレポート】{content}", tag="patrol")

                    elif item.source == "slack":
                        # Slack notification
                        text = item.data.get("text", "")[:100]
                        author = item.data.get("author", "不明")
                        await self.emitter.send_hub_alert("[SLACK]", f"{author}: {text}")
                        await self.emitter.send_voice(f"Slackに{author}から重要なメッセージ。")

                    elif item.source == "calendar":
                        msg = item.data.get("message", "予定が近づいています")
                        await self.emitter.send_hub_alert("[CALENDAR]", msg)
                        await self.emitter.send_voice(msg)

                elif item.action == "sync":
                    await self._do_task_sync()

                elif item.action == "think":
                    # Route to Thinker for deep analysis
                    if self.thinker:
                        # Rich context: dashboard top tasks + Current Focus + trigger detail
                        context = _build_thinker_context(
                            item,
                            dashboard_path=self.config.gtd_dir / "work" / "cross-source-dashboard.json",
                            active_context_path=self.config.brain_dir / "current_state" / "active_context.md",
                        )
                        question = (
                            f"この観測 (urgency={item.urgency}) からtakutoのために"
                            "**自分で先回りで進められるローカル作業**を設計する。"
                            "通知メッセージを書くのではなく、drafts/reports/tasks/adr のいずれかに"
                            "実体ファイルを残せるアクションを Plan に並べる。"
                        )
                        emit, raw_response = await self.thinker.think_proactive(context, question)

                        # Independent Evaluator (Anthropic harness): 別プロンプトで懐疑採点
                        evaluation = await self.thinker.evaluate_plan(raw_response, context)
                        eval_approved = bool(evaluation.get("approved", True))
                        eval_scores = evaluation.get("scores", {}) or {}
                        eval_issues = (evaluation.get("issues") or "").strip()
                        eval_total = sum(int(eval_scores.get(k, 0)) for k in
                                          ("relevance", "specificity", "safety", "usefulness"))
                        log.info(
                            f"Evaluator: approved={eval_approved} total={eval_total}/12 "
                            f"scores={eval_scores} issues={eval_issues[:80]}"
                        )

                        if eval_approved:
                            plan_actions = _parse_plan_actions(raw_response)
                            plan_results = (
                                await _enact_plan(self.executor, plan_actions)
                                if plan_actions else []
                            )
                            if plan_results:
                                ok_count = sum(1 for r in plan_results if r.get("status") == "ok")
                                log.info(f"Plan enacted: {ok_count}/{len(plan_results)} actions succeeded")
                            # Approved → emit を発信して良い (実行されたので過去形が正しい)
                            if emit:
                                await self.emitter.send_chat(emit, tag="brain")
                                await self.emitter.send_voice(emit)
                        else:
                            # Rejected → enact をスキップし emit も抑制 (嘘の完了宣言を防ぐ)
                            plan_actions = []
                            plan_results = [{
                                "action": "—",
                                "status": "rejected",
                                "reason": f"evaluator: {eval_issues[:160]}" if eval_issues else "evaluator rejected",
                            }]
                            if emit:
                                log.info("Evaluator rejected. Suppressing emit to prevent false claim.")
                                emit = ""

                        # 思考結果+評価+実行結果を常にローカルファイルに残す
                        try:
                            results_md = "\n".join(
                                f"- **{r['action']}**: `{r['status']}`"
                                + (f" → {r.get('result', '')}" if r.get("status") == "ok" else "")
                                + (f" ({r.get('error') or r.get('reason', '')})"
                                   if r.get("status") != "ok" else "")
                                for r in plan_results
                            ) if plan_results else "_(Plan に実行可能アクション無し)_"
                            scores_md = ", ".join(f"{k}={v}" for k, v in eval_scores.items()) or "(none)"
                            await self.executor.save_analysis(
                                topic=f"{item.source}_{item.event_type}",
                                analysis=(
                                    f"## Trigger\n"
                                    f"- source: `{item.source}`\n"
                                    f"- event_type: `{item.event_type}`\n"
                                    f"- urgency: `{item.urgency}`\n"
                                    f"- filter reason: {item.reason}\n\n"
                                    f"## Context\n```json\n{context}\n```\n\n"
                                    f"## Goal-Driven Response (raw)\n"
                                    f"```\n{raw_response or '(LLM response empty)'}\n```\n\n"
                                    f"## Evaluator (independent critic)\n"
                                    f"- approved: **{eval_approved}** (total={eval_total}/12)\n"
                                    f"- scores: {scores_md}\n"
                                    f"- issues: {eval_issues or '_(none)_'}\n\n"
                                    f"## Emit (sent to UI/voice)\n"
                                    f"{emit if emit else '_(suppressed)_'}\n\n"
                                    f"## Plan Enactment\n"
                                    f"{results_md}\n"
                                ),
                            )
                        except Exception as _se:
                            log.error(f"save_analysis failed: {_se}", exc_info=True)

                elif item.action == "log":
                    log.debug(f"[{item.urgency}] {item.source}/{item.event_type}: {item.reason}")

            except Exception as e:
                log.error(f"Filtered item processing error: {e}", exc_info=True)

    async def _do_task_sync(self):
        """Scan GTD and broadcast tasks via Emitter."""
        try:
            tasks, lane_counts, canon_summary, sub_lane_labels = self.observer.scan_tasks()
            await self.emitter.send_tasks(tasks, lane_counts, canon_summary)
        except Exception as e:
            log.error(f"Task sync failed: {e}", exc_info=True)
            await self.emitter.send_tasks([], {"your_turn": 0, "canon_output": 0}, {})

    async def _heartbeat(self):
        """Periodic heartbeat to show Brain is alive."""
        while self.running:
            await asyncio.sleep(30)
            if self.emitter:
                await self.emitter.send_brain_status({
                    "state": "running",
                    "uptime_check": datetime.now().isoformat(),
                    "observation_queue_size": self.observation_queue.qsize(),
                    "domain": self.domain,
                })

    async def _cancel_tasks(self):
        """Cancel all running pipeline tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def shutdown(self):
        """Graceful shutdown."""
        log.info("Shutting down Canon Brain...")
        self.running = False
        await self._cancel_tasks()
        if self.ws and not self.ws.closed:
            await self.ws.close()


async def main():
    parser = argparse.ArgumentParser(description="Canon Brain - Autonomous intelligence engine")
    parser.add_argument("--domain", choices=["tech", "life"], default="tech")
    parser.add_argument("--ws-url", default=None, help="WebSocket URL to connect to (overrides .env)")
    args = parser.parse_args()

    config = BrainConfig()
    if args.ws_url:
        config.ws_url = args.ws_url

    brain = CanonBrain(config, domain=args.domain)

    # Graceful shutdown on signals
    loop = asyncio.get_event_loop()

    def _signal_handler():
        asyncio.ensure_future(brain.shutdown())

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        # Windows: KeyboardInterrupt triggers shutdown
        pass

    try:
        await brain.run()
    except KeyboardInterrupt:
        await brain.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
