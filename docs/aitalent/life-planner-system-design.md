# 人生設計 AI プランナー設計ドキュメント

> 注意: このドキュメントは **将来構想/設計案** です。  
> **現行の事実ベース仕様（SSoT）は `docs/bmad/spec-current.md`** を参照してください（現状は Sheets 永続化 + LINEコマンド中心で、Supabase/Redis/QStash 等は未導入です）。

## 1. 体験ゴール
- ユーザーは対話ベースでゴール入力→AIがタスク化→自動スケジュール→LINE通知→進捗振り返りまで完了
- アプリを開かずに済むスマホ体験を最優先。通知からワンタップで「完了」「延期」「詳細確認」ができる UX を目指す。

## 2. ハイレベルワークフロー
1. **ゴール設定 (Goal Intake)**
   - フォーム or チャットで「期間」「成果」「優先度」「制約」を取得
   - DeepSeek-R1 で SMART 形式に正規化し、`goals` テーブルへ保存
2. **タスク生成 (Task Ideation)**
   - DeepSeek-R1 へゴール + 既存習慣/可用時間を渡し、エピック→タスク→マイクロステップへ分解
   - Guardrails: 1日の負荷上限、習慣化キューに沿った比率調整
3. **スケジュール反映 (Planner Engine)**
   - Orchestrator がユーザーの空き時間カレンダー/好みスロットを参照し、自動で週次ブロックを作成
   - 競合がある場合は優先度 + 締切からソートして再配置。不可ならユーザーに「調整候補」を通知
4. **通知 (LINE)**
   - 行動 30 分前、開始、終了後フォローの 3 通を基本とする
   - 未実施時は翌日の最初の空き枠に再配置し、リマインドを LINE で送付
5. **進捗管理 (Reflection)**
   - 日次チェックイン: クリア状況、感情タグ、所要時間を LINE で聞く
   - DeepSeek-V3 が内省サマリを生成し、週次レビューにまとめる

## 3. LINE 通知フロー案
| ステップ | 内容 | 実装メモ |
| --- | --- | --- |
| 認証 | LIFF + Messaging API でユーザー紐付け | webhook で userId を取得し、自前DBに保存 |
| サマリPush | 朝5時に「今日の3タスク」を送信 | Vercel Cron or Upstash QStash でジョブ化 |
| 開始前リマインド | タスクごとに開始30分前 | スケジューラが Redis Sorted Set で管理 |
| 実行中チェック | `開始→完了/延期` ボタン | Messaging API のリッチメニュー or Quick Reply |
| 反省記録 | 1日の終わりにフォーム URL or 3択ボタン | DeepSeek-R1 が回答を要約 |

### Notify vs Messaging API
- **Notify**: 実装が簡単・1:1 通知のみ・ボタン不可 → 朝夕サマリ程度なら可
- **Messaging API**: 双方向・クイックリプライ・Webhook 必須 → 本プロジェクトは対話コマンドが必要なのでこちらを採用

### 必要エンドポイント（例）
| Method | Path | 役割 |
| --- | --- | --- |
| POST | `/api/goals` | ゴール作成。DeepSeek で正規化 |
| POST | `/api/tasks/generate` | ゴールからタスク自動生成 |
| POST | `/api/schedule/apply` | タスクをカレンダーに割り当て |
| POST | `/api/line/webhook` | Messaging API 受信口 |
| POST | `/api/line/push` | 通知送信用 (internal) |
| GET  | `/api/progress/today` | 今日のタスク一覧 |
| POST | `/api/progress/complete` | タスク完了・延期更新 |

## 4. DeepSeek プロンプト設計メモ
- **Goal Normalizer** (R1):
  - Input: 生テキスト + 期間 + 制約
  - Output: JSON `{goal, why, success_metrics, guardrails}`
- **Task Planner** (R1/V3):
  - チェーン: `高レベル戦略 → 週次配分 → 1日の具体タスク`
  - System prompt で「1日最大3タスク」「45分以内」「休息含む」を固定
- **Reflection Synthesizer** (V3):
  - Input: タスクログ + 感情タグ
  - Output: 翌週の提案 + リスク警告

## 5. 技術構成案
- **フロント/バック**: Next.js App Router (Edge対応) + React Server Components
- **APIゲートウェイ**: App Router の `route.ts` を REST として利用
- **Orchestrator**: `apps/orchestrator` に Python FastAPI も併存し、長期ジョブ/LLMワークフローを担当
- **ジョブ管理**: QStash or Vercel Cron → Orchestrator の `/jobs/run` を叩く
- **DB**: Supabase (PostgreSQL) + pgvector
- **Cache/Queue**: Upstash Redis (通知スケジュール)
- **Observability**: Logtail or Datadog に HTTP トレースを送信

## 6. スマホ UX 指針
- 通知CTAは最大2択 (完了/延期) + 詳細リンク
- 週次サマリはカード形式でLINE上に画像リッチメッセージ化
- 入力コスト削減のため、自由記述よりテンプレ質問を優先
- オフライン時も追跡できるよう、重要通知はメール二段構え

## 7. 次のアクション
1. LINE Messaging API チャネル開設・Webhook エンドポイント雛形を追加
2. DeepSeek 連携のプロンプトテンプレートを `packages/prompt-kits` に配置
3. 通知スケジューラ (Redis + Cron) のPoC
