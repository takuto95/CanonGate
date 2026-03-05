# ADR 0005: ゴールをクエストライン化し「章（chapters）」を導入する

- **Status**: Accepted
- **Date**: 2026-01-10
- **Deciders**: User, bmad-orchestrator
- **Related**: `docs/bmad/spec-current.md`, `docs/bmad/specs/02-data-model-and-sheets-schema.md`

## Context
現行のタスク管理は `goals` と `tasks` を中心に「やるべきこと」を実行・記録する設計であり、ゴールが“物語（クエスト）の章立て”として進行する概念がない。

ユーザー要望として「RPGのようにストーリーのゴールが気になって、目の前のタスクを進めたくなる」体験を実現したい。

制約として、現行の永続化は Google Sheets であり、既存の `goals/tasks/logs/sessions/user_settings` を使って運用されている。互換性を壊さず段階的に導入する必要がある。

## Decision
以下を採用する。

- **ゴール（Goal）を「クエストライン（Questline）」として解釈**し、ゴール配下に **章（Chapter）** を持てるようにする。
- 新しいシート **`chapters`** を追加し、章を永続化する。
- タスクは `goalId` に加え **`chapterId`（任意）** を持ち、章に紐付けられる。
- 既存データ互換のため、`chapterId` が空の既存タスクは「章未設定（= 既存互換）」として扱う（表示・APIは空許容）。

## Options Considered
- Option A: 文章演出のみ（スキーマ変更なし）
  - Pros: 最速・安全
  - Cons: “章進行/次章予告/クエストライン”の骨格が作れず、物語牽引が弱い
- Option B: Goalに章テキストを埋める（最小メタ追加）
  - Pros: シート追加なしで実現可能
  - Cons: 章とタスクの関連、進行状態の計算・表示が曖昧になりやすい
- Option C: Chapterエンティティ導入（本ADR）
  - Pros: 章進行・次章予告・クエストライン表現が明確、UI/通知/分析に再利用できる
  - Cons: 新シート追加と移行・互換設計が必要

## Consequences
- **Positive**:
  - ゴールを「章立て」で表現でき、ユーザーの“続きが気になる”動機をシステムとして支えられる
  - タスクが物語進行（章）に結びつき、朝通知/LIFF/ステータスに共通の文脈を出せる
- **Negative / Risks**:
  - 新しい `chapters` シートが未作成の場合、運用手順が必要になる
  - AI出力（章/タスク割当）が不安定な場合のフォールバック設計が必要
- **Operational notes**:
  - 既存運用は継続できる（`chapterId` は任意、未設定でも動作）
  - `chapters` シートの追加とヘッダ整備が必要（手動/運用手順に明記）

## Follow-ups
- [ ] spec更新（`docs/bmad/spec-current.md` / `docs/bmad/specs/02-data-model-and-sheets-schema.md`）
- [ ] 実装（`chapters` repository、`TaskRecord.chapterId`、表示/通知反映）
- [ ] テスト/検証（型チェック、主要API/LIFF/朝通知の回帰確認）

