# BMAD Method ドキュメント（仕様の単一の真実）

このフォルダは **BMAD Method** に従って、仕様・判断・不足点を混在させずに管理するための置き場です。

- `spec-current.md`: 現行仕様（今の実装/ドキュメントから確定できる事実）をB/M/A/Dで整理
- `gaps.md`: 仕様として足りない点・未決定事項・例外系・非機能（優先度つき）
- `docs/rfcs/`: ADR/Specに落とす前段の提案（RFC: Request for Comments）
- `docs/adr/`: 設計上の意思決定（ADR: Architecture Decision Record）

運用ルール（混在防止）:
- **実装に合わせて更新する**のは `spec-current.md`
- **判断が必要/未確定**はすべて `gaps.md` に集約（決まったら `spec-current.md` に反映して gaps 側はクローズ）
- `docs/bmad-flow-plan.md` は「計画/ロードマップ」専用にして、仕様本文はここに置く
