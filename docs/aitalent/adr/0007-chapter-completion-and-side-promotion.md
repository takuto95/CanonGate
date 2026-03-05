# ADR 0007: 日報終了で「章完了」判定と「サイド→メイン昇格（最大1件）」を行う

- **Status**: Accepted
- **Date**: 2026-01-10
- **Deciders**: User, bmad-orchestrator
- **Related**: `docs/adr/0005-questline-chapters.md`, `docs/adr/0006-focus-and-task-lanes.md`, `docs/bmad/spec-current.md`, `docs/bmad/specs/06-daily-report-mode.md`

## Context
章（chapters）と lane（main/side）を導入しても、章の進行が確定しないと「ストーリーが進んだ感」が弱い。
またサイド（残タスク）が増殖すると、結局マルチタスクの圧に戻る。

日報終了は「今日の結果」と「明日への提案」を確定する場として既に機能しているため、ここで章進行とサイド回収を最小限自動化する。

## Decision
日報終了（`#日報終了`）で以下を行う。

1) **章完了（chapter completion）**
- 対象: `chapterId` を持つタスクのうち `lane=main` で、かつ `chapterStage` が `1`（または未指定）として解釈されるもの
- 条件: 上記の **todo が0件**になったら、その章を `chapters.status=completed` に更新する

2) **サイド→メイン昇格（side promotion）**
- 対象: `lane=side` かつ `status=todo` のタスク
- 条件: `priority=A` または `dueDate` が3日以内
- 実行: 条件に合うタスクのうち **最大1件**だけ `lane=main` に変更する

## Consequences
- **Positive**:
  - 日々「章が進む/完了する」体験を提供できる
  - サイドの“回収”が少しずつ進み、メインが詰まりにくい
- **Negative / Risks**:
  - 自動昇格がユーザーの意図とズレる可能性（最大1件・条件限定で緩和）
  - `lane/chapterStage` 未設定の既存タスクの扱い（互換: 未指定は `main` / stage1扱い）

## Follow-ups
- [ ] spec更新（`docs/bmad/spec-current.md` / `docs/bmad/specs/06-daily-report-mode.md`）
- [ ] 実装（`#日報終了` に章完了判定とサイド昇格を追加）
- [ ] テスト/検証（回帰: 日報終了・朝選定・章表示）

