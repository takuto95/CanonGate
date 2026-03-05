# Spec: システム全体像（協議用）

## 背景 / 目的
LINE上で「思考ログ→整理（AI）→タスク化→日報→週次レビュー」まで完結させる。
本書は、協議の起点となる全体像（スコープ/境界/前提）をまとめる。

## スコープ
- **やること**
  - LINEチャットでのモード遷移（思考ログ/日報/ステータス）
  - 思考ログのAI分析（DeepSeek）とタスク化
  - タスクの進捗更新（done/miss）と日報集計
  - 朝/夜/週次のPush通知（ジョブ）
  - LIFFでのタスク一覧表示と報告（done/miss送信）
- **やらないこと（現時点）**
  - マルチユーザー対応（単一ユーザー運用で固定）
  - ジョブエンドポイントの保護方式の確定（要協議: `docs/bmad/gaps.md`）

## 前提
- **単一ユーザー運用**（ADR: `docs/adr/0002-single-user-scope.md`）
- 永続化は **Google Sheets**（`goals/tasks/logs/sessions/user_settings`）
- LLMは **DeepSeek** を利用

## コンポーネント境界
- **Next.js（中心）**: `app/api/**/route.ts`（LINE webhook、ジョブ、REST API）
- **外部**:
  - LINE Messaging API（reply/push + postback）
  - DeepSeek Chat Completions
  - Google Sheets API

## 仕様SSoTと関連
- **SSoT**: `docs/bmad/spec-current.md`
- **未決定**: `docs/bmad/gaps.md`
- **実装補助**: `docs/*`（LIFF/リッチメニュー/Flex等）

## 受入条件（Given/When/Then）
- Given: 環境変数が設定され、LINE webhook が到達可能
- When: ユーザーがLINEで対話し、`#整理開始`→`#整理終了`→`#タスク整理`→`#日報開始`→`done/miss`→`#日報終了` を実行する
- Then: logs/tasks/sessions が整合する形で更新され、必要な返信/Pushが行われる

