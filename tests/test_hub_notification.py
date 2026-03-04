#!/usr/bin/env python3
"""
HUB Notification Tester
LiveTalk の HUB 機能（ADR-0119）をテストするためのスクリプト。
report.log に優先度タグ付きの行を書き込み、LiveTalk が反応するか確認する。

使い方:
  python test_hub_notification.py          # 全種類のテスト通知を順番に送信
  python test_hub_notification.py urgent   # 緊急通知のみ送信
"""
import sys
import time
from pathlib import Path
from datetime import datetime

LOG_PATH = Path(__file__).parent / "report.log"

TESTS = [
    ("[URGENT]", "本番 DB が高負荷状態です。確認してください！"),
    ("[SLACK]", "takut さんへのメンション: 明日のミーティング時間を変更したいです"),
    ("[GITHUB]", "PR #142 がマージされました: feat/voice-hub-integration"),
    ("[DEVIN]", "パトロール完了。新規エラー1件: TypeError in api_handler.py L34"),
    ("[ALERT]", "Research Patrol: 新しいトレンド記事が3件見つかりました"),
]

def send(tag, message):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{tag} [{ts}] {message}\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"[TEST] Sent → {line.strip()}")

if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    
    if mode == "urgent":
        send("[URGENT]", "緊急テスト: これは緊急通知のテストです！")
    elif mode == "slack":
        send("[SLACK]", "テスト Slack メンション: @takut お疲れ様です")
    else:
        print("📤 Sending all test notifications (1 per second)...")
        for tag, msg in TESTS:
            send(tag, msg)
            time.sleep(1.5)  # LiveTalk が処理できるよう少し間を空ける
    
    print("✅ Done. Check LiveTalk terminal for voice output.")
