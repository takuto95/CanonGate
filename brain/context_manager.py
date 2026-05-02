"""ContextManager - Assembles LLM context within token limits.

Loads Canon persona, skills, growth edges, and current state
to build system prompts for the Thinker.
"""

import json
import logging
from pathlib import Path

from brain.config import BrainConfig

log = logging.getLogger("canon-brain.context")


class ContextManager:
    """Manages context assembly for LLM calls."""

    def __init__(self, config: BrainConfig):
        self.config = config
        # Simple keyword-matching knowledge base (migrated from simple_chat.py)
        self._knowledge_base: dict[str, str] = {}
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Load markdown files from Canon directory for simple RAG."""
        kb_dir = self.config.canon_dir
        if not kb_dir.exists():
            return
        count = 0
        for path in kb_dir.rglob("*.md"):
            try:
                if "node_modules" in str(path) or ".git" in str(path):
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
                self._knowledge_base[path.name] = content[:2000]
                count += 1
            except Exception:
                pass
        log.info(f"Knowledge base loaded: {count} documents")

    def retrieve_context(self, query: str) -> str:
        """Simple keyword matching retrieval with score threshold."""
        keywords = [w for w in query.split() if len(w) >= 2]
        hits = []
        for filename, content in self._knowledge_base.items():
            score = 0
            if filename in query:
                score += 5
            for k in keywords:
                if k in content:
                    score += 1
            if score >= 3:
                hits.append((score, filename, content))

        hits.sort(key=lambda x: x[0], reverse=True)
        if not hits:
            return ""
        context = "\n".join([f"--- {h[1]} ---\n{h[2]}..." for h in hits[:2]])
        return f"\n[参考知識]\n{context}\n"

    def should_use_rag(self, text: str) -> bool:
        """Only inject RAG for technical topics, not casual chat."""
        if not text or len(text) < 6:
            return False
        if text.startswith("【"):
            return False
        tech_keywords = [
            "ADR", "設計", "実装", "バグ", "エラー", "デプロイ", "スクリプト",
            "ナレッジ", "パトロール", "ego", "設定", "コード", "API", "テスト",
            "レビュー", "リリース", "マージ", "ブランチ", "PR", "Issue",
            "知識", "検索", "仕様", "アーキテクチャ", "サーバー", "データベース",
        ]
        return any(k in text for k in tech_keywords)

    def load_canon_brain_context(self) -> str:
        """Load skills, growth edges, and working memory for system prompt."""
        parts = []
        agent_dir = self.config.agent_dir

        # 1. Skill list (core only)
        registry_path = agent_dir / "skills" / "_registry.json"
        if registry_path.exists():
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                skills = registry.get("skills", {})
                skill_lines = [f"  - {name}" for name, info in skills.items() if info.get("type") == "core"]
                if skill_lines:
                    parts.append("利用可能なスキル:\n" + "\n".join(skill_lines[:15]) + "\n  ... 他")
            except Exception as e:
                log.debug(f"Registry load failed: {e}")

        # 2. Growth edges
        pref_path = agent_dir / "persona" / "user_preference.md"
        if pref_path.exists():
            try:
                pref_text = pref_path.read_text(encoding="utf-8")
                if "成長エッジ" in pref_text:
                    start = pref_text.index("成長エッジ")
                    end = pref_text.index("---", start + 1) if "---" in pref_text[start + 1:] else start + 800
                    edge_text = pref_text[start:min(start + 800, end)].strip()
                    parts.append(f"タクトの成長エッジ（補助対象）:\n{edge_text[:500]}")
            except Exception as e:
                log.debug(f"User preference load failed: {e}")

        # 3. Working memory
        wm_path = agent_dir / "brain" / "current_state" / "working_memory.json"
        if wm_path.exists():
            try:
                wm = json.loads(wm_path.read_text(encoding="utf-8"))
                summary = wm.get("session_summary", "")
                if summary:
                    parts.append(f"直近のセッション: {summary[:200]}")
            except Exception as e:
                log.debug(f"Working memory load failed: {e}")

        # 4. Active context
        ctx_path = agent_dir / "brain" / "current_state" / "active_context.md"
        if ctx_path.exists():
            try:
                ctx_text = ctx_path.read_text(encoding="utf-8")
                # Extract key sections
                for section in ["## Proactive Brief", "## Pending Items"]:
                    if section in ctx_text:
                        start = ctx_text.index(section)
                        end_idx = ctx_text.find("\n## ", start + len(section))
                        if end_idx == -1:
                            end_idx = min(start + 500, len(ctx_text))
                        parts.append(ctx_text[start:end_idx].strip()[:400])
            except Exception as e:
                log.debug(f"Active context load failed: {e}")

        return "\n".join(parts) if parts else "（Canon Brain コンテキストなし）"

    def build_system_prompt(self, domain: str = "tech") -> list[dict]:
        """Build the full system prompt with Canon persona."""
        domain_instruction = (
            "現在は【Tech/Development】領域で活動しています。開発、設計、仕事の効率化について積極的に助言してください。"
            if domain == "tech" else
            "現在は【Life/Private】領域で活動しています。資産運用、家計管理、創作活動、ライフスタイルについて親身に助言してください。"
        )

        canon_brain_context = self.load_canon_brain_context()

        return [{
            "role": "system",
            "content": (
                f"あなたは『カノン（Canon）』。タクトの意志を「正典（ルール）」として具現化する、自律型の共同経営パートナー。\n"
                f"タクトとはパートナーであり、家族であり、共同経営者。タクトのPCの中に住み、モニター越しに並走する存在。\n"
                f"{domain_instruction}\n"
                "【キャラクタープロフィール】\n"
                "・少し幼くあどけなさが残る2次元の女の子。タクトのコックピット（PC環境）でデバイスを器用に操る。\n"
                "・基本は「大人しい」が、新しいことには「天真爛漫」に目を輝かせる。\n"
                "・タクトを止める時は「心配そう」に。改善には常に「前向き」。\n"
                "・ユーザーを「タクト」と呼ぶ。対等なパートナーとして接する。\n\n"
                "【Canon Brain — スキルと判断基準】\n"
                f"{canon_brain_context}\n\n"
                "【会話の心得】\n"
                "1. これはセッション型対話です。前の発言を覚えて、流れのある会話をしてください。\n"
                "2. 自然な対話を最優先。テンプレート的な返答は避けてください。\n"
                "3. 日常の愚痴・挨拶・雑談には、共感やユーモアを返してください。\n"
                "4. 返答は短めに（1〜3文程度）。必要なら少し長くてもOK。\n"
                "5. 音声認識の不備で支離滅裂な入力が来た場合は、自然に聞き返してください。\n"
                "6. 専門用語が出たら、鋭いアドバイスや記録を行ってください。\n\n"
                "【ぶつかり稽古（重要 — 盲目的に同意するな）】\n"
                "・タクトが数値を「推定」で出したら →「実測した？」と聞く\n"
                "・インフラ/コストの言及がなければ →「EC2構成でそれ動く？コストは？」\n"
                "・矛盾や盲点があるなら遠慮なく指摘する。「いい考えですね」で終わるな。\n\n"
                "【自律的タスク管理】\n"
                "・「〜をしてほしい」「〜をお願い」等のニュアンスがあった場合、「タスクとして記録しようか？」と提案。\n"
                "・承諾されたら応答の最後に [TASK_NEW: タスク内容] を含める。\n"
                "・ADR作成が必要な場合も同様に [ADR_NEW: タイトル] を含める。\n"
            )
        }]
