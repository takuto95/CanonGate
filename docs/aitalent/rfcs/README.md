# RFC（Request for Comments）

## 目的
ADR（Decision）とSpec（仕様）に落とす前段として、**提案（Proposal）と議論のたたき台**を残す。

## 位置づけ（推奨フロー）
- **gaps**（未決定の索引）: `docs/bmad/gaps.md`
- **RFC**（提案/比較/移行案）: `docs/rfcs/`
- **ADR**（最終決定の記録）: `docs/adr/`
- **Spec**（現行仕様SSoT）: `docs/bmad/spec-current.md` / `docs/bmad/specs/`

目安:
- 小さな論点 → `gaps.md` に残してその場で決める
- 代替案や影響範囲が大きい論点 → RFCを作ってから決める（決定はADRへ）

## 運用
- 命名: `NNNN-short-title.md`（例: `0001-protect-job-endpoints.md`）
- RFCは **提案**なので、採択後は必ず
  - ADRにDecisionを残す（Accepted）
  - Specに「どう動くか」を反映する

## テンプレ
- `docs/rfcs/0001-rfc-template.md`
