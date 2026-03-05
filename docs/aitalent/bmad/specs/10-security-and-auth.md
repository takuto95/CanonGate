# Spec: セキュリティ / 認証（現行と論点）

## 背景 / 目的
LINE連携・管理API・定時ジョブは外部から到達可能なため、認証/検証の境界を明確にする。

## 現行（確定しているもの）
- LINE受信（webhook/postback）は署名検証（`x-line-signature`）を行い、不正なら401
- 管理用push（`/api/line/push`）は内部認証（`INTERNAL_API_KEY`）を要求
- `/api/jobs/*` は内部認証（`INTERNAL_API_KEY`）を要求

## 補足
- ジョブは GitHub Actions から `Authorization: Bearer <INTERNAL_API_KEY>` で呼び出す
- `?key=` は実装上許容されるが、URL漏洩リスクがあるためジョブ用途では使わない

## 受入条件（Given/When/Then）
- Given: webhookに不正署名でリクエストが来る
- When: `/api/line/webhook` または `/api/line/postback` に到達する
- Then: 401が返り、処理されない

- Given: 内部認証なしで jobs にリクエストが来る
- When: `/api/jobs/*` に到達する
- Then: 401 が返る

