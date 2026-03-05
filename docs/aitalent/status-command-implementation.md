# *status コマンド実装完了

## 概要
`*status` コマンドを実装し、ユーザーの現在の状態を包括的に表示できるようにしました。

## 実装内容

### 1. 新規ファイル
- **`lib/core/status-service.ts`**: ステータス情報を取得・整形するサービス
  - `getUserStatus()`: ユーザーの総合ステータスを取得
  - `formatStatusInfo()`: ステータス情報を読みやすいテキストに変換
  - ストリーク計算、推奨アクション生成機能

- **`app/api/status/route.ts`**: ステータス取得API
  - `GET /api/status?userId=<userId>&format=<text|json>`
  - テキスト形式またはJSON形式で返却

### 2. 更新ファイル
- **`.cursor/rules/bmad/bmad-orchestrator.mdc`**: `*status` コマンドの説明を更新
- **`app/api/line/webhook/route.ts`**: LINEからの `#ステータス` コマンド対応
  - `STATUS_COMMANDS` に `#ステータス`, `ステータス` を追加
  - `handleStatusCommand()` を新しいサービスに切り替え
- **`docs/bmad/spec-current.md`**: ステータス確認機能の仕様を追加

### 3. 表示内容
ステータスコマンドは以下の情報を表示します：

1. **パーソナライズ設定**
   - キャラクターロール
   - メッセージトーン
   - 表示名
   - 変更方法のガイド

2. **今日のタスク**
   - 朝の命令タスク（今日の焦点）
   - 重要なタスク（優先度A、期限が近いもの）

3. **ゴールと進捗**
   - アクティブゴール（最大5件）
   - 進捗バー表示
   - 完了件数/総件数

4. **タスクサマリー**
   - 残りタスク総数
   - 優先度別（A/B/C）
   - 期限切れタスク

5. **最近の活動**
   - 連続記録日数（ストリーク）
   - 直近3日の記録件数
   - 最近完了したタスク

6. **統計情報**
   - 今週の完了件数
   - 今月の完了件数
   - 全体の完了率

7. **推奨アクション**
   - 状況に応じた次のアクション提案
   - 期限切れタスクの警告
   - ストリーク継続の励まし
   - タスク分割の提案など

## 使い方

### BMAD Orchestrator（Cursor）
```
*status
```

### LINE
```
#ステータス
ステータス
#状態
状態
#status
```

### REST API
```bash
# テキスト形式
GET /api/status?userId=U123456&format=text

# JSON形式
GET /api/status?userId=U123456&format=json
```

## テスト状況
- TypeScriptコンパイル: ✅ 成功
- 既存機能への影響: ✅ なし（既存のhandleStatusCommandを置き換え）

## 今後の拡張可能性
- グラフ表示（週次・月次の完了推移）
- より詳細な行動パターン分析
- カスタマイズ可能な表示項目
- エクスポート機能（CSV, PDF）
