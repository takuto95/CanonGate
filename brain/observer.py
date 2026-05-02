"""Observer - Polling and file-watching for Canon Brain.

No LLM usage. Pure Python monitoring to detect state changes
and emit Observations into the pipeline.
"""

import os
import sys
import re
import json
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp

from brain.config import BrainConfig

log = logging.getLogger("canon-brain.observer")


# --- HUB Priority Tags (from simple_chat.py) ---
HUB_PRIORITY_TAGS = {
    "[URGENT]": "緊急の通知だよ！",
    "[SLACK]": "Slackに動きがあったよ！",
    "[BACKLOG]": "バックログに更新があったよ！",
    "[GITHUB]": "GitHubの動きがあったよ！",
    "[DEVIN]": "Devinからレポートが来たよ！",
    "[FINANCE]": "家計簿のチェック結果だよ！",
    "[SYSTEM_REPORT]": "システムレポートが届いたよ！",
    "[PATROL]": "パトロール報告だよ！",
    "[CALENDAR]": "予定の時間が近いよ！",
    "[ALE_START]": "オートループが動き出したよ！",
    "[MORNING]": "おはよう！今日のブリーフィングだよ！",
    "[MUSING]": "独り言だけど、いいかな？",
    "[WORK_TASK]": "仕事タスクの状況だよ！",
    "[CANON_RAN]": "Canon が仕事タスクを実行したよ！",
}


@dataclass
class Observation:
    """A single observation from a monitoring source."""
    source: str          # "file_watcher", "gtd", "calendar", "slack", etc.
    event_type: str      # "hub_alert", "task_changed", "calendar_event", etc.
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    requires_llm: bool = False  # True if ambiguous and needs Ollama classification


class Observer:
    """Monitors local files and external sources for changes.

    Emits Observations into a queue for the Filter to process.
    No LLM calls - pure polling and file-watching.
    """

    # Slack user ID → display name
    SLACK_USER_MAP = {
        "U026LMZ5V5L": "風岡",
        "U0Q84A29E": "高野",
        "U06RQGZ12DD": "鈴木涼也",
        "U04DJKW71HN": "齊藤",
        "U09DPSGRSJU": "瀧澤",
        "U08P1FWJ6CT": "岸原",
        "U02SH245WAZ": "鳥井",
        "U070ZGARZ": "三浦",
        "U094EPQGQJC": "稲垣",
        "U09E4BQCP28": "古山",
        "U018U4D52HX": "吉安",
        "U038PGKV2LT": "長木",
        "U01JDBR41JR": "佐藤",
        "U098G2BK674": "掛川",
        "S030E720QQJ": "フロントチーム",
    }
    TAKUTO_USER_ID = "U026LMZ5V5L"

    def __init__(self, config: BrainConfig, domain: str = "tech"):
        self.config = config
        self.domain = domain
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # State tracking for change detection
        self._report_log_size = 0
        self._gtd_file_mtimes: dict[str, float] = {}
        self._last_cross_source_mtime: float = 0
        # Track previously seen task IDs to detect new entries on each dashboard refresh
        self._previous_task_ids: set[str] = set()
        # Track per-task state to detect significant changes (sub_lane shift, due-date approach)
        self._previous_task_state: dict[str, dict] = {}

        # Slack polling state
        self._slack_last_ts: str = ""  # oldest=newest timestamp for incremental polling
        self._slack_state_file = config.logs_dir / "brain_slack_state.json"
        self._load_slack_state()

    async def run(self, observation_queue: asyncio.Queue, emit_callback=None):
        """Start all monitoring tasks.

        emit_callback: optional async function for direct emissions
                       (used for messages that bypass the Filter, like hub_alerts)
        """
        self._running = True
        self._emit_callback = emit_callback
        self._observation_queue = observation_queue
        log.info("Observer starting...")

        # Initialize report.log position
        report_log = self.config.canongate_dir / "logs" / "report.log"
        if report_log.exists():
            self._report_log_size = report_log.stat().st_size

        # Initialize GTD file mtimes
        self._scan_gtd_mtimes()

        self._tasks = [
            asyncio.create_task(self._watch_report_log(), name="watch_report_log"),
            asyncio.create_task(self._watch_gtd_files(), name="watch_gtd"),
            asyncio.create_task(self._periodic_task_sync(), name="periodic_task_sync"),
        ]

        # Slack + external source polling (tech domain only)
        if self.domain == "tech":
            if self.config.slack_bot_token:
                self._tasks.append(
                    asyncio.create_task(self._poll_slack(), name="poll_slack")
                )
            self._tasks.append(
                asyncio.create_task(self._poll_external_sources(), name="poll_external")
            )

        log.info(f"Observer started with {len(self._tasks)} watchers")

        # Wait for all
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()

    # ------------------------------------------------------------------
    # Report.log file watcher (migrated from simple_chat.py file_watcher_task)
    # ------------------------------------------------------------------

    async def _watch_report_log(self):
        """Watch report.log for new lines with priority tags."""
        log_path = self.config.canongate_dir / "logs" / "report.log"
        if not log_path.exists():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch()

        while self._running:
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    f.seek(self._report_log_size)
                    new_content = f.read()
                    self._report_log_size = f.tell()

                for line in new_content.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    # Check for priority tags
                    handled = False
                    for tag, voice_prefix in HUB_PRIORITY_TAGS.items():
                        if tag in line:
                            content = line.replace(tag, "").strip()
                            if "]" in content:
                                content = content.split("]", 1)[-1].strip()

                            await self._emit(Observation(
                                source="file_watcher",
                                event_type="hub_alert",
                                data={
                                    "tag": tag,
                                    "content": content,
                                    "voice_prefix": voice_prefix,
                                    "is_patrol": tag == "[PATROL]",
                                },
                            ))
                            handled = True
                            break

                    if not handled and "[TASK_SYNC]" in line:
                        await self._emit(Observation(
                            source="file_watcher",
                            event_type="task_sync_requested",
                            data={},
                        ))

                    if not handled and "[SYSTEM_REPORT]" in line:
                        content = line.replace("[SYSTEM_REPORT]", "").strip()
                        await self._emit(Observation(
                            source="file_watcher",
                            event_type="system_report",
                            data={"content": content},
                        ))

            except Exception as e:
                log.warning(f"Report log watch error: {e}")
                self._report_log_size = 0
                await asyncio.sleep(5)

            await asyncio.sleep(self.config.interval_report_log)

    # ------------------------------------------------------------------
    # GTD file watcher
    # ------------------------------------------------------------------

    def _scan_gtd_mtimes(self):
        """Build initial mtime map of GTD files."""
        domains = ["work"] if self.domain == "tech" else ["private"]
        for d in domains:
            for folder in ["next-actions", "evaluating"]:
                target = self.config.gtd_dir / d / folder
                if target.exists():
                    for f in target.glob("*.md"):
                        try:
                            self._gtd_file_mtimes[str(f)] = f.stat().st_mtime
                        except Exception:
                            pass

    async def _watch_gtd_files(self):
        """Detect GTD file changes (added/modified/deleted)."""
        while self._running:
            try:
                domains = ["work"] if self.domain == "tech" else ["private"]
                current_files: dict[str, float] = {}

                for d in domains:
                    for folder in ["next-actions", "evaluating"]:
                        target = self.config.gtd_dir / d / folder
                        if target.exists():
                            for f in target.glob("*.md"):
                                try:
                                    current_files[str(f)] = f.stat().st_mtime
                                except Exception:
                                    pass

                changed = False
                # New or modified files
                for path, mtime in current_files.items():
                    old = self._gtd_file_mtimes.get(path)
                    if old is None or mtime > old:
                        changed = True
                        break

                # Deleted files
                if not changed:
                    for path in self._gtd_file_mtimes:
                        if path not in current_files:
                            changed = True
                            break

                if changed:
                    self._gtd_file_mtimes = current_files
                    await self._emit(Observation(
                        source="gtd",
                        event_type="files_changed",
                        data={"file_count": len(current_files)},
                    ))

            except Exception as e:
                log.warning(f"GTD watch error: {e}")

            await asyncio.sleep(self.config.interval_gtd_watch)

    # ------------------------------------------------------------------
    # Periodic task sync (heartbeat replacement)
    # ------------------------------------------------------------------

    async def _periodic_task_sync(self):
        """Periodically trigger a full task sync broadcast."""
        while self._running:
            await asyncio.sleep(30)
            await self._emit(Observation(
                source="heartbeat",
                event_type="periodic_sync",
                data={},
            ))

    # ------------------------------------------------------------------
    # Task scanning (migrated from simple_chat.py _manual_task_sync_inner)
    # ------------------------------------------------------------------

    def scan_tasks(self) -> tuple[list[dict], dict, dict, dict]:
        """Scan GTD directories and return task data for broadcast.

        Returns: (final_tasks, lane_counts, canon_summary, sub_lane_labels)
        """
        domains_to_scan = ["work"] if self.domain == "tech" else ["private"]
        tasks = []

        for domain_name in domains_to_scan:
            for folder in ["next-actions", "evaluating"]:
                target_dir = self.config.gtd_dir / domain_name / folder
                if not target_dir.exists():
                    continue
                for f in target_dir.glob("*.md"):
                    if f.name in ("README.md", "INDEX.md"):
                        continue
                    is_work = (domain_name == "work")
                    title = f.stem
                    if title.replace("【実行中】", "").strip() == "INDEX":
                        continue
                    meta = _read_frontmatter(f)
                    is_canon_exec = str(meta.get("canon_executable", "")).lower() in ("true", "yes", "1")

                    category = "ego_proposal"
                    if folder == "evaluating":
                        category = "user_decision"
                    elif "【実行中】" in title:
                        category = "ego_running" if is_canon_exec else "user_running"
                    elif "【要整理】" in title:
                        category = "needs_org"

                    clean_title = title.replace("【実行中】", "").replace("【要整理】", "").strip()
                    project = _infer_project(clean_title)
                    priority_rank, priority_label = _extract_task_priority(clean_title, meta)
                    marker_dir = self.config.canon_dir / "logs" / "canon_run_markers"
                    cli_executed = (marker_dir / f"{f.stem}.txt").exists() if marker_dir.exists() else False
                    cli_failed = (marker_dir / f"{f.stem}.failed.txt").exists() if marker_dir.exists() else False
                    context, last_run = _extract_task_context(f, marker_dir)

                    tasks.append({
                        "id": f.name,
                        "title": clean_title,
                        "category": category,
                        "is_work": is_work,
                        "folder": folder,
                        "cli_executed": cli_executed,
                        "cli_failed": cli_failed,
                        "evaluated": (folder == "evaluating"),
                        "project": project,
                        "priority_rank": priority_rank,
                        "priority_label": priority_label,
                        "context": context,
                        "last_run": last_run,
                        "_meta": meta,
                    })

        # Inbox notes (協議メモ)
        inbox_for_notes = (self.config.gtd_dir / "work" / "inbox") if self.domain == "tech" else (self.config.agent_dir / "inbox")
        if inbox_for_notes.exists():
            for f in inbox_for_notes.glob("協議メモ-*.md"):
                stem = f.stem
                meta = _read_frontmatter(f)
                marker_dir = self.config.canon_dir / "logs" / "canon_run_markers"
                cli_executed = (marker_dir / f"{stem}.txt").exists() if marker_dir.exists() else False
                cli_failed = (marker_dir / f"{stem}.failed.txt").exists() if marker_dir.exists() else False
                priority_rank, priority_label = _extract_task_priority(stem, meta)
                tasks.append({
                    "id": f.name,
                    "title": stem,
                    "category": "user_decision",
                    "is_work": (self.domain == "tech"),
                    "folder": "inbox",
                    "cli_executed": cli_executed,
                    "cli_failed": cli_failed,
                    "evaluated": False,
                    "project": _infer_project(stem),
                    "priority_rank": priority_rank,
                    "priority_label": priority_label,
                })

        # Recent done tasks (24h)
        done_tasks = []
        for domain_name in domains_to_scan:
            done_dir = self.config.gtd_dir / domain_name / "done"
            if not done_dir.exists():
                continue
            cutoff = time.time() - 86400
            for f in sorted(done_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.name == "README.md":
                    continue
                try:
                    mtime = f.stat().st_mtime
                except Exception:
                    continue
                if mtime < cutoff:
                    break
                done_tasks.append({
                    "id": f.name,
                    "title": f.stem,
                    "category": "done_recent",
                    "is_work": (domain_name == "work"),
                    "folder": "done",
                    "cli_executed": True,
                    "cli_failed": False,
                    "evaluated": True,
                    "project": _infer_project(f.stem),
                    "priority_rank": 999,
                    "priority_label": "",
                    "completed_at": datetime.fromtimestamp(mtime).strftime("%m/%d %H:%M"),
                })
                if len(done_tasks) >= 15:
                    break

        # Proactive items
        proactive = _scan_proactive_items(self.config.canon_dir)
        existing_ids = {t["id"] for t in tasks}
        for p in proactive:
            if p["id"] not in existing_ids:
                tasks.append(p)

        # Classify into lanes
        visible_tasks = []
        canon_summary = {"cli_done": 0, "running": 0, "autonomous": 0, "failed": 0}

        for t in tasks:
            t["is_internal"] = t["id"].startswith("infer_") or t["id"].startswith("auto_")
            _meta = t.get("_meta", {})
            _is_canon_exec = str(_meta.get("canon_executable", "")).lower() in ("true", "yes", "1")

            if t.get("lane") == "your_turn":
                visible_tasks.append(t)
            elif t.get("cli_failed"):
                t["lane"] = "your_turn"
                reason = _extract_failure_reason(t["id"].replace(".md", ""), self.config.canon_dir)
                t["action_hint"] = "Canon 実行失敗"
                t["failure_reason"] = reason
                canon_summary["failed"] += 1
                visible_tasks.append(t)
            elif t["category"] == "user_decision":
                t["lane"] = "your_turn"
                t["action_hint"] = "あなたの判断が必要"
                visible_tasks.append(t)
            elif t["category"] == "user_running":
                t["lane"] = "your_turn"
                t["action_hint"] = "あなたが対応中"
                visible_tasks.append(t)
            elif t.get("cli_executed"):
                canon_summary["cli_done"] += 1
            elif t["category"] == "ego_running":
                canon_summary["running"] += 1
            elif t["is_internal"]:
                canon_summary["autonomous"] += 1
            else:
                t["lane"] = "your_turn"
                t["action_hint"] = "" if _is_canon_exec else "あなたの対応が必要"
                visible_tasks.append(t)

        for t in done_tasks:
            t["lane"] = "canon_output"
            t["is_internal"] = False
            t["action_hint"] = ""

        # cross-source-dashboard.json overlay
        sub_lane_labels = {}
        dashboard_json = self.config.gtd_dir / "work" / "cross-source-dashboard.json"
        dashboard_tasks = None

        if dashboard_json.exists():
            try:
                age_sec = datetime.now().timestamp() - dashboard_json.stat().st_mtime
                if age_sec < 86400:
                    with open(dashboard_json, "r", encoding="utf-8") as _f:
                        dash = json.load(_f)
                    dashboard_tasks = dash.get("tasks", [])
                    sub_lane_labels = dash.get("sub_lane_labels", {})
            except Exception as e:
                log.warning(f"cross-source-dashboard read failed: {e}")

        if dashboard_tasks is not None:
            _your_lanes = {"urgent", "this_week"}
            for dt in dashboard_tasks:
                sl = dt.get("sub_lane", "")
                dt["lane"] = "your_turn" if sl in _your_lanes else "_canon"
                dt["is_internal"] = False
                dt["is_work"] = True
                if not dt.get("action_hint"):
                    dt["action_hint"] = sub_lane_labels.get(sl, "")

            _bg_count = len([dt for dt in dashboard_tasks if dt.get("sub_lane") not in _your_lanes])
            canon_dash_tasks = dash.get("canon_tasks", []) if dash else []
            canon_summary["queue"] = len(canon_dash_tasks) + _bg_count
            canon_summary["queue_titles"] = [t["title"] for t in canon_dash_tasks[:10]]
            canon_summary["weekly_summary"] = dash.get("weekly_summary", [])
            canon_summary["weekly_you"] = dash.get("weekly_you_count", 0)
            canon_summary["weekly_canon"] = dash.get("weekly_canon_count", 0)
            canon_summary["projects_overview"] = dash.get("projects_overview", [])
            final_tasks = dashboard_tasks + done_tasks
            your_turn_count = len([dt for dt in dashboard_tasks if dt.get("sub_lane") in _your_lanes])
        else:
            final_tasks = visible_tasks + done_tasks
            your_turn_count = sum(1 for t in final_tasks if t.get("lane") == "your_turn")

        lane_counts = {"your_turn": your_turn_count, "canon_output": len(done_tasks)}
        return final_tasks, lane_counts, canon_summary, sub_lane_labels

    # ------------------------------------------------------------------
    # External source polling (Backlog, ClickUp, cross-source)
    # ------------------------------------------------------------------

    async def _poll_external_sources(self):
        """Periodically run guardian scripts to sync external data."""
        log.info("External source polling started")
        # Initial delay
        await asyncio.sleep(30)

        cycle = 0
        while self._running:
            cycle += 1
            try:
                # Cross-source sync every cycle (5 min)
                changed = await self._run_cross_source_sync()
                if changed:
                    await self._emit(Observation(
                        source="cross_source",
                        event_type="files_changed",
                        data={"trigger": "periodic_sync"},
                    ))
                    # Detect newly-appeared task IDs and emit one Observation per task
                    new_tasks = self._detect_new_tasks_from_dashboard()
                    for task in new_tasks:
                        await self._emit(Observation(
                            source="cross_source",
                            event_type="new_task",
                            data=task,
                            requires_llm=False,
                        ))
                    # Detect significant state changes on existing tasks
                    state_changes = self._detect_task_state_changes()
                    for chg in state_changes:
                        await self._emit(Observation(
                            source="cross_source",
                            event_type="task_status_change",
                            data=chg,
                            requires_llm=False,
                        ))

                # ClickUp sync every 2nd cycle (10 min)
                if cycle % 2 == 0 and self.config.clickup_api_token:
                    await self._run_clickup_sync()

                # Backlog check every 2nd cycle (10 min), offset from ClickUp
                if cycle % 2 == 1 and self.config.backlog_api_key:
                    await self._run_backlog_check()

            except Exception as e:
                log.warning(f"External source poll error: {e}")

            await asyncio.sleep(self.config.interval_cross_source)  # 5 min

    async def _run_cross_source_sync(self) -> bool:
        """Run cross_source_sync.py and return True if dashboard changed."""
        dashboard = self.config.gtd_dir / "work" / "cross-source-dashboard.json"
        old_mtime = dashboard.stat().st_mtime if dashboard.exists() else 0

        await self.run_guardian_script("cross_source_sync.py", timeout=90)

        new_mtime = dashboard.stat().st_mtime if dashboard.exists() else 0
        changed = new_mtime > old_mtime
        if changed:
            log.info("Cross-source dashboard updated")
        return changed

    def _detect_task_state_changes(self) -> list[dict]:
        """Detect significant state changes on previously-seen tasks.

        Triggers:
          - sub_lane shifted (e.g. this_week -> urgent, or any change)
          - due_date is now today or in the past (newly imminent / overdue)
          - status string changed

        First call seeds the state; subsequent calls compare and emit only deltas.
        """
        dashboard = self.config.gtd_dir / "work" / "cross-source-dashboard.json"
        if not dashboard.exists():
            return []
        try:
            data = json.loads(dashboard.read_text(encoding="utf-8"))
        except Exception:
            return []
        tasks = data.get("tasks") or []

        today_iso = datetime.now().date().isoformat()
        current_state: dict[str, dict] = {}
        for t in tasks:
            tid = t.get("id")
            if not tid:
                continue
            current_state[tid] = {
                "sub_lane": t.get("sub_lane", ""),
                "due_date": t.get("due_date"),
                "status": t.get("status", ""),
                "title": t.get("title", "")[:200],
                "source": t.get("source", ""),
                "source_url": t.get("source_url", ""),
                "action_hint": t.get("action_hint", "")[:200],
            }

        if not self._previous_task_state:
            self._previous_task_state = current_state
            return []

        changes: list[dict] = []
        for tid, cur in current_state.items():
            prev = self._previous_task_state.get(tid)
            if not prev:
                continue  # new task — handled by _detect_new_tasks_from_dashboard
            change_kinds: list[str] = []
            if prev.get("sub_lane") != cur.get("sub_lane"):
                change_kinds.append(f"sub_lane:{prev.get('sub_lane')}→{cur.get('sub_lane')}")
            if prev.get("status") != cur.get("status"):
                change_kinds.append(f"status:{prev.get('status')}→{cur.get('status')}")
            # Due-date imminence: was None/future, now today-or-past
            prev_due = prev.get("due_date")
            cur_due = cur.get("due_date")
            if cur_due and str(cur_due) <= today_iso:
                if not prev_due or str(prev_due) > today_iso:
                    change_kinds.append(f"due_imminent:{cur_due}")
            if change_kinds:
                changes.append({**cur, "id": tid, "change_kinds": change_kinds})

        self._previous_task_state = current_state
        if changes:
            log.info(f"Detected {len(changes)} task state change(s)")
        return changes

    def _detect_new_tasks_from_dashboard(self) -> list[dict]:
        """Compare current dashboard task IDs against the previous snapshot
        and return entries for newly-appeared tasks.

        First call seeds the snapshot and returns empty (no false-positive flood).
        """
        dashboard = self.config.gtd_dir / "work" / "cross-source-dashboard.json"
        if not dashboard.exists():
            return []
        try:
            data = json.loads(dashboard.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Failed to read dashboard: {e}")
            return []
        tasks = data.get("tasks") or []
        current_ids = {t.get("id") for t in tasks if t.get("id")}
        if not self._previous_task_ids:
            # First snapshot: seed only, do not flood the pipeline
            self._previous_task_ids = current_ids
            log.info(f"Dashboard snapshot seeded with {len(current_ids)} tasks (no events emitted)")
            return []
        new_ids = current_ids - self._previous_task_ids
        self._previous_task_ids = current_ids
        if not new_ids:
            return []
        log.info(f"Detected {len(new_ids)} new task(s) in dashboard")
        # Return a trimmed payload per new task (keeping fields useful for thinker context)
        new_tasks = []
        for t in tasks:
            tid = t.get("id")
            if tid not in new_ids:
                continue
            new_tasks.append({
                "id": tid,
                "title": t.get("title", "")[:200],
                "sub_lane": t.get("sub_lane", ""),
                "source": t.get("source", ""),
                "source_url": t.get("source_url", ""),
                "due_date": t.get("due_date"),
                "action_hint": t.get("action_hint", "")[:200],
                "context": t.get("context", "")[:200],
                "is_work": t.get("is_work", True),
            })
        return new_tasks

    async def _run_clickup_sync(self):
        """Run ClickUp task sync."""
        log.debug("Running ClickUp sync...")
        success = await self.run_guardian_script("clickup_my_tasks_sync.py", timeout=60)
        if success:
            log.info("ClickUp sync completed")

    async def _run_backlog_check(self):
        """Run Backlog check via slack_backlog_monitor (backlog portion)."""
        log.debug("Running Backlog check...")
        success = await self.run_guardian_script("slack_backlog_monitor.py", timeout=60)
        if success:
            log.info("Backlog check completed")

    # ------------------------------------------------------------------
    # Slack polling
    # ------------------------------------------------------------------

    def _load_slack_state(self):
        """Load last Slack poll timestamp from state file."""
        if self._slack_state_file.exists():
            try:
                state = json.loads(self._slack_state_file.read_text(encoding="utf-8"))
                self._slack_last_ts = state.get("last_ts", "")
            except Exception:
                pass

    def _save_slack_state(self):
        """Save Slack poll timestamp."""
        try:
            self._slack_state_file.write_text(
                json.dumps({"last_ts": self._slack_last_ts, "updated": datetime.now().isoformat()}),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning(f"Failed to save Slack state: {e}")

    def _clean_slack_text(self, text: str) -> str:
        """Replace Slack user IDs with display names and clean markup."""
        for uid, name in self.SLACK_USER_MAP.items():
            text = text.replace(f"<@{uid}>", f"@{name}")
        # Clean URL markup: <https://url|label> → url
        text = re.sub(r"<(https?://[^|>]+)\|[^>]+>", r"\1", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        # Remove remaining angle bracket markup
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    def _resolve_author(self, msg: dict) -> str:
        """Extract author name from Slack message."""
        user_id = msg.get("user", "")
        if user_id in self.SLACK_USER_MAP:
            return self.SLACK_USER_MAP[user_id]
        return msg.get("username", msg.get("user", "不明"))

    async def _poll_slack(self):
        """Poll Slack agent-thread channel for new messages."""
        log.info(f"Slack polling started (interval={self.config.interval_slack}s, channel={self.config.slack_agent_thread_channel})")
        # Initial delay to let other systems stabilize
        await asyncio.sleep(10)

        while self._running:
            try:
                await self._poll_slack_once()
            except Exception as e:
                log.warning(f"Slack poll error: {e}")

            await asyncio.sleep(self.config.interval_slack)

    async def _poll_slack_once(self):
        """Single Slack poll cycle: fetch new messages and emit observations."""
        headers = {"Authorization": f"Bearer {self.config.slack_bot_token}"}
        channel = self.config.slack_agent_thread_channel

        # Fetch channel history
        params = {
            "channel": channel,
            "limit": 20,
        }
        if self._slack_last_ts:
            params["oldest"] = self._slack_last_ts

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://slack.com/api/conversations.history",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    log.warning(f"Slack API HTTP {resp.status}")
                    return

                data = await resp.json()
                if not data.get("ok"):
                    log.warning(f"Slack API error: {data.get('error', 'unknown')}")
                    return

        messages = data.get("messages", [])
        if not messages:
            return

        # Update timestamp for next poll (newest message)
        newest_ts = max(m.get("ts", "0") for m in messages)
        if newest_ts > self._slack_last_ts:
            self._slack_last_ts = newest_ts
            self._save_slack_state()

        # Filter out bot messages and old messages
        new_messages = []
        for msg in messages:
            # Skip bot messages and own messages
            if msg.get("bot_id") or msg.get("user") == self.TAKUTO_USER_ID:
                continue
            # Skip subtypes like channel_join, etc.
            if msg.get("subtype"):
                continue

            text = self._clean_slack_text(msg.get("text", ""))
            if not text or len(text) < 3:
                continue

            author = self._resolve_author(msg)
            new_messages.append({
                "text": text,
                "author": author,
                "ts": msg.get("ts", ""),
                "source": "slack",
                "channel": channel,
            })

        if not new_messages:
            return

        log.info(f"Slack: {len(new_messages)} new messages in agent-thread")

        # Also poll for mentions (search.messages)
        mention_messages = await self._poll_slack_mentions(headers)
        all_messages = new_messages + mention_messages

        # Emit each message as an observation
        for msg in all_messages:
            await self._emit(Observation(
                source="slack",
                event_type="new_message",
                data=msg,
                requires_llm=True,  # Default: let Filter decide with rules first
            ))

    async def _poll_slack_mentions(self, headers: dict) -> list[dict]:
        """Search for recent mentions of takuto in Slack."""
        params = {
            "query": f"<@{self.TAKUTO_USER_ID}> -from:me",
            "count": 5,
            "sort": "timestamp",
            "sort_dir": "desc",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://slack.com/api/search.messages",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    if not data.get("ok"):
                        return []

            matches = data.get("messages", {}).get("matches", [])
            results = []
            for match in matches:
                ts = str(match.get("ts", "0"))
                # Only include messages newer than last poll
                if self._slack_last_ts and ts <= self._slack_last_ts:
                    continue

                text = self._clean_slack_text(match.get("text", ""))
                if not text:
                    continue

                author = match.get("username", "不明")
                channel_name = match.get("channel", {}).get("name", "")
                results.append({
                    "text": text,
                    "author": author,
                    "ts": ts,
                    "source": "slack",
                    "channel": channel_name,
                    "is_mention": True,
                })

            if results:
                log.info(f"Slack: {len(results)} new mentions")
            return results

        except Exception as e:
            log.debug(f"Slack mention search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _emit(self, obs: Observation):
        """Put observation into the queue."""
        await self._observation_queue.put(obs)

    async def run_guardian_script(self, script_name: str, timeout: int = 60):
        """Run a guardian script as subprocess."""
        script = self.config.guardian_dir / script_name
        if not script.exists():
            log.warning(f"Guardian script not found: {script}")
            return False
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-u", str(script),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.config.canon_dir),
                env=env,
            )
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            if proc.returncode != 0 and proc.stderr:
                err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
                log.warning(f"{script_name} exit {proc.returncode}: {err[:200]}")
            return proc.returncode == 0
        except asyncio.TimeoutError:
            log.warning(f"{script_name} timed out after {timeout}s")
            return False
        except Exception as e:
            log.warning(f"{script_name} failed: {e}")
            return False

    async def refresh_with_sync(self):
        """Run state-tech updater + cross-source sync, then scan tasks."""
        for script_name in ("state_tech_auto_updater.py", "cross_source_sync.py"):
            await self.run_guardian_script(script_name)
        return self.scan_tasks()


# ======================================================================
# Utility functions (migrated from simple_chat.py, made standalone)
# ======================================================================

def _infer_project(title: str) -> str:
    if not title or not title.strip():
        return "その他"
    m = re.match(r"^([^-・_\s]+)", title.strip())
    return m.group(1) if m else title.strip()[:20] or "その他"


def _read_frontmatter(task_path: Path) -> dict:
    try:
        text = task_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    meta = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            meta[key] = value
    return meta


def _extract_task_context(task_path: Path, marker_dir: Path) -> tuple[str, str]:
    context = ""
    last_run = ""
    try:
        text = task_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return context, last_run

    body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)
    body = re.sub(r"^#\s+.*\n?", "", body, count=1).strip()

    for section_header in ["## Next Action", "## 目的", "## 状態", "## Canon 実行"]:
        match = re.search(re.escape(section_header) + r"\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
        if match:
            lines = [l.strip().lstrip("-").strip() for l in match.group(1).strip().splitlines() if l.strip()]
            context = lines[0][:80] if lines else ""
            break

    if not context:
        for line in body.splitlines():
            line = line.strip().lstrip("-").strip()
            if line and not line.startswith("#") and not line.startswith("|") and not line.startswith(">"):
                context = line[:80]
                break

    stem = task_path.stem
    for suffix, label in [(".failed.txt", "失敗"), (".txt", "成功")]:
        marker = marker_dir / f"{stem}{suffix}"
        if marker.exists():
            try:
                mtime = marker.stat().st_mtime
                last_run = f"{label} {datetime.fromtimestamp(mtime).strftime('%m/%d %H:%M')}"
            except Exception:
                last_run = label
            break

    return context, last_run


def _extract_task_priority(title: str, meta: dict) -> tuple[int, str]:
    numeric_keys = ("eval_priority", "evaluation_priority", "sort_order", "order", "rank")
    for key in numeric_keys:
        raw = meta.get(key)
        if raw is not None:
            try:
                val = int(str(raw).strip())
                return val, f"#{val}"
            except Exception:
                pass

    raw_priority = str(meta.get("priority", "")).strip().lower()
    priority_map = {
        "s": (0, "S"), "p0": (0, "P0"), "critical": (0, "Critical"),
        "urgent": (0, "Urgent"), "最高": (0, "最高"), "緊急": (0, "緊急"),
        "a": (1, "A"), "p1": (1, "P1"), "high": (1, "High"), "高": (1, "高"),
        "b": (2, "B"), "p2": (2, "P2"), "medium": (2, "Medium"),
        "med": (2, "Medium"), "normal": (2, "Normal"), "中": (2, "中"),
        "c": (3, "C"), "p3": (3, "P3"), "low": (3, "Low"), "低": (3, "低"),
        "d": (4, "D"), "backlog": (4, "Backlog"), "later": (4, "Later"), "後回し": (4, "後回し"),
    }
    if raw_priority in priority_map:
        return priority_map[raw_priority]

    title_patterns = [
        (r"^[\[\(【]?(P0|S)[\]\)】:_\-\s]", (0, "P0")),
        (r"^[\[\(【]?(P1|A)[\]\)】:_\-\s]", (1, "P1")),
        (r"^[\[\(【]?(P2|B)[\]\)】:_\-\s]", (2, "P2")),
        (r"^[\[\(【]?(P3|C)[\]\)】:_\-\s]", (3, "P3")),
    ]
    for pattern, normalized in title_patterns:
        if re.match(pattern, title, re.IGNORECASE):
            return normalized

    return 999, ""


def _extract_failure_reason(task_stem: str, canon_dir: Path) -> str:
    error_log = canon_dir / "logs" / "canon_run_errors.log"
    if not error_log.exists():
        return ""
    try:
        raw = error_log.read_bytes()
    except Exception:
        return ""
    text = raw.decode("utf-8", errors="replace")
    blocks = list(re.finditer(
        r"---\s+\d{4}-\d{2}-\d{2}T[\d:.]+\s+task=.*?---\s*\n(.*?)(?=\n---|\Z)",
        text, re.DOTALL
    ))
    if not blocks:
        return ""
    last_block = blocks[-1].group(1).strip()
    for line in last_block.splitlines():
        line = line.strip()
        if not line or len(line) < 5:
            continue
        for kw in ["Error", "Exception", "Failed", "Connection", "Timeout", "refused", "Caused by"]:
            if kw in line:
                clean = re.sub(r"object at 0x[0-9a-fA-F]+", "", line)
                clean = re.sub(r"[^\x20-\x7e\u3000-\u9fff\uff00-\uffef]", "", clean)
                return clean[:150]
    first_line = last_block.splitlines()[0].strip() if last_block else ""
    clean = re.sub(r"[^\x20-\x7e\u3000-\u9fff\uff00-\uffef]", "", first_line)
    return clean[:150] if len(clean) > 5 else ""


def _extract_my_actions(meeting_text: str) -> list:
    actions = []
    table_rows = re.findall(r"\|(.+?)\|(.+?)\|(.+?)\|", meeting_text)
    for row in table_rows:
        cols = [c.strip() for c in row]
        if len(cols) >= 2:
            assignee = cols[0]
            if "風岡" in assignee or "全員" in assignee or "共有" in assignee:
                action_text = cols[1].strip().lstrip("*").rstrip("*").strip()
                if action_text and action_text != "アクション（何をすることか）" and not action_text.startswith("---"):
                    deadline = cols[2].strip() if len(cols) >= 3 else ""
                    actions.append({"action": action_text, "deadline": deadline})
    return actions


def _scan_proactive_items(canon_dir: Path) -> list:
    """Scan for proactive items (meetings, follow-ups)."""
    items = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Today's meetings
    meetings_dirs = [
        canon_dir.parent / "Spec-driven-miraie" / "docs" / "organization" / "meetings",
    ]
    for mdir in meetings_dirs:
        if not mdir.exists():
            continue
        for f in mdir.glob(f"*{today_str}*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            head = text[:2500]
            if any(marker in head for marker in ["**完了**", "（完了）", "完了**"]):
                if "✅" in head and "完了" in head:
                    continue
                if "**完了**" in head or "完了**" in head or "（完了）" in head:
                    continue

            title_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
            title = title_match.group(1).strip()[:60] if title_match else f.stem
            time_match = re.search(r"(\d{1,2}:\d{2})", title)
            time_str = time_match.group(1) if time_match else ""

            items.append({
                "id": f"proactive-meeting-{f.stem}",
                "title": title,
                "category": "proactive",
                "is_work": True,
                "folder": "proactive",
                "cli_executed": False, "cli_failed": False, "evaluated": False,
                "project": "", "priority_rank": 0, "priority_label": "",
                "context": f"今日の会議 {time_str}".strip(),
                "last_run": "", "action_hint": "アジェンダ確認",
                "lane": "your_turn", "is_internal": False, "proactive_type": "meeting",
            })

            for i, action in enumerate(_extract_my_actions(text)):
                items.append({
                    "id": f"proactive-action-{f.stem}-{i}",
                    "title": action["action"][:60],
                    "category": "proactive",
                    "is_work": True,
                    "folder": "proactive",
                    "cli_executed": False, "cli_failed": False, "evaluated": False,
                    "project": "", "priority_rank": 1, "priority_label": "",
                    "context": action.get("deadline", ""),
                    "last_run": "", "action_hint": "あなたの宿題",
                    "lane": "your_turn", "is_internal": False, "proactive_type": "action",
                })

    # Follow-up items (待ち状態)
    gtd_work = canon_dir / ".agent" / "gtd" / "work" / "next-actions"
    if gtd_work.exists():
        wait_patterns = ["確認待ち", "依頼中", "依頼済", "待ち"]
        seen_prefixes = set()
        for f in sorted(gtd_work.glob("*.md")):
            if f.name in ("README.md", "INDEX.md"):
                continue
            if f.name.startswith("infer_") or f.name.startswith("auto_"):
                continue
            stem = f.stem.replace("【実行中】", "").replace("【要整理】", "").strip()
            if stem == "INDEX":
                continue
            prefix = stem[:20]
            if prefix in seen_prefixes:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat in wait_patterns:
                if pat in text:
                    ctx_line = ""
                    for line in text.splitlines():
                        if pat in line:
                            ctx_line = line.strip().lstrip("-").strip()[:80]
                            break
                    seen_prefixes.add(prefix)
                    items.append({
                        "id": f"proactive-wait-{f.stem}",
                        "title": stem,
                        "category": "proactive",
                        "is_work": True,
                        "folder": "proactive",
                        "cli_executed": False, "cli_failed": False, "evaluated": False,
                        "project": "", "priority_rank": 50, "priority_label": "",
                        "context": ctx_line or f"{pat}状態",
                        "last_run": "", "action_hint": "フォローアップ確認",
                        "lane": "your_turn", "is_internal": False, "proactive_type": "followup",
                    })
                    break

    return items
