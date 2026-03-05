# タスク更新失敗検知の修正（2024-12-30）

## 問題の概要

ユーザーから「タスク `t_1766122744120_1` を報告したがレコード上完了になっていない」という報告を受けた。

## 原因分析

### 発見されたバグ

`app/api/line/webhook/route.ts` の以下3箇所で、**タスク更新が失敗しても成功メッセージを返してしまう**致命的なバグを発見：

1. **日報モードの done コマンド**（1022-1048行目）
2. **日報モードの miss コマンド**（1051-1078行目）
3. **夜報告の完了/未達コマンド**（294-341行目）

#### 具体的な問題

- `updateStatus` の戻り値（boolean）を確認していない
- Google Sheets API エラーが発生しても、成功メッセージを返してしまう
- 更新が実際に成功したか検証していない

### 発生シナリオ

以下のいずれかの理由で更新が失敗した可能性：

1. **タスクIDが実際には存在しなかった**
   - `updateStatus` が `false` を返したが、ユーザーには成功と伝わった

2. **Google Sheets API の一時的なエラー**
   - ネットワークエラー、レート制限、認証エラーなど
   - エラーは発生したが、汎用的なエラーメッセージしか返らなかった

3. **入力形式の問題**
   - done コマンドが正しく解釈されなかった
   - 日報モードがアクティブでなかった

## 実装した対策

### 1. 更新成否の検証

```typescript
// 更新を試行し、結果を検証
let updateSuccess = false;
try {
  updateSuccess = await storage.tasks.updateStatus(taskId, "done");
} catch (error) {
  // Sheets API エラーを個別に捕捉
  console.error("[daily_done] updateStatus failed", { taskId, error });
  await replyText(replyToken, "完了登録に失敗した... ストレージエラーが発生した...");
  return NextResponse.json({ ok: false, note: "storage_error" });
}

if (!updateSuccess) {
  // updateStatus が false を返した場合
  console.warn("[daily_done] updateStatus returned false", { taskId });
  await replyText(replyToken, "完了登録に失敗した... タスクが見つからない...");
  return NextResponse.json({ ok: false, note: "update_failed" });
}
```

### 2. 更新後の状態確認

```typescript
// 更新後の状態を確認
const updated = await storage.tasks.findById(taskId);
if (updated && updated.status !== "done") {
  console.error("[daily_done] status verification failed", {
    taskId,
    expectedStatus: "done",
    actualStatus: updated.status
  });
  await replyText(replyToken, "完了登録の検証に失敗した... ストレージの整合性に問題がある...");
  return NextResponse.json({ ok: false, note: "verification_failed" });
}
```

### 3. 詳細なエラーメッセージ

- ユーザーに失敗理由を明確に伝える
- 再試行方法を提示する
- タスクIDを含めて、どのタスクで失敗したか特定可能にする

### 4. ログの強化

```typescript
console.log("[daily_done] success", { taskId, description: task.description });
console.warn("[daily_done] updateStatus returned false", { taskId });
console.error("[daily_done] updateStatus failed", { taskId, error });
console.error("[daily_done] status verification failed", { taskId, expectedStatus, actualStatus });
```

### 5. 新機能: タスクステータス確認コマンド

ユーザーがタスクの現在の状態を確認できるコマンドを追加：

```
status <taskId>
ステータス <taskId>
確認 <taskId>
```

**出力例:**
```
【タスク情報】
ID: t_1766122744120_1
ステータス: todo
説明: レポートを作成する
優先度: A
期限: 2024-12-31
割当日時: 2024-12-30T10:00:00Z
ソースログ: daily_1766122700000
```

## テストシナリオ

### シナリオ1: 正常系（done コマンド）

**Given:**
- 日報モードがアクティブ
- タスク `t_test_1` が `todo` 状態で存在する

**When:**
- ユーザーが `done t_test_1` を送信

**Then:**
- `updateStatus` が `true` を返す
- タスクの status が `done` になる
- ユーザーに「✅完了登録: {説明}」が返る
- ログに `[daily_done] success` が記録される

### シナリオ2: 異常系（タスクが存在しない）

**Given:**
- 日報モードがアクティブ
- タスク `t_invalid` が存在しない

**When:**
- ユーザーが `done t_invalid` を送信

**Then:**
- `findById` が `null` を返す
- ユーザーに「タスクID「t_invalid」は見つからない。IDを再確認しろ。」が返る
- 更新処理は実行されない

### シナリオ3: 異常系（更新失敗）

**Given:**
- 日報モードがアクティブ
- タスク `t_test_1` が存在する
- `updateStatus` が何らかの理由で `false` を返す

**When:**
- ユーザーが `done t_test_1` を送信

**Then:**
- ユーザーに「完了登録に失敗した: {説明}」が返る
- 再試行方法が提示される（「もう一度 list で確認してから done t_test_1 を送れ」）
- ログに `[daily_done] updateStatus returned false` が記録される

### シナリオ4: 異常系（Sheets API エラー）

**Given:**
- 日報モードがアクティブ
- タスク `t_test_1` が存在する
- Google Sheets API が一時的にエラーを返す

**When:**
- ユーザーが `done t_test_1` を送信

**Then:**
- try-catch でエラーを捕捉
- ユーザーに「完了登録に失敗した... ストレージエラーが発生した...」が返る
- ログに `[daily_done] updateStatus failed` とエラー詳細が記録される

### シナリオ5: 新機能（status コマンド）

**Given:**
- タスク `t_test_1` が存在する

**When:**
- ユーザーが `status t_test_1` を送信

**Then:**
- タスクの詳細情報（ID、ステータス、説明、優先度、期限など）が返る
- ユーザーが現在の状態を確認できる

## 影響範囲

### 修正したファイル

1. `app/api/line/webhook/route.ts`
   - `handleDailyMessage` 内の done/miss 処理
   - `tryHandleQuickNightReport` 内の夜報告処理
   - 新コマンド: タスクステータス確認

2. `docs/bmad/spec-current.md`
   - 日報モードの更新処理に検証機能を追記
   - 夜報告の更新処理に検証機能を追記
   - 新コマンド `status <taskId>` を追記

3. `docs/bmad/gaps.md`
   - 「タスク更新失敗の検知と通知」を完了としてマーク
   - 受入条件に更新成否の挙動を追記

### 互換性

- **破壊的変更なし**: 既存のコマンド形式は変更なし
- **新機能追加**: `status <taskId>` コマンド
- **エラーメッセージの改善**: より詳細で実用的なメッセージに

## 今後の課題

1. **リトライメカニズム**
   - 一時的なネットワークエラーの場合、自動リトライを検討

2. **トランザクション**
   - `recordDailyUpdate` と `updateStatus` の順序を保証
   - 片方が成功してもう片方が失敗した場合のロールバック

3. **監視とアラート**
   - 更新失敗の頻度を監視
   - 管理者への通知機能

4. **テスト自動化**
   - 統合テストの追加（モック環境）
   - エッジケースの網羅的なテスト

## まとめ

今回の修正により、ユーザーが報告した「タスクを報告したのに完了にならない」という問題が**次回から発生しない**ようになりました。

- ✅ 更新の成否を確認
- ✅ 失敗時に詳細なエラーメッセージ
- ✅ 再試行方法の提示
- ✅ ログの強化
- ✅ タスク状態確認コマンドの追加

ユーザーは今後、更新が失敗した場合に即座に気づき、適切に対処できるようになります。
