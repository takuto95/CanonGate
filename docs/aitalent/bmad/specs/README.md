# 追加spec（機能別spec）

`docs/bmad/spec-current.md` がSSoT（現行仕様の単一の真実）です。  
このディレクトリは、spec-currentを補完する **機能別の深掘りspec** を置きます。

## 区分け（用途別 × 横断関心）
このリポジトリでは、協議しやすさを優先して以下で分割します。

- **用途別（ユーザージャーニー）**: 思考ログ → タスク整理 → 日報 → ステータス → 通知/週次
- **横断関心**: データモデル/Sheets、認証・セキュリティ、運用（Cron/環境変数/ログ）

## 使い分け
- **spec-current**: 重要な仕様の要約/全体像/外部I/F/主要フローの事実
- **specs/**: ある機能の詳細（状態遷移、例外、エラーメッセージ、受入条件、UI文言など）
- **gaps**: 未決定/判断待ち（実装ブロックになるものはここに明示）

## 現行spec（協議用の分割版）
- `01-system-overview.md`（全体像/スコープ）
- `02-data-model-and-sheets-schema.md`（データモデル/Sheets）
- `03-line-session-and-command-routing.md`（モード/コマンド優先順位/セッション）
- `04-thought-log-mode.md`（思考ログ）
- `05-task-summary-and-goal-auto-creation.md`（#タスク整理/ゴール自動作成）
- `06-daily-report-mode.md`（日報）
- `07-status-feature.md`（#ステータス）
- `08-jobs-and-notifications.md`（morning/night/weekly + Cron）
- `09-liff-and-rich-menu.md`（LIFF/リッチメニュー/Flex周辺のUX）
- `10-security-and-auth.md`（LINE署名/内部APIキー/ジョブ保護の論点）
- `11-operations-and-env-vars.md`（環境変数/タイムゾーン/ログ運用）

## 推奨フォーマット
- タイトル
- 背景/目的
- 用語
- フロー（Given/When/Then）
- 例（入出力）
- 例外/エラー
- 非機能（必要なら）

