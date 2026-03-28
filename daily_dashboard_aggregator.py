"""
ADR-0192: CanonGate Daily Dashboard — カレンダー + タスクの統合タイムラインビュー
Phase 1: ICS ベース + GTD ファイル監視 → 統合タイムライン → WebSocket broadcast
"""

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from google_calendar_notifier import GoogleCalendarNotifier


BroadcastCallback = Callable[[dict], Awaitable[None]]


@dataclass
class TimelineEntry:
    type: str           # "calendar" | "task" | "free_slot"
    start: str          # "HH:MM" or "" for unscheduled tasks
    end: str            # "HH:MM" or ""
    title: str
    priority_rank: int  # 0=highest, 999=lowest; calendar=0, free_slot=999
    priority_label: str
    status: str         # "scheduled" | "pending" | "running" | "free" | "done"
    source: str         # "ics" | "gtd" | "computed"
    metadata: dict = field(default_factory=dict)


class DailyDashboardAggregator:
    def __init__(
        self,
        calendar_notifier: GoogleCalendarNotifier,
        canon_base_dir: Path,
        logger,
        broadcast_callback: BroadcastCallback,
        work_start: str = "09:00",
        work_end: str = "20:00",
        task_check_seconds: int = 5,
        state_check_seconds: int = 30,
    ):
        self.notifier = calendar_notifier
        self.base_dir = Path(canon_base_dir)
        self.log = logger
        self.broadcast = broadcast_callback
        self.work_start = work_start
        self.work_end = work_end
        self.task_check_seconds = task_check_seconds
        self.state_check_seconds = state_check_seconds

        self._last_task_mtimes: dict[str, float] = {}
        self._last_state_mtime: float = 0
        self._last_ics_hash: str = ""
        self._cached_timeline: Optional[dict] = None

    async def run(self):
        if not self.notifier.ics_url:
            self.log.info("DailyDashboard: ICS URL not configured; calendar will be empty.")

        self.log.info(
            "DailyDashboard started (task_check=%ss, state_check=%ss, work=%s-%s)",
            self.task_check_seconds,
            self.state_check_seconds,
            self.work_start,
            self.work_end,
        )

        # Initial build
        await self._rebuild_and_broadcast()

        tick = 0
        while True:
            await asyncio.sleep(1)
            tick += 1

            changed = False

            # Check task files every N seconds
            if tick % self.task_check_seconds == 0:
                if self._tasks_changed():
                    changed = True

            # Check state-tech every N seconds
            if tick % self.state_check_seconds == 0:
                if self._state_changed():
                    changed = True

            # Check ICS every poll cycle (reuse notifier's poll_seconds)
            if tick % self.notifier.poll_seconds == 0:
                if await self._ics_changed():
                    changed = True

            if changed:
                await self._rebuild_and_broadcast()

    async def refresh(self):
        """On-demand refresh triggered by UI."""
        await self._rebuild_and_broadcast()

    # ──────────────────────────────────────────────
    # Change detection
    # ──────────────────────────────────────────────

    def _tasks_changed(self) -> bool:
        task_dirs = self._get_task_dirs()
        current_mtimes = {}
        for d in task_dirs:
            if not d.exists():
                continue
            for f in d.glob("*.md"):
                if f.name.startswith("README"):
                    continue
                current_mtimes[str(f)] = f.stat().st_mtime

        if current_mtimes != self._last_task_mtimes:
            self._last_task_mtimes = current_mtimes
            return True
        return False

    def _state_changed(self) -> bool:
        state_file = self.base_dir / ".agent" / "brain" / "state-tech.md"
        if not state_file.exists():
            return False
        mtime = state_file.stat().st_mtime
        if mtime != self._last_state_mtime:
            self._last_state_mtime = mtime
            return True
        return False

    async def _ics_changed(self) -> bool:
        if not self.notifier.ics_url:
            return False
        try:
            ics_text = await asyncio.to_thread(self.notifier._fetch_ics)
            ics_hash = str(hash(ics_text))
            if ics_hash != self._last_ics_hash:
                self._last_ics_hash = ics_hash
                self._cached_ics_text = ics_text
                return True
        except Exception as e:
            self.log.warning(f"DailyDashboard ICS fetch error: {e}")
        return False

    # ──────────────────────────────────────────────
    # Data extraction
    # ──────────────────────────────────────────────

    def _get_task_dirs(self) -> list[Path]:
        gtd = self.base_dir / ".agent" / "gtd"
        return [
            gtd / "work" / "next-actions",
            gtd / "work" / "evaluating",
        ]

    def _get_today_events(self) -> list[TimelineEntry]:
        ics_text = getattr(self, "_cached_ics_text", "")
        if not ics_text and self.notifier.ics_url:
            try:
                ics_text = self.notifier._fetch_ics()
                self._cached_ics_text = ics_text
            except Exception:
                return []

        if not ics_text:
            return []

        now = datetime.now(self.notifier.tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        entries = []
        for event in self.notifier._parse_ics(ics_text):
            if event.all_day:
                continue
            if event.status.upper() == "CANCELLED":
                continue

            start = event.start.astimezone(self.notifier.tz)

            # Handle recurring events (RRULE) - check if today matches
            if not (today_start <= start < today_end):
                # For recurring events parsed from ICS, check day-of-week match
                # The ICS parser returns raw DTSTART, so recurring events from past
                # won't have today's date. We need to check RRULE separately.
                continue

            end_str = ""
            # Try to infer 30-min default duration
            end_time = start + timedelta(minutes=30)
            end_str = f"{end_time:%H:%M}"

            summary = (event.summary or "予定").replace("\\,", ",").replace("\\n", " ")

            entries.append(TimelineEntry(
                type="calendar",
                start=f"{start:%H:%M}",
                end=end_str,
                title=summary,
                priority_rank=0,
                priority_label="",
                status="scheduled",
                source="ics",
                metadata={"uid": event.uid},
            ))

        entries.sort(key=lambda e: e.start)
        return entries

    def _get_today_events_with_rrule(self) -> list[TimelineEntry]:
        """Enhanced ICS parsing that expands RRULE for today."""
        ics_text = getattr(self, "_cached_ics_text", "")
        if not ics_text and self.notifier.ics_url:
            try:
                ics_text = self.notifier._fetch_ics()
                self._cached_ics_text = ics_text
            except Exception:
                return []

        if not ics_text:
            return []

        now = datetime.now(self.notifier.tz)
        today = now.date()
        today_weekday = today.strftime("%a").upper()[:2]  # MO, TU, WE, TH, FR, SA, SU

        entries = []
        lines = self.notifier._unfold_lines(ics_text)
        current = None
        current_rrule = None

        for line in lines:
            if line == "BEGIN:VEVENT":
                current = {}
                current_rrule = None
                continue
            if line == "END:VEVENT":
                if current:
                    entry = self._process_vevent_for_today(current, current_rrule, today, today_weekday)
                    if entry:
                        entries.append(entry)
                current = None
                current_rrule = None
                continue
            if current is None or ":" not in line:
                continue

            raw_key, value = line.split(":", 1)
            parts = raw_key.split(";")
            key = parts[0].upper()

            if key == "RRULE":
                current_rrule = value
            else:
                params = {}
                for part in parts[1:]:
                    if "=" in part:
                        p_key, p_val = part.split("=", 1)
                        params[p_key.upper()] = p_val
                current[key] = (value, params)

        # Deduplicate by (start, title)
        seen = set()
        unique = []
        for e in entries:
            key = (e.start, e.end, e.title)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        unique.sort(key=lambda e: e.start)
        return unique

    def _process_vevent_for_today(self, raw: dict, rrule: Optional[str], today, today_weekday) -> Optional[TimelineEntry]:
        if "DTSTART" not in raw:
            return None

        start_value, start_params = raw["DTSTART"]
        start_dt, all_day = self.notifier._parse_datetime(start_value, start_params)
        if start_dt is None or all_day:
            return None

        status_val = raw.get("STATUS", ("", {}))[0] or ""
        if status_val.upper() == "CANCELLED":
            return None

        start_local = start_dt.astimezone(self.notifier.tz)
        event_date = start_local.date()

        is_today = False

        if event_date == today:
            is_today = True
        elif rrule:
            is_today = self._rrule_matches_today(rrule, start_local, today, today_weekday)

        if not is_today:
            return None

        # Calculate end time
        end_str = ""
        if "DTEND" in raw:
            end_value, end_params = raw["DTEND"]
            end_dt, _ = self.notifier._parse_datetime(end_value, end_params)
            if end_dt:
                end_local = end_dt.astimezone(self.notifier.tz)
                # For recurring events, use original time but today's date
                if event_date != today:
                    end_str = f"{end_local:%H:%M}"
                else:
                    end_str = f"{end_local:%H:%M}"
        if not end_str:
            end_time = start_local + timedelta(minutes=30)
            end_str = f"{end_time:%H:%M}"

        summary = (raw.get("SUMMARY", ("予定", {}))[0] or "予定").replace("\\,", ",").replace("\\n", " ")
        uid = raw.get("UID", ("", {}))[0] or f"event-{start_value}"

        return TimelineEntry(
            type="calendar",
            start=f"{start_local:%H:%M}",
            end=end_str,
            title=summary,
            priority_rank=0,
            priority_label="",
            status="scheduled",
            source="ics",
            metadata={"uid": uid},
        )

    def _rrule_matches_today(self, rrule: str, original_start: datetime, today, today_weekday: str) -> bool:
        """Simple RRULE matching for WEEKLY frequency with BYDAY."""
        parts = {}
        for segment in rrule.split(";"):
            if "=" in segment:
                k, v = segment.split("=", 1)
                parts[k.upper()] = v

        freq = parts.get("FREQ", "")

        # Check UNTIL - if the rule has expired, skip
        until = parts.get("UNTIL", "")
        if until:
            try:
                if until.endswith("Z"):
                    until_dt = datetime.strptime(until, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                else:
                    until_dt = datetime.strptime(until, "%Y%m%dT%H%M%S").replace(tzinfo=self.notifier.tz)
                if until_dt.date() < today:
                    return False
            except ValueError:
                pass

        if freq == "WEEKLY":
            byday = parts.get("BYDAY", "")
            if byday:
                days = [d.strip() for d in byday.split(",")]
                return today_weekday in days
            # No BYDAY = same day of week as original
            return original_start.strftime("%a").upper()[:2] == today_weekday

        if freq == "DAILY":
            return True

        if freq == "MONTHLY":
            byday = parts.get("BYDAY", "")
            if byday:
                # e.g., "1MO" = first Monday
                # Simple: check if today is the right weekday
                for d in byday.split(","):
                    d = d.strip()
                    if d.endswith(today_weekday):
                        return True
                return False
            # BYMONTHDAY
            bymonthday = parts.get("BYMONTHDAY", "")
            if bymonthday:
                return str(today.day) in bymonthday.split(",")
            return original_start.day == today.day

        return False

    def _get_tasks(self) -> list[TimelineEntry]:
        entries = []
        for d in self._get_task_dirs():
            if not d.exists():
                continue
            for f in sorted(d.glob("*.md")):
                if f.name.startswith("README") or f.name.startswith("【実行中】INDEX"):
                    continue
                entry = self._parse_task_file(f)
                if entry:
                    entries.append(entry)

        entries.sort(key=lambda e: e.priority_rank)
        return entries

    def _parse_task_file(self, path: Path) -> Optional[TimelineEntry]:
        title = path.stem
        is_running = title.startswith("【実行中】")
        title = title.replace("【実行中】", "").replace("【要整理】", "")

        # Read frontmatter for priority
        priority_label = ""
        canon_executable = False
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            fm = self._read_frontmatter(text)
            if fm.get("canon_executable"):
                canon_executable = True
            p = fm.get("priority", "")
            if p == "urgent":
                priority_label = "🔴"
            elif p == "this_week":
                priority_label = "🟡"
            else:
                priority_label = ""
        except Exception:
            text = ""
            fm = {}

        # Determine priority rank
        priority_rank = 50
        p = fm.get("priority", "")
        if p == "urgent":
            priority_rank = 10
        elif p == "this_week":
            priority_rank = 20
        elif p == "low":
            priority_rank = 80

        status = "running" if is_running else "pending"
        folder = path.parent.name

        return TimelineEntry(
            type="task",
            start="",
            end="",
            title=title,
            priority_rank=priority_rank,
            priority_label=priority_label,
            status=status,
            source="gtd",
            metadata={
                "file": path.name,
                "folder": folder,
                "canon_executable": canon_executable,
            },
        )

    def _read_frontmatter(self, text: str) -> dict:
        if not text.startswith("---"):
            return {}
        end = text.find("---", 3)
        if end == -1:
            return {}
        fm_text = text[3:end].strip()
        result = {}
        for line in fm_text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v.lower() in ("true", "yes"):
                    v = True
                elif v.lower() in ("false", "no"):
                    v = False
                result[k] = v
        return result

    # ──────────────────────────────────────────────
    # Free slot computation
    # ──────────────────────────────────────────────

    def _compute_free_slots(self, calendar_events: list[TimelineEntry]) -> list[TimelineEntry]:
        def to_minutes(hhmm: str) -> int:
            h, m = hhmm.split(":")
            return int(h) * 60 + int(m)

        def from_minutes(mins: int) -> str:
            return f"{mins // 60:02d}:{mins % 60:02d}"

        work_start = to_minutes(self.work_start)
        work_end = to_minutes(self.work_end)

        # Build occupied intervals from calendar events
        occupied = []
        for ev in calendar_events:
            if ev.start and ev.end:
                s = to_minutes(ev.start)
                e = to_minutes(ev.end)
                if s < e:
                    occupied.append((s, e))

        occupied.sort()

        # Merge overlapping intervals
        merged = []
        for s, e in occupied:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        # Find gaps
        slots = []
        cursor = work_start
        for s, e in merged:
            if s > cursor:
                duration = s - cursor
                if duration >= 15:  # Minimum 15-min slot
                    slots.append(TimelineEntry(
                        type="free_slot",
                        start=from_minutes(cursor),
                        end=from_minutes(s),
                        title=f"空きスロット（{duration}分）",
                        priority_rank=999,
                        priority_label="",
                        status="free",
                        source="computed",
                    ))
            cursor = max(cursor, e)

        if cursor < work_end:
            duration = work_end - cursor
            if duration >= 15:
                slots.append(TimelineEntry(
                    type="free_slot",
                    start=from_minutes(cursor),
                    end=from_minutes(work_end),
                    title=f"空きスロット（{duration}分）",
                    priority_rank=999,
                    priority_label="",
                    status="free",
                    source="computed",
                ))

        return slots

    # ──────────────────────────────────────────────
    # Timeline construction & broadcast
    # ──────────────────────────────────────────────

    def _build_today_plan(self, tasks: list[TimelineEntry], free_slots: list[TimelineEntry],
                          calendar_events: list[TimelineEntry], now_hhmm: str) -> dict:
        """今日やるべきことを整理して提案する。空きスロットにタスクを配置。"""

        # 1. 今日の優先タスクTOP3（urgent > this_week > その他）
        actionable = [t for t in tasks if t.status != "running"
                      and not t.metadata.get("canon_executable")]
        top3 = actionable[:3]

        # 2. 空きスロットにタスクを仮配置
        slot_assignments = []
        task_idx = 0
        for slot in free_slots:
            if slot.start < now_hhmm:
                continue  # 過去のスロットはスキップ
            duration = self._slot_duration(slot)
            if duration < 15:
                continue
            if task_idx < len(actionable):
                task = actionable[task_idx]
                slot_assignments.append({
                    "slot_start": slot.start,
                    "slot_end": slot.end,
                    "slot_minutes": duration,
                    "suggested_task": task.title,
                    "task_priority": task.priority_label,
                })
                task_idx += 1

        # 3. 会議前の準備タスク提案
        meeting_prep = []
        for ev in calendar_events:
            if ev.start > now_hhmm:
                # 会議名からキーワード抽出して関連タスクを探す
                related = [t for t in tasks
                          if any(kw in t.title for kw in ev.title.split()
                                if len(kw) >= 2)]
                if related:
                    meeting_prep.append({
                        "meeting": ev.title,
                        "meeting_time": ev.start,
                        "prep_tasks": [t.title for t in related[:2]],
                    })

        # 4. ブロッカー検出
        blockers = [t for t in tasks if "待ち" in t.title or "ブロック" in t.title
                    or "回答待ち" in t.title]

        # 5. 朝のブリーフィング文
        remaining_events = [e for e in calendar_events if e.start > now_hhmm]
        total_free = sum(self._slot_duration(s) for s in free_slots if s.start > now_hhmm)
        briefing = (
            f"今日は会議{len(remaining_events)}件、"
            f"空き時間{total_free}分、"
            f"優先タスク{len(top3)}件。"
        )
        if blockers:
            briefing += f" ブロッカー{len(blockers)}件あり。"
        if slot_assignments:
            briefing += f" 最初の空きは{slot_assignments[0]['slot_start']}から。"

        return {
            "top3_tasks": [{"title": t.title, "priority": t.priority_label} for t in top3],
            "slot_assignments": slot_assignments,
            "meeting_prep": meeting_prep,
            "blockers": [{"title": b.title} for b in blockers],
            "briefing": briefing,
        }

    async def _rebuild_and_broadcast(self):
        try:
            # Use enhanced RRULE-aware parser
            calendar_events = self._get_today_events_with_rrule()
            tasks = self._get_tasks()
            free_slots = self._compute_free_slots(calendar_events)

            # Build timeline: calendar (time-sorted) + free slots interleaved
            timeline = []
            cal_and_free = sorted(
                calendar_events + free_slots,
                key=lambda e: e.start if e.start else "99:99",
            )
            timeline.extend(cal_and_free)

            # Summary
            now = datetime.now(self.notifier.tz)
            now_hhmm = f"{now:%H:%M}"
            total_free = sum(
                self._slot_duration(s) for s in free_slots
            )

            next_event = None
            for ev in calendar_events:
                if ev.start > now_hhmm:
                    mins_until = self._minutes_between(now_hhmm, ev.start)
                    next_event = {
                        "title": ev.title,
                        "start": ev.start,
                        "minutes_until": mins_until,
                    }
                    break

            # 今日のプラン生成
            today_plan = self._build_today_plan(tasks, free_slots, calendar_events, now_hhmm)

            message = {
                "type": "daily_timeline",
                "date": now.strftime("%Y-%m-%d"),
                "now": now_hhmm,
                "timeline": [asdict(e) for e in timeline],
                "tasks": [asdict(t) for t in tasks],
                "today_plan": today_plan,
                "summary": {
                    "total_events": len(calendar_events),
                    "total_tasks": len(tasks),
                    "free_minutes": total_free,
                    "next_event": next_event,
                    "briefing": today_plan["briefing"],
                },
            }

            self._cached_timeline = message
            await self.broadcast(message)
            self.log.debug(
                f"DailyDashboard broadcast: {len(calendar_events)} events, "
                f"{len(tasks)} tasks, {len(free_slots)} free slots, "
                f"plan: {len(today_plan['top3_tasks'])} top tasks"
            )

        except Exception as e:
            self.log.error(f"DailyDashboard rebuild failed: {e}", exc_info=True)

    def _slot_duration(self, slot: TimelineEntry) -> int:
        if not slot.start or not slot.end:
            return 0
        return self._minutes_between(slot.start, slot.end)

    def _minutes_between(self, start_hhmm: str, end_hhmm: str) -> int:
        sh, sm = start_hhmm.split(":")
        eh, em = end_hhmm.split(":")
        return (int(eh) * 60 + int(em)) - (int(sh) * 60 + int(sm))
