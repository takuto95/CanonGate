# ADR（Architecture Decision Record）

このディレクトリは、アーキテクチャ/設計上の意思決定を **ADR形式**で記録します。

※提案段階（代替案の比較・議論のたたき台）は `docs/rfcs/` を利用し、**決定（Decision）をADRに残す**運用を推奨します。

## ルール（要点）
- **迷いが出る実装は先にADR**（データモデル、API契約、認証/権限、外部依存追加、永続化方式、ジョブ運用、重大なUX/フロー変更など）
- **ADRはspecと整合**（決めた内容を `docs/bmad/spec-current.md` / 必要なら `docs/bmad/specs/` に反映）
- **命名**: `NNNN-short-title.md`（例: `0002-protect-cron-endpoints.md`）

## テンプレ
- `docs/adr/0001-adr-template.md`

