# BMADフローに基づく開発計画（フロー/ロードマップ専用）

このドキュメントは **計画**（フローとロードマップ）だけを扱います。
仕様本文・不足点は混在防止のため `docs/bmad/` に分離しました。

- 仕様（現状の単一の真実）: `docs/bmad/spec-current.md`
- 足りないところ（未決定/例外/非機能）: `docs/bmad/gaps.md`

> 注意: ここに書かれている Supabase/Redis/QStash 等の構成は **将来計画** です。  
> 現行実装は Next.js（`app/api/**/route.ts`）+ Google Sheets（`goals/tasks/logs/sessions`）が中心です。

## B (Business/Background)
- **対象顧客**: 多忙な社会人 (30〜45歳) が本業と生活を両立しながら中長期ゴールを達成したい層。スマホ通知ベースで完結する伴走体験を重視。
- **課題**: ゴールをタスク化できず先送りになる、複数アプリを渡り歩く煩雑さ、客観的な振り返りができない。
- **成功指標**: ① 週次ゴール達成率70%以上、② 日次チェックイン回答率80%以上、③ LINE通知からの操作完結率90%以上。

## M (Market/Modeling)
- **主要ユースケース**
  1. **ゴール正規化**: フォーム/チャットから取得した曖昧なゴールをSMART形式に変換し、優先度・制約を明示。
  2. **タスク分解＋スケジュール**: DeepSeekでエピック→タスク→マイクロステップへ分解し、週次の空き時間へ自動配置。
  3. **LINE通知 & 進捗振り返り**: 朝のデイリーブリーフ、開始前リマインド、日次レビュー、週次サマリをMessaging APIでやり取り。
- **MVP機能セット**
  - Goal Intake API (`/api/goals`) + DeepSeek Goal Normalizer
  - Task Planner + Planner Engine (空き時間カレンダー反映)
  - LINE Messaging APIコネクタ (Webhook + Push)
  - 進捗チェック/ReflectionログAPI
  - Supabase (PostgreSQL + pgvector) を用いたユーザーデータ永続化

## A (Architecture/Assemble)
- **システム構成**
  - `app/route.ts` 配下: Next.js App RouterのRESTエンドポイント。Goal/Task/Progress APIやLINE Webhookをサーブ。
  - `lib/deepseek.ts`: DeepSeek-R1/V3クライアントとプロンプトテンプレを管理。
  - `lib/line.ts`: Messaging APIクライアント、Push/Replyユーティリティ。
  - `apps/orchestrator`: Python FastAPIランタイムで長時間タスクやスケジューラジョブを処理。Next.js APIからジョブをkickする。
  - Supabase(PostgreSQL) + pgvector: ゴール、タスク、進捗、Embeddingを保存。
  - Upstash Redis: 通知スケジューリング用Sorted Setキュー。
- **データフロー**
  1. ユーザーがLINE/フォームでゴールを入力し、Next.js APIがSupabaseへ保存、DeepSeek Goal Normalizerをキック。
  2. Task Plannerがタスク分解→Planner Engineがユーザーの空き時間カレンダーを参照して週次ブロック化。
  3. 生成タスクはRedisキューに積まれ、通知トリガー時にLINE Push/Replyを送信。
  4. 日次チェックイン結果はSupabaseへ保存→DeepSeekがReflectionサマリを生成し、週次レポートとして送信。
- **技術選定**
  - Next.js App Router (Edge対応) + TypeScript: APIとUIを兼用しつつVercelへのデプロイ容易化。
  - DeepSeek-R1/V3: Goal Normalizer、Task Planner、Reflection Synthesizerで共通利用。
  - Python 3.11 + FastAPI + AsyncIO: オーケストレータのバッチ/ジョブ処理。
  - Supabase(Prisma/PostgREST) + pgvector: LLMメモリとタスク履歴を一元管理。
  - Upstash Redis + QStash/Vercel Cron: 通知スケジュールと遅延ジョブ。

## D (Delivery/Deploy)
- **短期ロードマップ (0-4週間)**
  1. Goal/Task/Progress APIをNext.jsルートハンドラに実装し、Supabaseスキーマを定義。
  2. DeepSeek Goal Normalizer & Task Plannerプロンプトキットを整備し、lib以下に共通化。
  3. LINE Messaging APIチャネル設定、Webhook (`/api/line/webhook`) とPush (`/api/line/push`) を実装。
  4. Redisベースの通知スケジューラPoC (朝サマリ、開始30分前リマインド) を構築。
  5. Pythonオーケストレータで週次レビュー生成ジョブを実装し、QStash/Vercel Cronから起動。
- **デリバリー**
  - mainブランチはCI必須。プレビュー環境はVercel Preview + Railway(Supabase互換)。
  - Observability: Logtail/DatadogにAPIトレース、機密ログはPIIマスキング後に送信。
  - SecretsはVercel/1Password経由で管理、LINEチャネル情報は環境変数に限定。
