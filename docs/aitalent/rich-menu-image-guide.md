# リッチメニュー画像作成ガイド

このドキュメントでは、LINE公式アカウントに設定するリッチメニュー画像の作成方法を説明します。

## 画像仕様

### 基本要件
- **サイズ**: 2500x1686px（6ボタンレイアウト）または 2500x843px（4ボタンレイアウト）
- **フォーマット**: PNG または JPEG
- **最大ファイルサイズ**: 1MB
- **カラーモード**: RGB

### 推奨設定
- **解像度**: 72dpi（Web用）
- **背景色**: 白（#FFFFFF）またはブランドカラー
- **テキスト色**: 濃い色（#2C3E50など）で視認性を確保

---

## レイアウト: 6ボタン版（2行3列）

### 全体サイズ: 2500x1686px

```
┌──────────────┬──────────────┬──────────────┐
│              │              │              │
│  🎯 今日の   │  📋 タスク   │  ✅ 完了     │
│   タスク     │   一覧       │   報告       │
│              │              │              │
│  833x843px   │  834x843px   │  833x843px   │
├──────────────┼──────────────┼──────────────┤
│              │              │              │
│  📊 ステータ │  💭 思考     │  ❓ ヘルプ   │
│   ス         │   ログ       │              │
│              │              │              │
│  833x843px   │  834x843px   │  833x843px   │
└──────────────┴──────────────┴──────────────┘
```

### 各ボタンの座標

| ボタン | 位置 | X座標 | Y座標 | 幅 | 高さ |
|--------|------|-------|-------|-----|------|
| 今日のタスク | 左上 | 0 | 0 | 833 | 843 |
| タスク一覧 | 中上 | 833 | 0 | 834 | 843 |
| 完了報告 | 右上 | 1667 | 0 | 833 | 843 |
| ステータス | 左下 | 0 | 843 | 833 | 843 |
| 思考ログ | 中下 | 833 | 843 | 834 | 843 |
| ヘルプ | 右下 | 1667 | 843 | 833 | 843 |

---

## レイアウト: 4ボタン版（1行4列）

### 全体サイズ: 2500x843px

```
┌──────────┬──────────┬──────────┬──────────┐
│          │          │          │          │
│ 🎯 今日の│📋 タスク │✅ 完了   │📊 ステー │
│  タスク  │  一覧    │  報告    │  タス    │
│          │          │          │          │
│ 625x843  │ 625x843  │ 625x843  │ 625x843  │
└──────────┴──────────┴──────────┴──────────┘
```

---

## デザインガイドライン

### 1. テキストスタイル

**推奨フォント:**
- **日本語**: Noto Sans JP（Bold）、ヒラギノ角ゴ（W6）
- **英数字**: Roboto（Bold）、SF Pro（Semibold）

**フォントサイズ:**
- **絵文字**: 80-100px
- **メインテキスト**: 50-60px
- **サブテキスト**: 30-40px

**テキスト配置:**
- 中央揃え（縦横）
- 上部に絵文字、下部にテキスト

### 2. 色の使い方

**背景色:**
- 白（#FFFFFF）: シンプルで読みやすい
- 淡いグレー（#F8F9FA）: 落ち着いた印象
- ブランドカラー: 統一感を出す

**テキスト色:**
- 濃いグレー（#2C3E50）: 視認性が高い
- 黒（#000000）: コントラスト重視

**アクセントカラー:**
- 緑（#10B981）: 完了・ポジティブアクション
- 青（#3B82F6）: 情報・ナビゲーション
- オレンジ（#F59E0B）: 注意・重要

### 3. 境界線

**推奨設定:**
- 線の太さ: 2-3px
- 色: 薄いグレー（#E5E7EB）
- スタイル: 実線

ボタンの境界を明確にして、タップしやすくする。

---

## Figmaテンプレート

### 新規作成手順

1. **Figmaを開く**
   - https://www.figma.com/

2. **新規ファイルを作成**
   - サイズ: 2500x1686px

3. **グリッドを設定**
   - 列: 3列（833px, 834px, 833px）
   - 行: 2行（各843px）

4. **各ボタンを配置**
   - 矩形ツールで各ボタンエリアを作成
   - 背景色を設定（白または淡いグレー）
   - 境界線を追加（2px、#E5E7EB）

5. **テキストを追加**
   - 絵文字: 80px（中央上部）
   - テキスト: 50px（中央下部）

6. **エクスポート**
   - PNG形式
   - 2x解像度（5000x3372px）
   - 縮小して2500x1686pxに調整

---

## Canvaテンプレート

### 作成手順

1. **Canvaを開く**
   - https://www.canva.com/

2. **カスタムサイズを選択**
   - 幅: 2500px
   - 高さ: 1686px

3. **グリッドを配置**
   - 要素 → 線 → グリッド
   - 3列2行に調整

4. **各ボタンを作成**
   - 図形 → 矩形
   - サイズ調整（833x843px等）
   - 背景色と境界線を設定

5. **絵文字とテキストを追加**
   - テキストツールで絵文字を入力
   - フォントサイズを調整

6. **ダウンロード**
   - PNG形式
   - 推奨品質（高解像度）

---

## オンラインツール

### 簡易作成ツール

**LINE公式ツール（非公式）:**
- https://line-richimage-generator.netlify.app/
- ブラウザ上で作成可能
- テキスト・色を選択するだけで生成

**Photopea（無料Photoshop代替）:**
- https://www.photopea.com/
- PSD形式対応
- オンラインで完結

---

## サンプル画像の作成方法（HTMLベース）

簡易的なリッチメニュー画像をHTMLで生成する方法：

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body { margin: 0; padding: 0; }
    .rich-menu {
      width: 2500px;
      height: 1686px;
      display: grid;
      grid-template-columns: 833px 834px 833px;
      grid-template-rows: 843px 843px;
      background: white;
      font-family: 'Hiragino Sans', sans-serif;
    }
    .button {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      border: 2px solid #E5E7EB;
      background: white;
      color: #2C3E50;
    }
    .button:hover {
      background: #F8F9FA;
    }
    .emoji {
      font-size: 100px;
      margin-bottom: 20px;
    }
    .text {
      font-size: 50px;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <div class="rich-menu">
    <div class="button">
      <div class="emoji">🎯</div>
      <div class="text">今日のタスク</div>
    </div>
    <div class="button">
      <div class="emoji">📋</div>
      <div class="text">タスク一覧</div>
    </div>
    <div class="button">
      <div class="emoji">✅</div>
      <div class="text">完了報告</div>
    </div>
    <div class="button">
      <div class="emoji">📊</div>
      <div class="text">ステータス</div>
    </div>
    <div class="button">
      <div class="emoji">💭</div>
      <div class="text">思考ログ</div>
    </div>
    <div class="button">
      <div class="emoji">❓</div>
      <div class="text">ヘルプ</div>
    </div>
  </div>
</body>
</html>
```

**スクリーンショット手順:**
1. 上記HTMLをブラウザで開く
2. ブラウザのズームを100%に設定
3. スクリーンショットツールで2500x1686pxで切り取る
4. PNG形式で保存

---

## チェックリスト

デザイン完成前に以下を確認：

- [ ] サイズが正確（2500x1686px または 2500x843px）
- [ ] ファイルサイズが1MB以下
- [ ] PNG/JPEG形式で保存
- [ ] 各ボタンの境界が明確
- [ ] テキストが読みやすい（フォントサイズ・色）
- [ ] 絵文字が正しく表示される
- [ ] ボタンの座標が正しい（タップ領域と一致）

---

## 実装手順

画像作成後、以下の手順で設定：

1. **画像を配置**
   ```bash
   # 画像を public/ に保存
   cp rich-menu.png /workspace/public/
   ```

2. **スクリプトを実行**
   ```bash
   npm run setup-rich-menu
   ```

3. **確認**
   - LINE公式アカウントのトーク画面を開く
   - メニューが表示されているか確認
   - 各ボタンをタップして動作確認

---

## トラブルシューティング

### 画像がアップロードできない

**原因**: ファイルサイズが1MBを超えている

**解決策**:
- 画像を圧縮（TinyPNG: https://tinypng.com/）
- JPEG形式に変更（品質80-90%）

### ボタンがタップできない

**原因**: 座標設定が間違っている

**解決策**:
- `lib/line/rich-menu-config.ts` の `bounds` を確認
- 画像の境界線とタップ領域が一致しているか確認

### メニューが表示されない

**原因**: デフォルト設定がされていない

**解決策**:
```bash
npm run setup-rich-menu -- --skip-image
```

---

## 参考リンク

- **LINE Messaging API - リッチメニュー**
  https://developers.line.biz/ja/docs/messaging-api/using-rich-menus/

- **リッチメニュー画像デザインガイドライン**
  https://developers.line.biz/ja/docs/messaging-api/rich-menu-design-guidelines/

- **Figma（デザインツール）**
  https://www.figma.com/

- **Canva（デザインツール）**
  https://www.canva.com/
