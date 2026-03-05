# Spec: データモデル / Google Sheets スキーマ

## 背景 / 目的
本システムの永続化はGoogle Sheetsで行う。協議・実装・デバッグの共通言語として、データモデルとシート構造を明文化する。

## 用語
- **Sheet**: Google Spreadsheet内のタブ（`goals` 等）
- **Row**: 各データ行
- **ID**: `g_`（goal）, `t_`（task）などのprefixを持つ文字列

## データモデル
### Goal
- `id`: string
- `title`: string
- `confidence`: number|string（現行は文字列で保存される可能性あり）
- `status`: `pending | approved | archived`（現行は主に `pending` 作成）
- `createdAt`, `updatedAt`: ISO文字列想定

### Chapter
- `id`: string
- `goalId`: string（Goalへの参照）
- `title`: string
- `order`: number|string（章順。文字列で保存される可能性あり）
- `status`: string（例: `active | completed`）
- `hook`: string（次の展開/予告。空可）
- `createdAt`, `updatedAt`: ISO文字列想定

### Task
- `id`: string
- `goalId`: string（Goalへの参照）
- `chapterId`: string（Chapterへの参照、空可）
- `lane`: string（例: `main | side`、空可）
- `chapterStage`: string（例: `1|2|3...`、空可）
- `description`: string
- `status`: 主に `todo | done | miss`
- `dueDate`: string（YYYY-MM-DD想定 / 空可）
- `priority`: `A | B | C` 想定（空/不明可）
- `assignedAt`: ISO文字列想定 / 空可
- `sourceLogId`: string（タスク生成元ログID）

### Log
- `id`: string
- `timestamp`: ISO文字列想定
- `userId`: string
- `rawText`: string（サマリー含む場合あり）
- `emotion`, `coreIssue`, `currentGoal`, `todayTask`, `warning`: string（空可）

### SessionEvent（sessions）
- `sessionId`: string
- `userId`: string
- `type`: string（例: start/user/assistant/daily_update/morning_order/task_started/task_snoozed/task_review 等）
- `content`: string
- `timestamp`: ISO文字列
- `meta`: JSON文字列（mode等）

### UserSettings（user_settings）
- `userId`: string
- `characterRole`: string（例: default/ceo/heir/athlete/scholar）
- `messageTone`: string（例: strict/formal/friendly）
- `displayName`: string
- `createdAt`, `updatedAt`: ISO文字列想定
- `focusGoalId`: string（空可）
- `focusChapterId`: string（空可）
- `focusUpdatedAt`: ISO文字列（空可）

## Google Sheets スキーマ（シート）
SSoT: `docs/bmad/spec-current.md` の「永続化（Google Sheets スキーマ）」に準拠。

- `goals`: `id,title,confidence,status,createdAt,updatedAt`
- `chapters`: `id,goalId,title,order,status,hook,createdAt,updatedAt`
- `tasks`: `id,goalId,chapterId,lane,chapterStage,description,status,dueDate,priority,assignedAt,sourceLogId`
- `logs`: `id,timestamp,userId,rawText,emotion,coreIssue,currentGoal,todayTask,warning`
- `sessions`: `sessionId,userId,type,content,timestamp,meta`
- `user_settings`: `userId,characterRole,messageTone,displayName,createdAt,updatedAt,focusGoalId,focusChapterId,focusUpdatedAt`

## 受入条件（Given/When/Then）
- Given: シートが上記ヘッダを持つ
- When: API/LINE操作により追加・更新が行われる
- Then: 追加/更新後の再取得で値が整合し、日報更新などの後続処理が前提とする語彙（例: `todo/done/miss`）が維持される

