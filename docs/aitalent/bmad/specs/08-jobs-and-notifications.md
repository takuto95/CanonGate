# Spec: ジョブ（morning/night/weekly）と通知

## 背景 / 目的
定時にユーザーへ「今日の焦点」「夜の確認」「週次レビュー」をPushし、習慣化を支援する。

## エンドポイント
- `/api/jobs/morning`（GET/POST）
- `/api/jobs/nudge`（GET/POST）: 昼の軽い促し（条件付き・最大2回/日）
- `/api/jobs/night`（GET/POST）
- `/api/jobs/weekly`（GET/POST）
- `/api/jobs/cadence`（GET/POST）: 互換/手動用（旧: 4時間枠の統合）
- `/api/jobs/daily-review`（GET/POST）: 日次のタスク見直し（提案のみ、確定はボタン）

## スケジュール（GitHub Actions）
SSoT: `.github/workflows/` 配下（用途別に分割してよい）

- morning（朝）: JST 08:00（UTC 23:00）
- nudge（昼）: JST 12/16/20（UTC 03/07/11）
- night（夜）: JST 00:00（UTC 15:00）
- weekly（週次）: 日曜 21:00 JST（= 日曜 12:00 UTC）
  - 月次/四半期は週次実行の中で判定して追加送信（実装済み）
- daily-review（日次見直し）: 毎日（JST朝の通知前を推奨）

## morning（朝の命令）
- todoから「今日の焦点」を選び、Flex MessageでPushする
- `sessions` に `morning_order` を記録（todoが無い場合も空で記録）
- postback: 今すぐ開始/後で/変更（変更は開発中）

## night（夜の確認）
- 返信は `完了` または `未達 <理由1行>` を要求
- 返信がどのモードでもない場合でも受理し、直近の `morning_order` のタスクを done/miss 更新する

## weekly（週次レビュー）
- 直近7日ログからDeepSeekで週次レビューを生成してPushする

## daily-review（日次のタスク見直し）
- 日報の有無に関わらず、todo一覧と直近ログから「見直し案」を生成して提示する
- **タスク更新/追加は自動では行わない**（誤爆防止）
- 反映（保存）は **ボタン（message action / postback）でのみ確定**する
  - 例: 優先度/期限の反映、後続タスクの追加
  - 例: 表現の修正は `🛠 相談` に誘導する

## セキュリティ（確定）
- `/api/jobs/*` は内部認証（`INTERNAL_API_KEY`）を要求する
- GitHub Actions から `Authorization: Bearer <INTERNAL_API_KEY>` で呼び出す

## 受入条件（Given/When/Then）
- Given: todoが存在し、LINE送信が可能
- When: `/api/jobs/morning` を実行する
- Then: Flex MessageがPushされ、`sessions` に `morning_order` が記録される

