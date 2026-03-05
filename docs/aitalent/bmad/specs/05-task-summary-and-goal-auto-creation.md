# Spec: タスク整理（#タスク整理）/ ゴール自動作成

## 背景 / 目的
終了済みの思考ログセッションから、タスクを生成し、必要ならゴールも作成する。

## スコープ
- **やること**
  - `#タスク整理` で「直近の終了済みlogセッション」を対象にタスク生成
  - logsに1件（要約/構造化結果）、tasksに複数件（todo）を追加
  - AI抽出 `currentGoal` をもとに goals を自動作成（重複チェック）
  - tasksは goals の **実ID** を `goalId` に保存
- **やらないこと（未決定/要協議）**
  - 同一ログに対して `#タスク整理` を複数回許可するか（現状は拒否、方針は `docs/bmad/gaps.md` で協議）

## フロー（Given/When/Then）
- Given: 直近に終了済みの思考ログセッションがある
- When: `#タスク整理` を送る
- Then: logsに1件、tasksに1件以上が追加され、返信にログID等の参照情報が含まれる

## ゴール自動作成
- Given: AIが `currentGoal` を抽出した
- When: goalsに同名titleが存在するかチェックする
- Then:
  - 存在する: 既存goalのIDを使う
  - 存在しない: `g_` prefixのIDで新規作成し、そのIDを tasks.goalId に設定する

## 例外 / エラーハンドリング
- DeepSeek失敗時の扱いは `docs/bmad/gaps.md` で協議する

