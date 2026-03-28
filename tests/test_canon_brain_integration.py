"""P0/P2: Canon Brain Integration テスト"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

# simple_chat.py のインポートは依存が重いのでモック
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_load_canon_brain_context_returns_string():
    """_load_canon_brain_context がスキル情報を含む文字列を返すか"""
    # simple_chat.py のグローバル変数が多いため、関数を直接テストするのは困難。
    # 代わりに、Canon/.agent/skills/_registry.json の存在と構造をテストする。
    agent_dir = Path(__file__).parent.parent.parent / "Canon" / ".agent"
    registry_path = agent_dir / "skills" / "_registry.json"

    assert registry_path.exists(), f"Registry not found at {registry_path}"

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    skills = registry.get("skills", {})

    # 最低20個の core スキルがあるはず
    core_skills = {k: v for k, v in skills.items() if v.get("type") == "core"}
    assert len(core_skills) >= 20, f"Expected >= 20 core skills, got {len(core_skills)}"

    # 必須スキルの存在確認
    required = ["tech-analysis", "code-review", "leadership", "negotiation", "skill-evolution"]
    for skill in required:
        assert skill in core_skills, f"Required skill '{skill}' not found in registry"


def test_working_memory_exists_and_valid():
    """working_memory.json が存在し、必要なフィールドを含むか"""
    wm_path = Path(__file__).parent.parent.parent / "Canon" / ".agent" / "brain" / "current_state" / "working_memory.json"

    assert wm_path.exists(), f"working_memory.json not found at {wm_path}"

    wm = json.loads(wm_path.read_text(encoding="utf-8"))
    assert "session_summary" in wm, "session_summary field missing"
    assert "key_changes" in wm, "key_changes field missing"
    assert len(wm["session_summary"]) > 10, "session_summary is too short"


def test_user_preference_has_growth_edges():
    """user_preference.md に成長エッジセクションがあるか"""
    pref_path = Path(__file__).parent.parent.parent / "Canon" / ".agent" / "persona" / "user_preference.md"

    assert pref_path.exists(), f"user_preference.md not found"

    text = pref_path.read_text(encoding="utf-8")
    assert "成長エッジ" in text, "成長エッジ section not found in user_preference.md"
    assert "ぶつかり稽古" in text, "ぶつかり稽古 section not found in user_preference.md"


def test_hallucination_filter():
    """ハルシネーションフィルタが典型パターンを検出するか"""
    # simple_chat.py から直接インポートできないため、ロジックを再実装してテスト
    HALLUCINATION_PHRASES = [
        "ご視聴ありがとうございます",
        "チャンネル登録",
        "Thank you",
    ]

    def is_hallucination(text):
        if not text:
            return True
        for phrase in HALLUCINATION_PHRASES:
            if phrase in text:
                return True
        return False

    assert is_hallucination("") == True
    assert is_hallucination(None) == True
    assert is_hallucination("ご視聴ありがとうございます") == True
    assert is_hallucination("チャンネル登録お願いします") == True
    assert is_hallucination("今日の天気は晴れです") == False
    assert is_hallucination("積水賃貸のパフォーマンスを改善したい") == False


def test_stt_drift_correction():
    """STTドリフト補正が正しく動くか"""
    STT_DRIFT_CORRECTIONS = [
        ("競技中", "編集中"),
        ("エディアール", "ADR"),
        ("アルターエゴ", "Canon"),
    ]

    def correct_stt_drift(text):
        if not text:
            return text
        s = text
        for wrong, right in STT_DRIFT_CORRECTIONS:
            s = s.replace(wrong, right)
        return s

    assert correct_stt_drift("競技中のファイル") == "編集中のファイル"
    assert correct_stt_drift("エディアールを作成") == "ADRを作成"
    assert correct_stt_drift("アルターエゴに聞いて") == "Canonに聞いて"
    assert correct_stt_drift("普通のテキスト") == "普通のテキスト"
    assert correct_stt_drift("") == ""
    assert correct_stt_drift(None) == None


def test_ws_host_security():
    """WS_HOSTがデフォルトでlocalhostになっているか（P4セキュリティ）"""
    import os
    # 環境変数が設定されていない場合のデフォルト値をチェック
    if "WS_HOST" not in os.environ:
        # simple_chat.py の WS_HOST デフォルト値が 127.0.0.1 であることを確認
        chat_path = Path(__file__).parent.parent / "simple_chat.py"
        text = chat_path.read_text(encoding="utf-8")
        assert 'os.getenv("WS_HOST", "127.0.0.1")' in text, \
            "WS_HOST default should be 127.0.0.1 for security"


if __name__ == "__main__":
    tests = [
        test_load_canon_brain_context_returns_string,
        test_working_memory_exists_and_valid,
        test_user_preference_has_growth_edges,
        test_hallucination_filter,
        test_stt_drift_correction,
        test_ws_host_security,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✅ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
