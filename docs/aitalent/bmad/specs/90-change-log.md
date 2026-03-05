# Spec: 協議/変更の記録（リンク集）

## 目的
README に混在していた「協議の記録/変更履歴」を、仕様（SSoT）と分離して参照できるように集約する。

- **SSoT（現行仕様）**: `docs/bmad/spec-current.md`
- **意思決定（Decision）はADR**: `docs/adr/`
- **実装の詳細経緯（fixドキュメント）**: `docs/bmad/fix-*.md`

## 変更履歴（主要）

### 2024-12-30
- タスク更新失敗の検知と通知: `docs/bmad/fix-2024-12-30-task-update-verification.md`
- 日報UX改善（入力形式/エラー検知/分割表示）: `docs/bmad/fix-2024-12-30-improved-ux.md`
- モチベーション改善: `docs/bmad/fix-2024-12-30-motivation-improvement.md`
- 思考ログの深掘り改善: `docs/bmad/fix-2024-12-30-thought-log-deep-dive.md`
- ゴール自動作成/ゴール-タスク連携: `docs/bmad/fix-2024-12-30-goal-auto-creation.md`, `docs/bmad/fix-2024-12-30-goal-task-linkage.md`
- キーワードレス化/改善まとめ: `docs/bmad/fix-2024-12-30-keywordless-and-improvements.md`
- フェーズ進捗まとめ: `docs/bmad/PHASE1-4-COMPLETE.md`

### 2025-01-02
- Flex Message（朝の命令通知）導入〜改善・UI統合: `docs/bmad/fix-2024-12-30-all-improvements.md`（関連） / `docs/flex-message-test.md`
- リッチメニュー & LIFF: `docs/liff-deployment-guide.md`, `docs/rich-menu-image-guide.md`

## メモ
- 「この仕様を変える」場合は、まず `docs/bmad/gaps.md` に未決定点として追加し、決まったら `docs/bmad/spec-current.md` に反映する。
- 認証/権限などの設計判断は ADR に残す（例: 単一ユーザー方針 `docs/adr/0002-single-user-scope.md`）。
