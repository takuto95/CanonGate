# Flex Message テスト手順

このドキュメントでは、実装したFlexメッセージ（リッチメッセージ）をLINE公式の**Flex Message Simulator**でテスト・確認する方法を説明します。

## 1. Flex Message Simulatorとは？

LINE公式が提供する、Flexメッセージのデザインをブラウザ上でプレビュー・編集できるツールです。

**URL**: https://developers.line.biz/flex-simulator/

## 2. テスト用JSON

以下のJSONをコピーして、Flex Message Simulatorに貼り付けてください。

### 朝の命令メッセージ（基本版）

```json
{
  "type": "bubble",
  "header": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": "🎯 今日の焦点",
        "weight": "bold",
        "color": "#1DB446",
        "size": "md"
      }
    ],
    "backgroundColor": "#F0FFF0",
    "paddingAll": "md"
  },
  "hero": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": "プレゼン資料を作成する",
        "weight": "bold",
        "size": "xl",
        "wrap": true,
        "color": "#2C3E50"
      }
    ],
    "backgroundColor": "#FFFFFF",
    "paddingAll": "xl"
  },
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "box",
        "layout": "baseline",
        "contents": [
          {
            "type": "text",
            "text": "🎯",
            "size": "sm",
            "flex": 0
          },
          {
            "type": "text",
            "text": "キャリアアップ",
            "size": "sm",
            "color": "#666666",
            "flex": 1,
            "margin": "sm",
            "wrap": true
          }
        ],
        "margin": "md"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": "優先度:",
                "size": "sm",
                "color": "#999999",
                "flex": 0
              },
              {
                "type": "text",
                "text": "A",
                "size": "sm",
                "color": "#FF6B6B",
                "weight": "bold",
                "margin": "sm",
                "flex": 0
              }
            ],
            "flex": 1
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": "期限:",
                "size": "sm",
                "color": "#999999",
                "flex": 0
              },
              {
                "type": "text",
                "text": "2026-01-03",
                "size": "sm",
                "color": "#FF6B6B",
                "weight": "bold",
                "margin": "sm",
                "flex": 0
              }
            ],
            "flex": 1
          }
        ],
        "margin": "md"
      },
      {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "💡 AI選定理由",
            "size": "xs",
            "color": "#999999",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "優先度Aで期限が明日。ゴール進捗が40%と遅れているため、このタスクを優先すべきです。",
            "size": "xs",
            "color": "#666666",
            "wrap": true,
            "margin": "xs"
          }
        ],
        "margin": "lg",
        "backgroundColor": "#F8F9FA",
        "paddingAll": "sm",
        "cornerRadius": "md"
      },
      {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "📊 今日の傾向",
            "size": "xs",
            "color": "#999999",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "月曜は完了率が高い！チャレンジングなタスクもいけそうです。朝は集中力が高い時間帯。重要なタスクに取り組みましょう。",
            "size": "xs",
            "color": "#666666",
            "wrap": true,
            "margin": "xs"
          }
        ],
        "margin": "lg",
        "backgroundColor": "#FFF8E1",
        "paddingAll": "sm",
        "cornerRadius": "md"
      }
    ],
    "paddingAll": "xl"
  },
  "footer": {
    "type": "box",
    "layout": "vertical",
    "spacing": "sm",
    "contents": [
      {
        "type": "button",
        "style": "primary",
        "height": "sm",
        "action": {
          "type": "postback",
          "label": "✅ 今すぐ開始",
          "data": "action=start_task&taskId=t_1234567890",
          "displayText": "✅ このタスクに取り組みます"
        },
        "color": "#1DB446"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {
              "type": "postback",
              "label": "⏰ 後で",
              "data": "action=snooze_task&taskId=t_1234567890",
              "displayText": "⏰ 後でやります"
            },
            "flex": 1
          },
          {
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {
              "type": "postback",
              "label": "🔄 変更",
              "data": "action=change_task",
              "displayText": "変更"
            },
            "flex": 1
          }
        ]
      }
    ],
    "paddingAll": "xl"
  }
}
```

### 朝の命令メッセージ（シンプル版・ゴールなし）

```json
{
  "type": "bubble",
  "header": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": "🎯 今日の焦点",
        "weight": "bold",
        "color": "#1DB446",
        "size": "md"
      }
    ],
    "backgroundColor": "#F0FFF0",
    "paddingAll": "md"
  },
  "hero": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "text",
        "text": "メールの返信をする",
        "weight": "bold",
        "size": "xl",
        "wrap": true,
        "color": "#2C3E50"
      }
    ],
    "backgroundColor": "#FFFFFF",
    "paddingAll": "xl"
  },
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": "優先度:",
                "size": "sm",
                "color": "#999999",
                "flex": 0
              },
              {
                "type": "text",
                "text": "B",
                "size": "sm",
                "color": "#FFA500",
                "weight": "bold",
                "margin": "sm",
                "flex": 0
              }
            ],
            "flex": 1
          },
          {
            "type": "box",
            "layout": "baseline",
            "contents": [
              {
                "type": "text",
                "text": "期限:",
                "size": "sm",
                "color": "#999999",
                "flex": 0
              },
              {
                "type": "text",
                "text": "なし",
                "size": "sm",
                "color": "#666666",
                "margin": "sm",
                "flex": 0
              }
            ],
            "flex": 1
          }
        ],
        "margin": "md"
      }
    ],
    "paddingAll": "xl"
  },
  "footer": {
    "type": "box",
    "layout": "vertical",
    "spacing": "sm",
    "contents": [
      {
        "type": "button",
        "style": "primary",
        "height": "sm",
        "action": {
          "type": "postback",
          "label": "✅ 今すぐ開始",
          "data": "action=start_task&taskId=t_9876543210",
          "displayText": "✅ このタスクに取り組みます"
        },
        "color": "#1DB446"
      },
      {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {
              "type": "postback",
              "label": "⏰ 後で",
              "data": "action=snooze_task&taskId=t_9876543210",
              "displayText": "⏰ 後でやります"
            },
            "flex": 1
          },
          {
            "type": "button",
            "style": "link",
            "height": "sm",
            "action": {
              "type": "postback",
              "label": "🔄 変更",
              "data": "action=change_task",
              "displayText": "変更"
            },
            "flex": 1
          }
        ]
      }
    ],
    "paddingAll": "xl"
  }
}
```

## 3. テスト手順

1. **Flex Message Simulatorを開く**
   - https://developers.line.biz/flex-simulator/

2. **JSONを貼り付ける**
   - 左側の「JSON」タブにある編集エリアに、上記のJSONをコピー&ペースト

3. **プレビューを確認**
   - 右側にリアルタイムでプレビューが表示される
   - スマートフォンのサイズで表示される

4. **デザインを調整**
   - JSONの値を変更すると、プレビューが即座に更新される
   - 色（`color`）、サイズ（`size`）、余白（`margin`, `padding`）などを調整可能

5. **実機テスト**
   - Simulatorの「Share」ボタンでQRコードを生成
   - スマホでQRコードを読み取ると、LINE上でプレビュー可能

## 4. 主要なカスタマイズポイント

### 色の変更

```json
{
  "type": "text",
  "text": "テキスト",
  "color": "#1DB446"  // ← ここを変更（LINE緑: #1DB446、赤: #FF6B6B）
}
```

### ボタンの色

```json
{
  "type": "button",
  "style": "primary",
  "color": "#1DB446"  // ← ここを変更
}
```

### 優先度の色設定

- **優先度A**: `#FF6B6B`（赤）
- **優先度B**: `#FFA500`（オレンジ）
- **優先度C**: `#4ECDC4`（シアン）
- **未設定**: `#999999`（グレー）

### 期限が近い場合の強調

期限が3日以内の場合、期限テキストを赤色＋太字で表示：

```json
{
  "type": "text",
  "text": "2026-01-03",
  "color": "#FF6B6B",
  "weight": "bold"
}
```

## 5. よくある調整

### タスク説明が長い場合

```json
{
  "type": "text",
  "text": "非常に長いタスク説明が入る場合でも、wrap:trueで自動折り返しされます",
  "wrap": true,  // ← 必須
  "maxLines": 3  // ← オプション（3行まで表示、それ以上は省略）
}
```

### ボタンを1つにしたい場合

footerの`contents`配列から不要なボタンを削除：

```json
"footer": {
  "type": "box",
  "layout": "vertical",
  "contents": [
    {
      "type": "button",
      "style": "primary",
      "action": { ... }
    }
    // 他のボタンを削除
  ]
}
```

## 6. デバッグのコツ

### JSONエラーが出る場合

- カンマ（`,`）の位置を確認（最後の要素にカンマは不要）
- クォート（`"`）の閉じ忘れをチェック
- オンラインのJSON Lintを使う: https://jsonlint.com/

### プレビューが崩れる場合

- `flex`プロパティのバランスを調整（合計が均等になるように）
- `paddingAll`, `margin`の値を調整（`xs`, `sm`, `md`, `lg`, `xl`）

## 7. 実装への反映

Simulatorで確認したデザインを実装に反映する場合：

1. `lib/line/flex-messages.ts` の `buildMorningTaskFlexMessage` 関数を編集
2. JSON構造をTypeScriptのオブジェクトに変換
3. 動的な値（タスク情報、ゴール名など）を変数で埋め込む

## 8. 参考リンク

- **LINE Messaging API - Flex Message**
  https://developers.line.biz/ja/docs/messaging-api/using-flex-messages/

- **Flex Message Simulator**
  https://developers.line.biz/flex-simulator/

- **Flex Message デザインガイドライン**
  https://developers.line.biz/ja/docs/messaging-api/flex-message-design-guidelines/

---

## 次のステップ

デザインが確定したら、以下を実施：
1. Vercel/本番環境にデプロイ
2. LINE公式アカウントの朝の命令（`/api/jobs/morning`）を手動実行してテスト
3. ボタンのpostback動作を確認（`/api/line/postback`のログを確認）
4. ユーザーフィードバックを収集して微調整
