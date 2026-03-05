# パーソナライズとタスク選定の対話化（2024-12-30）

## 概要
ユーザーの責任感を高め、状況に応じた柔軟なタスク選定を可能にする大規模改善を実施しました。

## 主な変更

### 1. **パーソナライズ機能**
ユーザーがキャラクターロールとメッセージトーンを選択できるようになりました。

#### キャラクターロール
- `default`: デフォルト（鬼コーチ）
- `ceo`: 社長（「社長、今日の経営課題は...」）
- `heir`: 御曹司（「若様、今日の修行は...」）
- `athlete`: アスリート（「選手、今日のトレーニングは...」）
- `scholar`: 研究者（「博士、今日の研究テーマは...」）

#### メッセージトーン
- `strict`: 厳格（「〜しろ」「〜だ」）- 現行デフォルト
- `formal`: 敬語（「〜してください」「〜です」）
- `friendly`: フレンドリー（「〜しよう」「〜だね」）

#### 設定方法
```
#設定                    # 現在の設定を表示
#設定 キャラクター 社長   # キャラクターを変更
#設定 トーン 敬語         # トーンを変更
#設定 名前 田中           # 表示名を設定
```

#### 実装ファイル
- `lib/personalization.ts`: トーン変換とキャラクターカスタマイズ
- `lib/storage/repositories.ts`: `UserSettingsRecord`, `CharacterRole`, `MessageTone`
- `lib/storage/sheets-repository.ts`: `SheetsUserSettingsRepository`
- `app/api/line/webhook/route.ts`: `handleSettingsCommand()`, `replyPersonalized()`

#### データモデル
新シート `user_settings`:
```
userId, characterRole, messageTone, displayName, createdAt, updatedAt
```

---

### 2. **朝の命令の対話化**
朝のタスク提示に対して、ユーザーが変更を要求できるようになりました。

#### フロー
```
1. 朝のタスク自動Push（AIが最適なタスクを選定）
   ↓
2. 「このタスクでOK？変更希望なら『変更』と送って」
   ↓
3. ユーザーが「変更」と返信
   ↓
4. 候補タスク3件を提示（または条件指定）
   ↓
5. ユーザーが番号で選択 or 「今日は休む」
   ↓
6. 選択されたタスクを morning_order に記録
```

#### 条件指定
- `スマホのみ`: 読む/調べる/考えるタスクに絞り込み
- `軽いタスク`: 優先度B/Cのタスクに絞り込み
- `今日は休む`: タスクなしで記録

#### 実装
- `app/api/line/webhook/route.ts`:
  - `handleMorningTaskChange()`: 候補タスク提示
  - `tryHandleMorningTaskSelection()`: タスク選択処理
- `app/api/jobs/morning/route.ts`: 対話機能の追加

---

### 3. **AI によるスマートタスク選定**
朝のタスク選定時に、以下を考慮してAIが最適なタスクを選びます。

#### 考慮要素
1. **期限が近いタスク**（3日以内）は優先
2. **優先度A** は重視するが、Aばかりに偏らないようバランスを取る
3. **ゴールの進捗**が遅れているゴールのタスクを優先
4. **最近の傾向**（missが続いている場合は軽めのタスクを）

#### 実装
- `lib/prompts.ts`: `buildSmartTaskSelectionPrompt()`
- `app/api/jobs/morning/route.ts`: `selectSmartTask()`

#### 出力形式
```json
{
  "primary": {
    "taskId": "t_123",
    "reason": "期限が明日に迫っており、ゴール進捗が40%と遅れているため"
  },
  "alternatives": [
    { "taskId": "t_456", "reason": "優先度Aだが期限に余裕あり" },
    { "taskId": "t_789", "reason": "スマホで可能な軽めのタスク" }
  ]
}
```

AIが失敗した場合は従来通り優先度順で先頭を選択します。

---

## 影響範囲

### 新規ファイル
- `lib/personalization.ts`: パーソナライズ機能
- `docs/bmad/fix-2024-12-30-personalization-and-dialogue.md`: このドキュメント

### 修正ファイル
- `lib/storage/repositories.ts`: UserSettings型追加
- `lib/storage/sheets-repository.ts`: UserSettingsRepository追加
- `lib/prompts.ts`: スマートタスク選定プロンプト追加
- `app/api/line/webhook/route.ts`: 設定コマンド、パーソナライズ、朝タスク変更
- `app/api/jobs/morning/route.ts`: AIタスク選定、パーソナライズ、対話機能

### 更新ドキュメント
- `docs/bmad/spec-current.md`: 仕様に反映（次のステップ）

---

## データベース変更

### 新シート: `user_settings`
```
userId         | characterRole | messageTone | displayName | createdAt           | updatedAt
---------------|---------------|-------------|-------------|---------------------|---------------------
user_12345     | ceo           | formal      | 田中        | 2024-12-30T10:00:00 | 2024-12-30T10:00:00
```

初回使用時に自動作成されます。

---

## テスト観点

### パーソナライズ
- [ ] `#設定` で現在の設定が表示される
- [ ] `#設定 キャラクター 社長` でキャラクターが変更される
- [ ] `#設定 トーン 敬語` でトーンが変更される
- [ ] 次のメッセージから変更が反映される（「〜しろ」→「〜してください」）
- [ ] 朝のメッセージに「社長、今日の経営課題」と表示される

### 朝の命令対話化
- [ ] 朝のメッセージに「このタスクでOK？変更希望なら...」が表示される
- [ ] 「変更」と送ると候補タスク3件が提示される
- [ ] 「スマホのみ」と送るとスマホ可能なタスクに絞られる
- [ ] 「今日は休む」と送るとタスクなしで記録される
- [ ] 番号を送ると選択したタスクが morning_order に記録される

### AIタスク選定
- [ ] 期限が近いタスクが優先的に選ばれる
- [ ] ゴール進捗が遅れているゴールのタスクが選ばれる
- [ ] 選定理由が朝のメッセージに表示される
- [ ] AIが失敗しても従来通りの選定にフォールバックする

---

## 今後の改善案
- [ ] キャラクターロールごとに専用プロンプトを用意（よりロールに沿った応答）
- [ ] AIタスク選定の精度向上（ユーザーの行動パターン学習）
- [ ] パーソナライズ設定のプリセット（「初心者向け」「ストイック」など）
- [ ] 朝のタスク変更履歴を記録し、ユーザーの好みを学習

---

## 関連Issue/PR
- 関連する修正: `fix-2024-12-30-message-split-and-next-task.md`（メッセージ分割と次タスク案内）
