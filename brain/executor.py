"""Executor - Local file operations for Canon Brain.

Writes analysis results, drafts, GTD updates, and events.
NEVER touches external APIs (no Slack, no Backlog, no GitHub).
"""

import json
import re
import logging
from datetime import datetime
from pathlib import Path

from brain.config import BrainConfig

log = logging.getLogger("canon-brain.executor")


class Executor:
    """Executes local-only actions based on Thinker decisions."""

    def __init__(self, config: BrainConfig):
        self.config = config
        # Ensure directories exist
        self._drafts_dir = config.brain_dir / "drafts"
        self._drafts_dir.mkdir(parents=True, exist_ok=True)
        self._reports_dir = config.brain_dir / "reports"
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._events_dir = config.brain_dir / "events"
        self._events_dir.mkdir(parents=True, exist_ok=True)

    async def create_draft(self, title: str, content: str) -> Path:
        """Save a draft document."""
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", title)[:60].strip() or "draft"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_name}.md"
        path = self._drafts_dir / filename
        path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
        log.info(f"Draft created: {path}")
        return path

    async def save_analysis(self, topic: str, analysis: str) -> Path | None:
        """Save an analysis report — with dedup + empty-content guards.

        2026-05-01: 1015件の brain_analysis_* 暴走対処 (planning/skill-logging-gap-diagnosis 参照)。
        - 内容ハッシュが直近24時間に存在 → スキップ
        - analysis が極端に短い (< 300 chars) → スキップ
        - approved=False で raw_response empty → 呼び出し側で抑制を期待
        """
        import hashlib

        # Empty/junk guard: 短すぎる出力は保存しない
        if not analysis or len(analysis.strip()) < 300:
            log.debug(f"Analysis skipped (too short, len={len(analysis or '')}): {topic[:40]}")
            return None

        # Dedup: 直近24時間に同一内容ハッシュが存在すればスキップ
        content_hash = hashlib.sha256(analysis.encode("utf-8")).hexdigest()[:16]
        hash_index_path = self._reports_dir / "_content_hash_index.txt"
        recent_hashes = set()
        if hash_index_path.exists():
            try:
                lines = hash_index_path.read_text(encoding="utf-8").strip().split("\n")
                # 直近1000ハッシュのみ保持
                recent_hashes = set(lines[-1000:])
            except Exception:
                pass

        if content_hash in recent_hashes:
            log.info(f"Analysis dedup'd (content seen recently): {topic[:40]} hash={content_hash}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r'[\\/:*?"<>|]', "_", topic)[:40].strip() or "analysis"
        filename = f"brain_analysis_{timestamp}_{safe_topic}.md"
        path = self._reports_dir / filename
        path.write_text(
            f"# Brain Analysis: {topic}\n\n"
            f"**Generated**: {datetime.now().isoformat()}\n"
            f"**Source**: Canon Brain autonomous analysis\n"
            f"**Content-Hash**: {content_hash}\n\n"
            f"{analysis}\n",
            encoding="utf-8",
        )
        # Append hash to index
        try:
            with open(hash_index_path, "a", encoding="utf-8") as f:
                f.write(content_hash + "\n")
        except Exception:
            pass

        log.info(f"Analysis saved: {path}")
        return path

    async def create_gtd_task(self, title: str, body: str = "", domain: str = "work") -> Path:
        """Create a new GTD task file."""
        safe_name = re.sub(r'[\\/:*?"<>|]', "_", title)[:80].strip() or "新規タスク"
        next_dir = self.config.gtd_dir / domain / "next-actions"
        next_dir.mkdir(parents=True, exist_ok=True)
        task_path = next_dir / f"{safe_name}.md"

        if task_path.exists():
            log.info(f"Task already exists: {task_path}")
            return task_path

        content = f"# {title}\n\n"
        if body:
            content += f"{body}\n"
        task_path.write_text(content, encoding="utf-8")
        log.info(f"GTD task created: {task_path}")
        return task_path

    async def create_adr(self, title: str, context: str = "") -> Path:
        """Create a new ADR file."""
        adr_dir = self.config.canon_dir / "docs" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)

        # Find next ADR number
        existing = sorted(adr_dir.glob("*.md"))
        max_num = 0
        for f in existing:
            m = re.match(r"(\d+)", f.name)
            if m:
                max_num = max(max_num, int(m.group(1)))
        next_num = max_num + 1

        slug = re.sub(r'[\\/:*?"<>|\s]+', "-", title)[:60].strip("-").lower()
        filename = f"{next_num:04d}-{slug}.md"
        adr_path = adr_dir / filename
        today = datetime.now().strftime("%Y-%m-%d")

        adr_path.write_text(
            f"# ADR-{next_num:04d}: {title}\n\n"
            f"**Date**: {today}\n"
            f"**Status**: Proposed\n"
            f"**Source**: Canon Brain autonomous capture\n\n"
            f"## Context\n\n{context or '(自動検出 — 詳細を追記してください)'}\n\n"
            f"## Decision\n\n{title}\n\n"
            f"## Consequences\n\n(TBD)\n",
            encoding="utf-8",
        )
        log.info(f"ADR created: {adr_path} (#{next_num})")
        return adr_path

    async def record_event(self, event_type: str, domain: str, payload: dict):
        """Append an event to the brain event log (JSONL)."""
        now = datetime.now()
        event = {
            "id": f"evt_{now.strftime('%Y%m%d_%H%M%S')}_{id(payload) % 0xFFFF:04x}",
            "timestamp": now.isoformat(),
            "type": event_type,
            "domain": domain,
            "source": "canon_brain",
            "payload": payload,
        }

        month_file = self._events_dir / f"{now.strftime('%Y-%m')}.jsonl"
        with open(month_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        log.debug(f"Event recorded: {event_type}")

    async def update_proactive_brief(self, brief_data: dict):
        """Update the proactive brief in active_context.md."""
        ctx_path = self.config.brain_dir / "current_state" / "active_context.md"
        if not ctx_path.exists():
            return

        try:
            text = ctx_path.read_text(encoding="utf-8")
            # Update the Proactive Brief section
            brief_text = "\n## Proactive Brief (latest)\n"
            for alert in brief_data.get("alerts", [])[:5]:
                urgency_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(alert.get("urgency", ""), "⚪")
                brief_text += f"- {urgency_emoji} {alert.get('text_preview', '')[:80]}\n"

            if "## Proactive Brief" in text:
                # Replace existing section
                start = text.index("## Proactive Brief")
                end = text.find("\n## ", start + 1)
                if end == -1:
                    end = len(text)
                text = text[:start] + brief_text.strip() + "\n" + text[end:]
            else:
                text += "\n" + brief_text

            ctx_path.write_text(text, encoding="utf-8")
            log.info("Proactive brief updated in active_context.md")
        except Exception as e:
            log.warning(f"Failed to update proactive brief: {e}")
