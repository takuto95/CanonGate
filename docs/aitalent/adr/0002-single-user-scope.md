# ADR 0002: 単一ユーザー運用（まずはLINE_USER_ID固定）

- **Status**: Accepted
- **Date**: 2026-01-07
- **Deciders**: User（運用決定）
- **Related**: `docs/bmad/spec-current.md`, `docs/bmad/gaps.md`

## Context
現状の実装・運用は `LINE_USER_ID` を中心にPushや各種処理を行う前提が混ざっている。
一方、webhookには `source.userId` があり、マルチユーザー対応を始めると設計・運用が広範囲に影響する。

## Decision
当面は **単一ユーザー運用** とし、基本方針を以下に固定する。

- **運用対象ユーザーは1人**（Push先は `LINE_USER_ID` を前提）
- マルチユーザー対応は **必要が出たタイミングで再協議**し、別ADRで方針を決める

## Options Considered
- Option A: 単一ユーザーで固定（今回採用）
- Option B: webhook `source.userId` を主キーにしてマルチユーザー化
- Option C: ハイブリッド（source.userIdで受信、Pushは運用で指定）

## Consequences
- **Positive**:
  - 仕様・運用がシンプルで、初期コストが低い
  - 既存の前提（`LINE_USER_ID`）と整合しやすい
- **Negative / Risks**:
  - 将来マルチユーザー化する際に、データ/セッション/認証/権限の設計変更が発生する
- **Operational notes**:
  - マルチユーザー化検討が必要になったら、まず `gaps.md` に論点を整理し、ADRを追加する

## Follow-ups
- [ ] `docs/bmad/gaps.md` の「ユーザー識別/マルチユーザー方針」をクローズ（本ADR参照）
- [ ] `docs/bmad/spec-current.md` に「単一ユーザー運用」の明記を追加（SSoT）

