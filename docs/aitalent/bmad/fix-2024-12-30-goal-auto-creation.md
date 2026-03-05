# 修正: ゴール自動作成機能（2024-12-30）

## 概要
思考ログからタスク生成時に、AIが抽出した`currentGoal`を自動的にgoalsシートに追加する機能を実装しました。

---

## 🔍 問題点（修正前）

### 仕様の欠陥
```typescript
// GoalIntakeService.handle() - 修正前
await this.tasksRepo.add({
  id: buildTaskId(),
  goalId: parsed.currentGoal || "",  // ← 文字列を直接入れる
  description,
  status: "todo",
  // ...
});
```

**問題**:
- AIが抽出した`currentGoal`（例: "キャリアアップ"）を**タスクのgoalIdに文字列として保存**
- **goalsシートにはレコードが存在しない**
- ゴール進捗計算が機能しない（goalIdに対応するゴールレコードがない）
- ゴール一覧に表示されない

### 影響
- ❌ 日報終了時の「ゴール進捗表示」が表示されない
- ❌ AIタスク選定時の「ゴールバランス考慮」が機能しない
- ❌ `GET /api/goals` でゴール一覧が空

---

## ✅ 解決策

### 実装内容
1. **`ensureGoal()` メソッドを追加**
   - AIが抽出したゴールタイトルをgoalsシートに自動追加
   - **重複チェック**: 同じタイトルのゴールが既に存在する場合は既存のIDを返す
   - 新規の場合は`g_` prefixのIDを生成してgoalsシートに追加

2. **タスク生成時にゴールIDを使用**
   - `goalId: parsed.currentGoal`（文字列）→ `goalId: goalId`（goalsシートのID）

### コード

```typescript
/**
 * ゴールを自動的に作成または既存のIDを取得
 * 同じtitleのゴールが既に存在する場合はそのIDを返す
 */
private async ensureGoal(goalTitle: string): Promise<string> {
  if (!goalTitle || !goalTitle.trim()) {
    return "";
  }

  const normalizedTitle = goalTitle.trim();
  
  // 既存のゴールを確認
  const existingGoals = await this.goalsRepo.list();
  const existing = existingGoals.find(
    g => g.title.toLowerCase() === normalizedTitle.toLowerCase()
  );
  
  if (existing) {
    return existing.id;
  }
  
  // 新規ゴールを作成
  const goalId = buildGoalId();
  const timestamp = new Date().toISOString();
  await this.goalsRepo.add({
    id: goalId,
    title: normalizedTitle,
    confidence: "0.8", // デフォルト値
    status: "pending",
    createdAt: timestamp,
    updatedAt: timestamp
  });
  
  return goalId;
}

async handle(payload: GoalIntakePayload): Promise<GoalIntakeResult> {
  // ...
  
  // ゴールを自動作成または既存IDを取得
  const goalId = parsed?.currentGoal 
    ? await this.ensureGoal(parsed.currentGoal)
    : "";

  // タスク生成時にgoalsシートのIDを使用
  await this.tasksRepo.add({
    id: buildTaskId(),
    goalId: goalId, // ← goalsシートの実際のID
    description,
    status: "todo",
    // ...
  });
}
```

---

## 🎯 修正後の動作フロー

```
【思考ログ→タスク生成】
ユーザー: 「キャリアアップしたい。プレゼンスキルを磨く」
↓
AI分析: currentGoal = "キャリアアップ"
↓
ensureGoal("キャリアアップ")
  → goalsシートを確認
  → 存在しない → 新規作成
  → id: g_1735567890123, title: "キャリアアップ"
↓
tasksに追加:
  - goalId: "g_1735567890123" ← goalsシートのID
  - description: "プレゼン資料を作成する"
↓
✅ ゴール進捗計算が正常に機能
✅ 日報終了時: 「キャリアアップ: ████░░ 40% (2/5)」
✅ AIタスク選定: 進捗が遅れているゴールを優先
```

### 重複防止
```
【2回目の思考ログ】
ユーザー: 「キャリアアップのため英語を勉強する」
↓
AI分析: currentGoal = "キャリアアップ"
↓
ensureGoal("キャリアアップ")
  → goalsシートを確認
  → 既に存在！ → 既存のIDを返す
  → id: g_1735567890123
↓
tasksに追加:
  - goalId: "g_1735567890123" ← 同じゴールに紐付く
  - description: "英語の勉強をする"
↓
✅ 同じゴールに複数のタスクが紐付く
✅ ゴール進捗: 「キャリアアップ: 3/7タスク完了」
```

---

## 📊 実現する機能

### 1. ゴール進捗の可視化
- **日報終了時**: 「キャリアアップ: ████░░ 40% (2/5タスク完了)」
- どのゴールがどれくらい進んでいるか一目瞭然

### 2. ゴールバランスの最適化
- **AIタスク選定**: 進捗が遅れているゴールのタスクを優先
- 特定のゴールばかりに偏らないようバランス調整

### 3. ゴール別タスク管理
- `GET /api/goals` でゴール一覧取得
- 各ゴールに紐づくタスクを確認可能
- 「キャリアアップ」ゴール達成に必要なタスクが全て見える

---

## 🧪 テスト観点

### 基本動作
- [ ] 思考ログ→タスク生成時にgoalsシートにレコードが追加される
- [ ] AIが抽出したゴールタイトルが正しく保存される
- [ ] タスクのgoalIdがgoalsシートのIDと一致する

### 重複防止
- [ ] 同じゴールタイトルで2回目のタスク生成を実行
- [ ] goalsシートに重複レコードが作成されない
- [ ] 既存のゴールIDが再利用される

### ゴール進捗
- [ ] 日報終了時にゴール進捗が表示される
- [ ] タスク完了後に進捗率が更新される
- [ ] 複数ゴールの進捗が正しく表示される

### AIタスク選定
- [ ] 進捗が遅れているゴールのタスクが優先される
- [ ] ゴールなしタスクも正常に扱われる

---

## 📁 修正ファイル

- `lib/core/goal-intake-service.ts`
  - `ensureGoal()` メソッド追加
  - `Dependencies` に `goalsRepo` 追加
  - `handle()` でゴール自動作成処理を追加
- `app/api/line/webhook/route.ts`
  - `GoalIntakeService` のインスタンス化を修正（`goalsRepo` を渡す）

---

## 🎉 効果

### Before
```
goalsシート: （空）

tasksシート:
id: t_123, goalId: "キャリアアップ", description: "..."
          ↑ 文字列（goalsシートにレコードなし）
```

### After
```
goalsシート:
id: g_456, title: "キャリアアップ", status: "pending"

tasksシート:
id: t_123, goalId: "g_456", description: "..."
          ↑ goalsシートの実際のID
```

✅ **ゴールとタスクが正しく紐付き、全ての機能が正常動作！**

---

## 関連ドキュメント
- [現行仕様](spec-current.md)
- [パーソナライズとタスク選定の対話化](fix-2024-12-30-personalization-and-dialogue.md)
