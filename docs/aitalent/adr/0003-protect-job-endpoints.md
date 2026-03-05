# ADR 0003: /api/jobs/* エンドポイントの保護方針

- **Status**: Accepted
- **Date**: 2026-01-07
- **Deciders**: User（運用決定）
- **Related**: `docs/bmad/gaps.md`, `docs/bmad/specs/10-security-and-auth.md`, `vercel.json`

## Context
`/api/jobs/*` は定時実行（Vercel Cron）で利用しているが、現状は認証なしで到達可能なため以下のリスクがある。

- 任意実行による **スパムPush**（LINE APIの利用増、ユーザー体験の毀損）
- 任意実行による **コスト増**（DeepSeek/LINE/Sheets の呼び出し）
- 任意実行による **状態改変**（`sessions` 等への記録、タスク状態への影響）

一方で、Vercel Cron の仕組み上「特定のヘッダ/クエリの付与」「IP制限」などの制約があり、保護方式を誤ると cron が動かなくなる。

## Decision
以下を採用する。

- **Option D + Option A の組み合わせ**:
  - ジョブ実行基盤は GitHub Actions に移管する
  - `/api/jobs/*` は `INTERNAL_API_KEY` による内部認証を必須化する
    - `Authorization: Bearer <token>` または `x-internal-api-key: <token>` を推奨（URLクエリは使わない）

評価軸（例）:
- Cronを壊さないこと（運用性）
- 外部からの任意実行を防げること（安全性）
- 秘密情報の取り扱いが単純であること（漏洩時の影響を限定）
- 実装/移行コストが妥当であること

## Options Considered
- **Option A: `INTERNAL_API_KEY` 相当のキーを jobs にも要求（ヘッダ/クエリ）**
  - 例: `Authorization: Bearer ...` / `x-internal-api-key` / `?key=...`
  - 注意: Vercel Cron が確実にヘッダ付与できるか、ログ/URLにキーが残らないか

- **Option B: Vercel側の保護機能に寄せる（Cron/スケジューラ機能での認証）**
  - 例: Vercelの機能/設定で外部から直接叩けない形にする（可能なら最小変更）

- **Option C: IP allowlist（Cron送信元の固定IPを許可）**
  - 注意: 送信元IPが固定できない/変動する場合、運用が破綻する

- **Option D: 外部ジョブ実行基盤へ移管（GitHub Actions / Cloud Scheduler 等）**
  - 例: 外部から `INTERNAL_API_KEY` を付けて叩く、あるいは直接処理を移す
  - 注意: 運用部品が増える、監視/失敗時リトライが必要

- **Option E: /api/jobs を廃止し、処理を「イベント駆動（webhook起点）」に寄せる**
  - 注意: 要件（朝/週次のPush）と整合するか要検討

## Consequences
- **Positive**:
  - 任意実行リスクを下げ、コスト/スパムを抑制できる
  - 運用上の境界（外部到達可能/不可）が明確になる
- **Negative / Risks**:
  - Cron連携の制約により、方式によっては運用が不安定になる
  - 実装だけでなく秘密情報管理（キーの配布/ローテ）も必要になる
- **Operational notes**:
  - 方式確定後は、`docs/bmad/specs/10-security-and-auth.md` と `docs/bmad/spec-current.md` に反映し、`docs/bmad/gaps.md` をクローズする

## Follow-ups
- [ ] 保護方式を選定（このADRを Accepted にする）
- [ ] spec更新（`docs/bmad/spec-current.md` / `docs/bmad/specs/10-security-and-auth.md`）
- [ ] 実装タスク（jobsルートに保護を追加）
- [ ] 手動実行/cron実行の検証手順を追記（運用ドキュメント）
