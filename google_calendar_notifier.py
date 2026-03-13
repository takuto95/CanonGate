import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

import requests


NotifyCallback = Callable[[str, bool], Awaitable[None]]


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    start: datetime
    status: str = ""
    all_day: bool = False


class GoogleCalendarNotifier:
    def __init__(
        self,
        ics_url: str,
        cache_path: Path,
        logger,
        notify_minutes_before: int = 30,
        poll_seconds: int = 60,
        timezone_name: str = "Asia/Tokyo",
        voice: bool = True,
    ):
        self.ics_url = (ics_url or "").strip()
        self.cache_path = Path(cache_path)
        self.logger = logger
        self.notify_minutes_before = max(1, int(notify_minutes_before))
        self.poll_seconds = max(15, int(poll_seconds))
        self.tz = self._get_timezone(timezone_name)
        self.voice = bool(voice)
        self._notified = self._load_cache()

    async def run(self, notify_callback: NotifyCallback):
        if not self.ics_url:
            self.logger.info("Google Calendar notifier disabled: ICS URL is not configured.")
            return

        self.logger.info(
            "Google Calendar notifier started (poll=%ss, notify_before=%sm).",
            self.poll_seconds,
            self.notify_minutes_before,
        )

        while True:
            try:
                await self.poll_once(notify_callback)
            except Exception as e:
                self.logger.warning(f"Google Calendar notifier poll failed: {e}")
            await asyncio.sleep(self.poll_seconds)

    async def poll_once(self, notify_callback: NotifyCallback):
        ics_text = await asyncio.to_thread(self._fetch_ics)
        if not ics_text:
            return

        now = datetime.now(self.tz)
        window_start = now
        window_end = now + timedelta(minutes=self.notify_minutes_before)
        changed = False

        for event in self._parse_ics(ics_text):
            if event.all_day:
                continue
            if event.status.upper() == "CANCELLED":
                continue

            start = event.start.astimezone(self.tz)
            if not (window_start < start <= window_end):
                continue

            cache_key = self._cache_key(event)
            if cache_key in self._notified:
                continue

            message = self._build_message(event)
            await notify_callback(message, self.voice)
            self._notified[cache_key] = now.isoformat()
            changed = True

        if self._cleanup_cache(now):
            changed = True

        if changed:
            self._save_cache()

    def _fetch_ics(self) -> str:
        try:
            response = requests.get(self.ics_url, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.warning(f"Google Calendar ICS fetch failed: {type(e).__name__}")
            return ""

    def _parse_ics(self, ics_text: str) -> list[CalendarEvent]:
        lines = self._unfold_lines(ics_text)
        events = []
        current = None

        for line in lines:
            if line == "BEGIN:VEVENT":
                current = {}
                continue
            if line == "END:VEVENT":
                event = self._build_event(current or {})
                if event:
                    events.append(event)
                current = None
                continue
            if current is None or ":" not in line:
                continue

            raw_key, value = line.split(":", 1)
            parts = raw_key.split(";")
            key = parts[0].upper()
            params = {}
            for part in parts[1:]:
                if "=" in part:
                    p_key, p_val = part.split("=", 1)
                    params[p_key.upper()] = p_val
            current[key] = (value, params)

        return events

    def _build_event(self, raw: dict) -> Optional[CalendarEvent]:
        if "DTSTART" not in raw:
            return None

        start_value, start_params = raw["DTSTART"]
        start_dt, all_day = self._parse_datetime(start_value, start_params)
        if start_dt is None:
            return None

        uid = raw.get("UID", ("", {}))[0] or f"event-{start_value}"
        summary = raw.get("SUMMARY", ("予定", {}))[0] or "予定"
        status = raw.get("STATUS", ("", {}))[0] or ""
        return CalendarEvent(uid=uid, summary=summary, start=start_dt, status=status, all_day=all_day)

    def _parse_datetime(self, value: str, params: dict) -> tuple[Optional[datetime], bool]:
        if params.get("VALUE", "").upper() == "DATE":
            return None, True

        value = value.strip()
        tzid = params.get("TZID")

        formats = ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%dT%H%M")
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            return None, False

        if value.endswith("Z"):
            parsed = parsed.replace(tzinfo=timezone.utc)
        elif tzid:
            parsed = parsed.replace(tzinfo=self._get_timezone(tzid))
        else:
            parsed = parsed.replace(tzinfo=self.tz)

        return parsed, False

    def _build_message(self, event: CalendarEvent) -> str:
        start_local = event.start.astimezone(self.tz)
        summary = (event.summary or "予定").replace("\\,", ",").replace("\\n", " ")
        return f"{self.notify_minutes_before}分後に予定です。{start_local:%H:%M} から {summary}"

    def _cache_key(self, event: CalendarEvent) -> str:
        return f"{event.uid}|{event.start.astimezone(self.tz).isoformat()}"

    def _load_cache(self) -> dict[str, str]:
        try:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self._notified, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self.logger.warning(f"Google Calendar cache save failed: {e}")

    def _cleanup_cache(self, now: datetime) -> bool:
        changed = False
        cutoff = now - timedelta(days=7)
        keep = {}
        for key, notified_at in self._notified.items():
            try:
                notified_dt = datetime.fromisoformat(notified_at)
            except Exception:
                changed = True
                continue
            if notified_dt >= cutoff:
                keep[key] = notified_at
            else:
                changed = True
        self._notified = keep
        return changed

    def _unfold_lines(self, text: str) -> list[str]:
        unfolded = []
        for line in text.splitlines():
            if line.startswith((" ", "\t")) and unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line.strip())
        return unfolded

    def _get_timezone(self, timezone_name: str):
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(timezone_name)
        except Exception:
            if timezone_name == "Asia/Tokyo":
                return timezone(timedelta(hours=9))
            return timezone.utc
