# ADR 0010: GitHub Actionsジョブ分割（制約撤廃・提案は自動/確定はボタン）

- **Status**: Accepted
- **Date**: 2026-01-14
- **Deciders**: Product / Engineering
- **Related**:
  - `docs/adr/0003-protect-job-endpoints.md`（/api/jobs/* 保護）
  - `docs/adr/0009-github-actions-jobs-4h-cadence.md`（4時間枠のガードレール）
  - `docs/bmad/spec-current.md`（ジョブ/通知・button-first）
  - `docs/bmad/specs/08-jobs-and-notifications.md`

## Context
従来は運用制約（Cron本数など）を前提に、ジョブを `/api/jobs/cadence` に集約していた。
しかし GitHub Actions に移行したことで、ジョブ本数の制約を実質撤廃できる。

一方で、日報を送らない日もあるため「日報終了に依存したタスク見直し」だけでは不十分であり、
日次で“本当にこのタスクで良いか”を見直す仕組みが必要になった。
ただし、タスクの更新を自動確定すると誤爆のコストが大きいので、**確定はボタン**に統一する。

## Decision
以下を採用する。

1) **ジョブは用途別に分割してよい（GitHub Actionsワークフローも分割）**
- `/api/jobs/*` のエンドポイントは用途別に追加してよい。
- GitHub Actionsワークフローは、用途別に分割してよい（本数上限を前提にしない）。

2) **日次のタスク見直しを“提案ジョブ”として追加する**
- ジョブは自動で見直し案を生成し、ユーザーへ提示する。
- **反映（保存）は必ずボタン（message action / postback）で確定**し、自動適用はしない。

3) **4時間枠cadenceのガードレールは維持する**
- ジョブ本数の制約は撤廃しても、ユーザー体験（しつこさ）とコストのため、ADR 0009の送信上限・間引き方針は維持する。

## Consequences
- **Positive**:
  - 日報を送らない日でも、翌朝に“整理の機会”が発生し復帰しやすい。
  - 確定をボタンに統一することで誤爆の救済が容易（ログも追える）。
  - スケジュールの変更や追加がやりやすくなる。
- **Negative / Risks**:
  - ワークフローが増えるため運用・監視対象は増える（失敗時の通知/可視化が必要）。

