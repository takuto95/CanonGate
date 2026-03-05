# Spec: 日報（dailyモード）

## 背景 / 目的
当日のタスク進捗（done/miss）を素早く記録し、終了時にサマリーと次の一手（評価/明日の焦点/見直し案/後続タスク）につなげる。

## スコープ
- **やること**
  - `#日報開始` で開始（todoを優先度順に2–3件表示、全件は `list`）
  - モード中は `done` / `miss` / `list` / `status` 等を受理
  - `#日報終了` でサマリー化し、DeepSeekで提案生成、必要なら後続タスク追加
  - `#再スケジュール作成` で提案から再スケジュール用タスクを作成
- **やらないこと（現行）**
  - 日報終了時の「見直し案」を自動適用（提案のみ）

## 入力形式
- **推奨（動詞が先）**
  - 完了: `done 1` / `完了 1`
  - 未達: `miss 2 理由` / `未達 2 理由`
- **逆順検知**
  - `1 done` のような逆順はエラーとして、正しい形式を提示する

## フロー（Given/When/Then）
- Given: 日報モードではない
- When: `#日報開始` を送る
- Then: todo一覧（2–3件）と入力例が返る

- Given: 日報モード中
- When: `done <番号|taskId>` を送る
- Then: tasks.status が done に更新され、成功/失敗が検証されて返信される

- Given: 日報モード中
- When: `miss <番号|taskId> <理由?>` を送る
- Then: tasks.status が miss に更新され、成功/失敗が検証されて返信される

- Given: 日報モード中
- When: `#日報終了` を送る
- Then:
  - サマリーが返信され、logsに追記される
  - DeepSeekで提案（評価/明日の焦点/見直し案/後続タスク）を生成して返信する
  - 後続タスク提案があれば tasks に todo で追加する
  - （Option A）章完了判定とサイド回収を行う:
    - **章完了**: `lane=main` かつ `chapterStage=1`（または未指定として扱う）の todo が0件になった章は `chapters.status=completed` に更新する
    - **サイド回収**: `lane=side` の todo のうち、`priority=A` または `dueDate` が3日以内のものを最大1件だけ `lane=main` に昇格する

## 例外 / エラーハンドリング（未決定含む）
- DeepSeek失敗時の最低保証（サマリーのみ返す等）は `docs/bmad/gaps.md` で協議する
- 「対象 1,3」の表示明示などUX整備は `docs/bmad/gaps.md`（UX項目）で協議/実装する

