"""Filter - Rule-based + Ollama classification for observations.

Decides which observations need attention, at what urgency level,
and whether they should be routed to the Thinker for deep reasoning.
"""

import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp

from brain.config import BrainConfig
from brain.observer import Observation

log = logging.getLogger("canon-brain.filter")

# Customer names for urgency detection
CUSTOMER_NAMES = [
    "積水", "セキスイ", "住林", "住友林業", "住協",
    "みずほ", "アットホーム", "光島",
    "岸原", "吉安", "浅見", "石川",
]

# Deadline keywords
DEADLINE_KEYWORDS = [
    "期限", "deadline", "納期", "〆切", "締切", "急ぎ", "至急",
    "urgent", "ASAP", "今日中", "本日中", "明日まで",
    "まで", "締め切り", "必須",
]

# Blocker patterns (from proactive-scanner.py)
BLOCKER_PATTERNS = {
    "waiting": ["待ち", "待っています", "回答待ち", "確認待ち", "返答待ち"],
    "blocked": ["ブロック", "ブロッカー", "blocker", "blocked", "止まっている"],
    "confirmation_needed": ["確認いただけ", "ご確認", "確認お願い", "ご対応"],
    "status_inquiry": ["どのような状況", "進捗", "完了してますか", "いかがでしょう"],
}

# Action keywords (from proactive-scanner.py)
ACTION_KEYWORDS = ["お願い", "よろしく", "修正", "対応", "確認", "教えて", "どう", "いかが"]
QUESTION_MARKERS = ["?", "？", "ですか", "でしょうか"]

# Known important tags that bypass classification
HIGH_PRIORITY_TAGS = {"[URGENT]", "[SLACK]", "[BACKLOG]", "[GITHUB]", "[CALENDAR]"}


@dataclass
class FilteredItem:
    """An observation that passed through the filter."""
    source: str
    event_type: str
    urgency: str        # "critical", "high", "medium", "low", "info"
    action: str          # "notify", "think", "sync", "log"
    data: dict = field(default_factory=dict)
    reason: str = ""     # Why this urgency level
    timestamp: datetime = field(default_factory=datetime.now)


class Filter:
    """Classifies observations by urgency and action type.

    Stage 1: Rule-based (no LLM) — catches obvious patterns
    Stage 2: Ollama qwen3:4b (local) — classifies ambiguous items
    """

    def __init__(self, config: BrainConfig):
        self.config = config
        self._ollama_available: Optional[bool] = None
        # Deduplication: track recently emitted items
        self._recent_notifications: dict[str, float] = {}
        self._dedup_window_seconds = 300  # 5 min

    async def run(self, observation_queue, filtered_queue):
        """Main filter loop: read observations, classify, emit FilteredItems."""
        log.info("Filter started")
        while True:
            try:
                obs: Observation = await observation_queue.get()
                result = await self.classify(obs)
                if result:
                    if not self._is_duplicate(result):
                        await filtered_queue.put(result)
                    else:
                        log.debug(f"Deduplicated: {result.source}/{result.event_type}")
            except Exception as e:
                log.error(f"Filter error: {e}", exc_info=True)

    async def classify(self, obs: Observation) -> Optional[FilteredItem]:
        """Classify an observation. Returns None if should be dropped."""

        # Stage 1: Rule-based classification
        result = self._apply_rules(obs)
        if result is not None:
            return result

        # Stage 2: Ollama classification for ambiguous items
        if obs.requires_llm:
            return await self._classify_with_ollama(obs)

        # Default: log only
        return FilteredItem(
            source=obs.source,
            event_type=obs.event_type,
            urgency="info",
            action="log",
            data=obs.data,
            reason="no rule matched",
        )

    def _apply_rules(self, obs: Observation) -> Optional[FilteredItem]:
        """Pure rule-based classification. Returns None for ambiguous items."""

        # Hub alerts from report.log
        if obs.event_type == "hub_alert":
            tag = obs.data.get("tag", "")
            urgency = "high" if tag in HIGH_PRIORITY_TAGS else "medium"
            return FilteredItem(
                source=obs.source,
                event_type="hub_alert",
                urgency=urgency,
                action="notify",
                data=obs.data,
                reason=f"HUB tag: {tag}",
            )

        # Cross-source dashboard changes -> think (Backlog/ClickUp変化を先回り分析)
        if obs.event_type == "files_changed" and obs.source == "cross_source":
            return FilteredItem(
                source=obs.source,
                event_type="cross_source_change",
                urgency="medium",
                action="think",
                data=obs.data,
                reason="cross-source dashboard updated; analyze for proactive action",
            )

        # 既知タスクの状態変化 (sub_lane/status/due_date imminence) -> think
        if obs.event_type == "task_status_change":
            kinds = obs.data.get("change_kinds", [])
            # urgency: due_imminent or sub_laneがurgentに変化 -> high、その他 -> medium
            urg = "medium"
            if any(k.startswith("due_imminent") for k in kinds):
                urg = "high"
            elif any("→urgent" in k for k in kinds):
                urg = "high"
            return FilteredItem(
                source=obs.source,
                event_type="task_status_change",
                urgency=urg,
                action="think",
                data=obs.data,
                reason=f"task state change: {', '.join(kinds)[:100]}",
            )

        # 新規タスク検知 (ClickUp/Backlog/next-actions等から1件) -> think (個別段取り)
        if obs.event_type == "new_task":
            sub_lane = obs.data.get("sub_lane", "")
            due_date = obs.data.get("due_date")
            # urgency: urgent lane or 期限超過/今日 → high、それ以外 → medium
            urg = "medium"
            try:
                if sub_lane == "urgent":
                    urg = "high"
                elif due_date:
                    today = datetime.now().date().isoformat()
                    if str(due_date) <= today:
                        urg = "high"
            except Exception:
                pass
            return FilteredItem(
                source=obs.source,
                event_type="new_task",
                urgency=urg,
                action="think",
                data=obs.data,
                reason=f"new task detected (sub_lane={sub_lane}, due={due_date})",
            )

        # GTD file changes -> sync
        if obs.event_type == "files_changed":
            return FilteredItem(
                source=obs.source,
                event_type="task_sync",
                urgency="low",
                action="sync",
                data=obs.data,
                reason="GTD files changed",
            )

        # Periodic sync
        if obs.event_type == "periodic_sync":
            return FilteredItem(
                source=obs.source,
                event_type="task_sync",
                urgency="info",
                action="sync",
                data=obs.data,
                reason="periodic heartbeat",
            )

        # Task sync request
        if obs.event_type == "task_sync_requested":
            return FilteredItem(
                source=obs.source,
                event_type="task_sync",
                urgency="low",
                action="sync",
                data=obs.data,
                reason="explicit request",
            )

        # System report
        if obs.event_type == "system_report":
            return FilteredItem(
                source=obs.source,
                event_type="system_report",
                urgency="medium",
                action="notify",
                data=obs.data,
                reason="system report",
            )

        # Slack messages (Phase 4 - full proactive-scanner patterns)
        if obs.source == "slack" and obs.event_type == "new_message":
            text = obs.data.get("text", "")
            author = obs.data.get("author", "")
            is_mention = obs.data.get("is_mention", False)

            # Rule 1: customer name + deadline keyword -> critical (send to Thinker)
            has_customer = any(name in text or name in author for name in CUSTOMER_NAMES)
            has_deadline = any(kw in text for kw in DEADLINE_KEYWORDS)

            if has_customer and has_deadline:
                return FilteredItem(
                    source="slack", event_type="urgent_message",
                    urgency="critical", action="think",
                    data=obs.data, reason="customer + deadline detected",
                )

            # Rule 2: direct mention with action keyword -> think (返信案ドラフト)
            has_action = any(kw in text for kw in ACTION_KEYWORDS)
            has_question = any(kw in text for kw in QUESTION_MARKERS)

            if is_mention and (has_action or has_question):
                return FilteredItem(
                    source="slack", event_type="action_item",
                    urgency="high", action="think",
                    data=obs.data, reason="mention + action/question; draft response",
                )

            # Rule 3: blocker patterns -> high
            for blocker_type, patterns in BLOCKER_PATTERNS.items():
                if any(pat in text for pat in patterns):
                    return FilteredItem(
                        source="slack", event_type="blocker",
                        urgency="high", action="notify",
                        data={**obs.data, "blocker_type": blocker_type},
                        reason=f"blocker pattern: {blocker_type}",
                    )

            # Rule 4: customer name only -> think (顧客関連は先回り分析)
            if has_customer:
                return FilteredItem(
                    source="slack", event_type="customer_message",
                    urgency="medium", action="think",
                    data=obs.data, reason="customer name detected; proactive analysis",
                )

            # Rule 5: deadline keyword only -> high
            if has_deadline:
                return FilteredItem(
                    source="slack", event_type="deadline_mention",
                    urgency="high", action="notify",
                    data=obs.data, reason="deadline keyword detected",
                )

            # Rule 6: mention without action keyword -> medium
            if is_mention:
                return FilteredItem(
                    source="slack", event_type="mention",
                    urgency="medium", action="notify",
                    data=obs.data, reason="direct mention",
                )

            # Ambiguous: needs Ollama classification
            obs.requires_llm = True
            return None

        # Calendar events
        if obs.source == "calendar":
            return FilteredItem(
                source="calendar",
                event_type="calendar_event",
                urgency="high",
                action="notify",
                data=obs.data,
                reason="upcoming calendar event",
            )

        return None  # Unknown -> will get default handling

    async def _classify_with_ollama(self, obs: Observation) -> Optional[FilteredItem]:
        """Call Ollama qwen3:4b for lightweight classification."""
        if self._ollama_available is False:
            return FilteredItem(
                source=obs.source,
                event_type=obs.event_type,
                urgency="low",
                action="log",
                data=obs.data,
                reason="ollama unavailable, defaulting to low",
            )

        text = obs.data.get("text", str(obs.data))[:500]
        prompt = (
            "以下のメッセージを分類してください。JSON形式で回答:\n"
            '{"urgency": "high|medium|low", "needs_attention": true|false, "reason": "1行理由"}\n\n'
            f"メッセージ: {text}"
        )

        try:
            payload = {
                "model": self.config.ollama_model,
                "messages": [
                    {"role": "system", "content": "You are a message classifier. Respond with JSON only. /no_think"},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        self._ollama_available = False
                        log.warning(f"Ollama unavailable: {resp.status}")
                        return None

                    result = await resp.json()
                    self._ollama_available = True
                    content = result.get("message", {}).get("content", "{}")
                    classification = json.loads(content)

            if classification.get("needs_attention", False):
                return FilteredItem(
                    source=obs.source,
                    event_type=obs.event_type,
                    urgency=classification.get("urgency", "medium"),
                    action="notify",
                    data=obs.data,
                    reason=f"ollama: {classification.get('reason', 'classified as important')}",
                )
            else:
                return FilteredItem(
                    source=obs.source,
                    event_type=obs.event_type,
                    urgency="low",
                    action="log",
                    data=obs.data,
                    reason=f"ollama: {classification.get('reason', 'not important')}",
                )

        except Exception as e:
            log.debug(f"Ollama classification failed: {e}")
            self._ollama_available = False
            return None

    def _is_duplicate(self, item: FilteredItem) -> bool:
        """Check if we recently emitted the same notification."""
        # Dedup key based on source + content hash
        key_parts = [item.source, item.event_type]
        content = item.data.get("content", item.data.get("text", ""))
        if content:
            key_parts.append(content[:50])
        key = "|".join(key_parts)

        now = time.time()
        # Clean old entries
        self._recent_notifications = {
            k: v for k, v in self._recent_notifications.items()
            if now - v < self._dedup_window_seconds
        }

        if key in self._recent_notifications:
            return True

        self._recent_notifications[key] = now
        return False
