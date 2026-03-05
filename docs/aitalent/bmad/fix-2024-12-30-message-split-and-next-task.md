# 修正: メッセージ分割と次タスク案内（2024-12-30）

## 概要
思考ログと日報のUX改善を実施しました。

## 変更内容

### 1. 思考ログのメッセージ分割
**問題**: やり取りが増えると、感情・要約・提案・質問が1つのメッセージに詰まって読みづらい

**解決策**: LINEの`replyMessages`機能を使い、AIの返信を3つに分割

#### 分割の構成
1. **1つ目**: 感情の共感（`parsed.emotion`）
2. **2つ目**: 現状の整理（`parsed.aiSummary`）と気づきの提案（`parsed.aiSuggestion`）
3. **3つ目**: 核心を突く質問（`parsed.userNextStep`）

#### 実装
```typescript
function buildThoughtReplyMessages(parsed: ThoughtAnalysis | null, aiRaw: string): string[] {
  if (!parsed) {
    return [compactReplyLines([
      "ちょっと整理がうまくいかなかった。",
      "もう一度、今の気持ちを送ってくれる？",
      "",
      aiRaw || "(AI出力が空でした)"
    ])];
  }

  const messages: string[] = [];
  
  // 1つ目: 感情の共感
  if (parsed.emotion) {
    messages.push(parsed.emotion);
  }
  
  // 2つ目: 現状の整理
  const summaryParts: string[] = [];
  if (parsed.aiSummary) {
    summaryParts.push(parsed.aiSummary);
  }
  if (parsed.aiSuggestion) {
    summaryParts.push("", parsed.aiSuggestion);
  }
  if (summaryParts.length > 0) {
    messages.push(compactReplyLines(summaryParts));
  }
  
  // 3つ目: 核心を突く質問
  const nextStep = parsed.userNextStep || "それで、本当はどう感じてる？";
  messages.push(nextStep);

  return messages.filter(Boolean);
}
```

#### 使用箇所
- `handleSessionMessage`: 通常の思考ログ会話
- `handleInactiveMessage`: 自動で思考ログモードを開始した場合

---

### 2. done報告時の次タスク案内
**問題**: 日報終了時にしか進捗確認とサマリーが出ない。日中に完了した場合、もう1件こなせる可能性があるのに案内がない。

**解決策**: `done`コマンド実行時に残りのtodoを確認し、次のタスクを自動で提示

#### フロー
1. ユーザーが`done 1`を送信
2. タスクを完了状態に更新
3. 残りのtodoを確認
   - **残りがある場合**: 次のタスクを提示（「💪 もう1件いける？」）
   - **全タスク完了**: 「🎉 全タスク完了！」と表示

#### 実装
```typescript
// 次タスク案内（モチベーション向上）
const { todos, displayed } = await resolveDisplayedTodoList(session);
const remainingTodos = displayed.filter(t => t.id !== taskId); // 今完了したタスクを除外

const messages = [doneMessage];

if (remainingTodos.length > 0) {
  // 次のタスクを提示（優先度順で最初の1件）
  const nextTask = remainingTodos[0];
  const nextIndex = todos.findIndex(t => t.id === nextTask.id);
  const displayNumber = nextIndex >= 0 ? nextIndex + 1 : "?";
  const priority = nextTask.priority || "-";
  
  const nextMessages = [
    "💪 もう1件いける？",
    "",
    `次のタスク:`,
    `${displayNumber}) [${priority}] ${nextTask.description}`,
    "",
    `やるなら: done ${displayNumber}`,
    `今日はここまで: ${DAILY_END_KEYWORD}`
  ];
  messages.push(nextMessages.join("\n"));
} else {
  // 全タスク完了！
  messages.push(
    [
      "",
      "🎉 全タスク完了！",
      `今日の報告を締めるなら: ${DAILY_END_KEYWORD}`
    ].join("\n")
  );
}

await replyTexts(replyToken, messages);
```

#### メッセージ例
**ケース1: 残りのタスクがある場合**
```
✅ よくやった！
プレゼン資料を作成する

---

💪 もう1件いける？

次のタスク:
2) [A] 報告書をレビューする

やるなら: done 2
今日はここまで: #日報終了
```

**ケース2: 全タスク完了した場合**
```
✅ 完璧だ！
報告書をレビューする

---

🎉 全タスク完了！
今日の報告を締めるなら: #日報終了
```

---

## 影響範囲

### 修正ファイル
- `app/api/line/webhook/route.ts`
  - `buildThoughtReplyMessages()`: 新規追加（メッセージ分割用）
  - `handleSessionMessage()`: `replyTexts`に変更
  - `handleInactiveMessage()`: `replyTexts`に変更（自動思考ログモード開始時）
  - `handleDailyMessage()`: done時の次タスク案内を追加

### 更新ドキュメント
- `docs/bmad/spec-current.md`
  - 思考ログのメッセージ分割を追記
  - done時の次タスク案内を追記

---

## テスト観点

### 思考ログのメッセージ分割
- [ ] 思考ログモード開始後、ユーザーがメッセージを送ると3つに分割されて返ってくる
- [ ] 自動で思考ログモードが開始された場合も分割される
- [ ] AIのJSON解析に失敗した場合もエラーメッセージが返る

### done報告時の次タスク案内
- [ ] `done 1`を送信すると、完了メッセージ + 次タスク案内が返る
- [ ] 残りtodoが0件の場合、「🎉 全タスク完了！」が表示される
- [ ] 日報対象を絞り込んでいる場合も正しく次タスクが表示される
- [ ] 次タスクの番号は全件基準で正しい

---

## 今後の改善案
- [ ] 思考ログの分割数を動的に調整（長い場合は4〜5分割）
- [ ] done後の「もう1件いける？」の条件を時刻で調整（夜遅い場合は出さない）
- [ ] ユーザーの完了ペースを学習し、次タスクの提示タイミングを最適化

---

## 関連Issue/PR
- 関連する修正: `fix-2024-12-30-improved-ux.md`（日報開始時のメッセージ分割）
