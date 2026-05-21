"""Proposal Grounding — multi-source context retrieval for Per-Task Proposals.

Implements priority-1 改修 from research (2026-05-07): grounding the LLM in
task-specific knowledge so Brain stops outputting textbook-generic options.

Sources (priority order, char-budgeted to avoid context rot — Liu 2023, Chroma 2025):
  1. Task body — gtd/work/next-actions/{title}.md or evaluating/
  2. Related ADR — Canon/docs/adr/*.md by keyword overlap
  3. Related knowledge — agent/brain/knowledge/*.md by keyword overlap
  4. Persons context — agent/persons.json relevant entries

Total injected context capped at ~2500 chars (Lost-in-the-Middle: keep prompt focused).
Per-source caps prevent any single source from monopolizing budget.
"""

import json
import os
import re
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("canon-brain.proposal_grounding")

# Per-source character budgets (sum ≈ 3500 with user memory enabled)
MAX_TASK_BODY = 700
MAX_PER_ADR = 400
MAX_TOTAL_ADR = 700
MAX_PER_KNOWLEDGE = 400
MAX_TOTAL_KNOWLEDGE = 600
MAX_PERSONS = 500
MAX_PER_USER_MEMORY = 350
MAX_TOTAL_USER_MEMORY = 800

# Departure / leave / handover keywords scanned in persons.json note for
# the resource planner context (always injected unconditionally).
DEPARTURE_KEYWORDS = [
    "退職", "離脱", "異動", "業務委託", "抜け", "段階移管",
    "引継ぎ先", "引継先", "離れ", "卒業",
]

# Default user-level Claude session memory location. Brain runs as the user
# so this is reachable. Override via CANON_USER_MEMORY_DIR env var.
def _user_memory_dir() -> Optional[Path]:
    explicit = os.getenv("CANON_USER_MEMORY_DIR", "").strip()
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    # Default to current user's c--databee project memory
    p = Path.home() / ".claude" / "projects" / "c--databee" / "memory"
    return p if p.exists() else None


_CJK_PUNCT = "、。！？「」『』【】（）()[]{}<>《》"


def _extract_keywords(text: str, max_n: int = 8) -> list[str]:
    """Extract candidate keywords from a task title/body.

    Picks ASCII alphanumeric chunks length ≥3, plus CJK chunks length ≥2.
    Removes stopwords. Returns deduplicated, in order of appearance.
    """
    if not text:
        return []
    # ASCII tokens
    ascii_tokens = re.findall(r"[A-Za-z0-9_\-]{3,}", text)
    # CJK tokens (≥2 consecutive Han/Hiragana/Katakana chars)
    cjk_tokens = re.findall(r"[぀-ヿ一-鿿]{2,}", text)
    stop = {
        "対応", "確認", "依頼", "実施", "実装", "案", "件",
        "について", "に関する", "について", "回答",
        "the", "and", "for", "with", "from", "have", "this", "that",
    }
    seen: set[str] = set()
    out: list[str] = []
    for tok in ascii_tokens + cjk_tokens:
        low = tok.lower()
        if low in stop or low in seen:
            continue
        seen.add(low)
        out.append(tok)
        if len(out) >= max_n:
            break
    return out


def _read_md_safe(path: Path, max_chars: int) -> str:
    """Read a markdown file with frontmatter stripped, capped at max_chars."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    body = re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)
    body = body.strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "\n... (truncated)"
    return body


def _score_file_against_keywords(path: Path, keywords: list[str], scan_max_chars: int = 4000) -> int:
    """Count keyword occurrences in the first scan_max_chars of file. Lightweight BM25-like signal."""
    if not keywords:
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:scan_max_chars]
    except Exception:
        return 0
    text_lower = text.lower()
    score = 0
    for kw in keywords:
        kw_low = kw.lower()
        score += text_lower.count(kw_low)
    return score


def _gather_task_body(config, task_data: dict) -> str:
    """Read the task body from gtd/work/next-actions or evaluating."""
    task_id = task_data.get("id") or ""
    title = (task_data.get("title") or "").strip()
    candidates: list[Path] = []

    # If id ends in .md, treat as filename in next-actions/evaluating
    domains = ["work", "private"]
    folders = ["next-actions", "evaluating"]
    if task_id.endswith(".md"):
        for d in domains:
            for fol in folders:
                candidates.append(config.gtd_dir / d / fol / task_id)
    # Also try by title as filename (existing convention)
    if title:
        safe = re.sub(r'[\\/:*?"<>|]', "_", title)[:80].strip()
        for d in domains:
            for fol in folders:
                candidates.append(config.gtd_dir / d / fol / f"{safe}.md")

    for p in candidates:
        if p.exists():
            body = _read_md_safe(p, MAX_TASK_BODY)
            if body:
                return f"### Source: {p.name}\n{body}"
    return ""


def _gather_related_adr(config, keywords: list[str]) -> str:
    """Pull top ADR markdowns by keyword overlap."""
    if not keywords:
        return ""
    adr_dir = config.canon_dir / "docs" / "adr"
    if not adr_dir.exists():
        return ""
    scored: list[tuple[int, Path]] = []
    for f in adr_dir.glob("*.md"):
        s = _score_file_against_keywords(f, keywords)
        if s > 0:
            scored.append((s, f))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    parts: list[str] = []
    used = 0
    for score, f in scored[:3]:
        body = _read_md_safe(f, MAX_PER_ADR)
        if not body:
            continue
        chunk = f"### {f.stem} (kwhit={score})\n{body}"
        if used + len(chunk) > MAX_TOTAL_ADR:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n\n".join(parts)


def _gather_related_knowledge(config, keywords: list[str]) -> str:
    """Pull top knowledge markdowns from agent/brain/knowledge by keyword overlap."""
    if not keywords:
        return ""
    knowledge_dir = config.knowledge_dir
    if not knowledge_dir.exists():
        return ""
    scored: list[tuple[int, Path]] = []
    for f in knowledge_dir.rglob("*.md"):
        s = _score_file_against_keywords(f, keywords)
        if s > 0:
            scored.append((s, f))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    parts: list[str] = []
    used = 0
    for score, f in scored[:3]:
        body = _read_md_safe(f, MAX_PER_KNOWLEDGE)
        if not body:
            continue
        rel = f.relative_to(knowledge_dir)
        chunk = f"### knowledge/{rel} (kwhit={score})\n{body}"
        if used + len(chunk) > MAX_TOTAL_KNOWLEDGE:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n\n".join(parts)


def _gather_user_memory(keywords: list[str]) -> str:
    """Pull top user-level Claude session memory markdowns by keyword overlap.

    Source: ~/.claude/projects/c--databee/memory/{project,feedback,reference,user}_*.md
    Excludes MEMORY.md (index file). Capped at MAX_TOTAL_USER_MEMORY chars.

    These memories are richer than persons.json/knowledge — they contain
    project status, departure plans, decisions, feedback patterns.
    """
    mem_dir = _user_memory_dir()
    if not mem_dir or not keywords:
        return ""
    scored: list[tuple[int, Path]] = []
    for f in mem_dir.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        s = _score_file_against_keywords(f, keywords)
        if s > 0:
            scored.append((s, f))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    parts: list[str] = []
    used = 0
    for score, f in scored[:3]:
        body = _read_md_safe(f, MAX_PER_USER_MEMORY)
        if not body:
            continue
        chunk = f"### memory/{f.name} (kwhit={score})\n{body}"
        if used + len(chunk) > MAX_TOTAL_USER_MEMORY:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n\n".join(parts)


def _gather_persons_context(config, task_data: dict, base_context: str) -> str:
    """Extract relevant persons from persons.json based on names mentioned
    in task title/body/base_context.
    """
    persons_path = config.agent_dir / "persons.json"
    if not persons_path.exists():
        return ""
    try:
        data = json.loads(persons_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    haystack = " ".join([
        task_data.get("title", ""),
        task_data.get("context", ""),
        task_data.get("action_hint", ""),
        base_context[:1500] if base_context else "",
    ])

    # persons.json structure varies; handle list of dicts or dict with persons key
    persons_list: list[dict] = []
    if isinstance(data, list):
        persons_list = data
    elif isinstance(data, dict):
        for k in ("persons", "members", "people", "team"):
            v = data.get(k)
            if isinstance(v, list):
                persons_list = v
                break
        if not persons_list:
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    persons_list = v
                    break

    if not persons_list:
        return ""

    matched: list[str] = []
    used = 0
    for p in persons_list:
        if not isinstance(p, dict):
            continue
        name_keys = []
        for k in ("name", "display_name", "full_name", "ja_name", "kana"):
            v = p.get(k)
            if isinstance(v, str) and v:
                name_keys.append(v)
        if not any(n and n in haystack for n in name_keys):
            continue
        # Build a one-line summary
        parts = []
        for k in ("name", "display_name", "role", "team", "status", "departure_date", "notes"):
            v = p.get(k)
            if v and isinstance(v, (str, int, float)):
                parts.append(f"{k}={v}")
        line = "; ".join(parts)[:200]
        if used + len(line) > MAX_PERSONS:
            break
        matched.append("- " + line)
        used += len(line)
    return "\n".join(matched)


def gather_grounding_for_task(config, task_data: dict, base_context: str = "") -> str:
    """Build a markdown-formatted grounding block for a task.

    Returns empty string if nothing matched (caller can detect and skip injection).
    """
    title = (task_data.get("title") or "").strip()
    body_seed = (task_data.get("context") or "") + " " + (task_data.get("action_hint") or "")
    keywords = _extract_keywords(title + " " + body_seed)

    sections: list[tuple[str, str]] = []

    task_body = _gather_task_body(config, task_data)
    if task_body:
        sections.append(("Task body", task_body))

    adr_block = _gather_related_adr(config, keywords)
    if adr_block:
        sections.append(("Related ADR (kwhit ranked)", adr_block))

    knowledge_block = _gather_related_knowledge(config, keywords)
    if knowledge_block:
        sections.append(("Related knowledge", knowledge_block))

    persons_block = _gather_persons_context(config, task_data, base_context)
    if persons_block:
        sections.append(("Relevant persons (from persons.json)", persons_block))

    user_memory_block = _gather_user_memory(keywords)
    if user_memory_block:
        sections.append(("User memory (project/feedback/reference)", user_memory_block))

    if not sections:
        log.debug(f"Grounding: no sources matched for task '{title[:40]}' (keywords={keywords})")
        return ""

    out_parts = ["## Grounding (Brain が引いた周辺事実)"]
    for label, body in sections:
        out_parts.append(f"\n### {label}\n{body}")
    block = "\n".join(out_parts)
    log.info(
        f"Grounding gathered: task='{title[:40]}' "
        f"sections={len(sections)} chars={len(block)} keywords={keywords[:5]}"
    )
    return block


def gather_resource_planner_context(config) -> str:
    """Build resource-planner-specific grounding.

    Always injected (independent of task title), unlike per-task grounding:
      - Departing/handover-pending members from persons.json (note keyword scan)
      - Member roster summary (name, capacity, current_focus)
      - Recent project_*.md from user memory (project status, departure plans)

    Returns markdown block. Used by thinker.think_resource_review to cure
    the 'handover plan = 該当なし' false-negative.
    """
    parts: list[str] = ["## Grounding (Resource Planner 専用)"]

    # ---- Members from persons.json ----
    persons_path = config.agent_dir / "persons.json"
    departing: list[str] = []
    roster: list[str] = []
    if persons_path.exists():
        try:
            data = json.loads(persons_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Resource planner: persons.json parse failed: {e}")
            data = {}
        members = data.get("members", []) if isinstance(data, dict) else []
        for m in members:
            if not isinstance(m, dict):
                continue
            name = m.get("name", "?")
            note = (m.get("note") or "").strip()
            cap = m.get("capacity_hours_week")
            focus = m.get("current_focus") or []
            focus_short = ", ".join(focus[:3])[:80] if focus else ""
            roster_line = f"- **{name}** (cap={cap}h/週) focus=[{focus_short}]"
            if note:
                roster_line += f" note=「{note[:120]}」"
            roster.append(roster_line)
            # Departing detection
            if any(kw in note for kw in DEPARTURE_KEYWORDS):
                departing.append(f"- 🚨 **{name}**: {note[:200]}")
    if departing:
        parts.append("\n### 退職/異動/移管予定 (persons.json note 由来 — 引継ぎ計画必須)")
        parts.extend(departing)
    if roster:
        parts.append("\n### メンバー一覧 (capacity と current_focus)")
        parts.extend(roster)

    # ---- Recent project_*.md from user memory ----
    mem_dir = _user_memory_dir()
    if mem_dir:
        # Sort by mtime, take most recent 3 project_*.md
        project_files = sorted(
            mem_dir.glob("project_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]
        if project_files:
            parts.append("\n### 直近 project memory (上位3件、最終更新順)")
            used = 0
            for f in project_files:
                body = _read_md_safe(f, MAX_PER_USER_MEMORY)
                if not body:
                    continue
                chunk = f"#### memory/{f.name}\n{body}"
                if used + len(chunk) > MAX_TOTAL_USER_MEMORY:
                    break
                parts.append(chunk)
                used += len(chunk)

    block = "\n".join(parts)
    log.info(
        f"Resource planner context built: chars={len(block)} "
        f"departing={len(departing)} roster={len(roster)}"
    )
    return block if len(parts) > 1 else ""
