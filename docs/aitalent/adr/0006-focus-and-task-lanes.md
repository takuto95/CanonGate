# ADR 0006: フォーカス固定（現在のクエスト/章）と Task Lane（main/side）+ chapterStage を導入する

- **Status**: Accepted
- **Date**: 2026-01-10
- **Deciders**: User, bmad-orchestrator
- **Related**: `docs/adr/0005-questline-chapters.md`, `docs/bmad/spec-current.md`, `docs/bmad/specs/02-data-model-and-sheets-schema.md`, `docs/bmad/gaps.md`

## Context
章（chapters）を導入しても、タスク生成（思考ログ/日報）によりゴールが増えたりタスクが増えると、ユーザーが「1つのストーリーを追いたい」のにマルチタスク化しやすい。

また「並列タスク」「後続タスク（順序のあるタスク）」を章内で表現したいが、現行の Task は `priority/dueDate` しか持たず、関係性を表現できない。

## Decision
以下を採用する（Option A）。

1) **フォーカス固定（現在のクエスト/章）**
- 現在のフォーカスは **`user_settings` に保存**する（単一ユーザー運用でも、将来のマルチユーザーに耐える）。
  - `focusGoalId`, `focusChapterId`, `focusUpdatedAt`
- 変更履歴は **`sessions` にイベントとして記録**する。
  - `focus_changed`（systemセッションとして記録し、他モードをブロックしない）

2) **Task Lane（main/side）**
- `tasks` に `lane` を追加し、`main | side` を持つ。
- 既存互換のため、未設定は `main` 相当として扱う。
- 日報由来の残タスク/フォローアップは原則 `side` とする（メインストーリー進行を邪魔しない）。

3) **chapterStage（並列/後続の最小表現）**
- `tasks` に `chapterStage`（文字列）を追加する。
- 同じ `chapterId` かつ同じ `chapterStage` のタスクは **並列（Parallel）** と解釈する。
- `chapterStage` が増える（1→2→3...）ほど **後続（Sequential）** と解釈する。
- 既存互換のため、未設定は「段未指定（= 並列扱い）」として扱う。

## Options Considered
- Option A: `lane` + `chapterStage`（今回採用）
  - Pros: 低コスト・Sheetsに馴染む・最小の追加で並列/後続を表現できる
  - Cons: 依存関係（DAG）ほど厳密ではない
- Option B: `dependsOnTaskId[]`（依存関係DAG）
  - Pros: 厳密
  - Cons: データ/UX/編集が重くなる（Sheets運用には過剰）
- Option C: 章プランを sessions に保存し tasks は最小のまま
  - Pros: タスク表は軽い
  - Cons: 表示/APIで毎回集計が必要、整合性が取りづらい

## Consequences
- **Positive**:
  - メインストーリー進行を保護しつつ、サイドに“溜める”ことができる
  - 章内の「並列/後続」の表現が最低限でき、次にやるべき段を判断しやすくなる
- **Negative / Risks**:
  - `lane`/`chapterStage` の入力がAI任せだとブレやすい（フォールバックが必要）
  - `user_settings` のスキーマ拡張（列追加）が必要
- **Operational notes**:
  - 追加列は後方互換（空でも動く）にする
  - `tasks` の列追加はヘッダ末尾に追記し、既存列順は崩さない

## Follow-ups
- [ ] spec更新（`docs/bmad/spec-current.md` / `docs/bmad/specs/*`）
- [ ] 実装（Sheets repo、morning選定 main優先、daily follow-up を side、focus_changed 記録）
- [ ] テスト/検証（build/型、主要フロー回帰）

