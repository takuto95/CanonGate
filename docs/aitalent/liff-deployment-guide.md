# LIFF アプリ デプロイガイド

このドキュメントでは、LIFFアプリ（タスク一覧画面）のセットアップとデプロイ方法を説明します。

## 前提条件

- LINE Developers アカウント
- LINE公式アカウント（Messaging API有効化済み）
- Vercel アカウント（または他のホスティングサービス）

---

## ステップ1: LIFF アプリの作成

### 1.1 LINE Developers コンソールにアクセス

1. https://developers.line.biz/console/ にアクセス
2. プロバイダーを選択
3. Messaging APIチャネルを選択

### 1.2 LIFF アプリを追加

1. **「LIFF」タブをクリック**
2. **「追加」ボタンをクリック**
3. **設定を入力**:
   - **LIFFアプリ名**: `TaskFlow - タスク一覧`
   - **サイズ**: `Full`（全画面表示）
   - **エンドポイントURL**: `https://your-app.vercel.app/liff/tasks.html`
     - ⚠️ デプロイ後に正しいURLに置き換える
   - **Scope**: 
     - ✅ `profile`（ユーザー情報取得）
     - ✅ `chat_message.write`（メッセージ送信）
   - **ボットリンク機能**: `On (Aggressive)` または `On (Normal)`
   - **Scan QR**: `Off`（必要に応じて）

4. **「追加」をクリック**

### 1.3 LIFF IDをコピー

作成後、LIFF IDが表示されます（例: `2008835190-F0ZpGhEt`）。このIDを控えておきます。

---

## ステップ2: コードにLIFF IDを設定

### 2.1 LIFF アプリのHTMLを更新

`public/liff/tasks.html` の以下の行を更新：

```javascript
const liffId = '2008835190-F0ZpGhEt';
```

### 2.2 リッチメニュー設定を更新

`lib/line/rich-menu-config.ts` の以下の行を更新：

```typescript
uri: 'https://liff.line.me/2008835190-F0ZpGhEt'
```

---

## ステップ3: Vercel にデプロイ

### 3.1 Vercelプロジェクトの作成

**方法1: Vercel CLI（推奨）**

```bash
# Vercel CLIをインストール
npm install -g vercel

# ログイン
vercel login

# デプロイ
vercel

# プロダクションデプロイ
vercel --prod
```

**方法2: GitHub連携**

1. GitHubリポジトリにプッシュ
2. Vercelダッシュボードで「New Project」
3. GitHubリポジトリを選択
4. 「Deploy」をクリック

### 3.2 環境変数の設定

Vercelダッシュボードで以下の環境変数を設定：

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `LINE_USER_ID`
- `DEEPSEEK_API_KEY`
- `GOOGLE_CLIENT_EMAIL`
- `GOOGLE_PRIVATE_KEY`
- `SHEETS_SPREADSHEET_ID`
- `INTERNAL_API_KEY`

### 3.3 デプロイURLを確認

デプロイ完了後、VercelからURLが発行されます（例: `https://your-app.vercel.app`）。

---

## ステップ4: LIFF エンドポイントURLを更新

### 4.1 LINE Developers コンソールで更新

1. LINE Developers コンソールを開く
2. LIFFタブを選択
3. 作成したLIFFアプリを編集
4. **エンドポイントURL** を実際のURLに更新:
   - `https://your-app.vercel.app/liff/tasks.html`
5. 「更新」をクリック

---

## ステップ5: リッチメニューを設定

### 5.1 リッチメニュー画像を準備

`docs/rich-menu-image-guide.md` を参考に、リッチメニュー画像を作成します。

- サイズ: 2500x1686px（6ボタン）
- フォーマット: PNG/JPEG
- ファイル名: `rich-menu.png`
- 保存先: `public/rich-menu.png`

### 5.2 リッチメニューを登録

```bash
# 画像を配置
cp /path/to/rich-menu.png public/

# リッチメニューを作成・登録
npm run setup-rich-menu
```

### 5.3 動作確認

1. LINE公式アカウントのトーク画面を開く
2. 画面下部にリッチメニューが表示されているか確認
3. 「📋 タスク一覧」ボタンをタップ
4. LIFFアプリが開くか確認

---

## ステップ6: 動作確認

### 6.1 LIFFアプリのテスト

1. **LINEアプリでLIFFを開く**
   - リッチメニューの「タスク一覧」をタップ
   - または、LIFF URLを直接開く: `https://liff.line.me/2008835190-F0ZpGhEt`

2. **タスク一覧が表示されるか確認**
   - タスクカードが表示される
   - 優先度・期限・ゴール情報が正しく表示される

3. **ボタン操作をテスト**
   - 「✅ 完了」ボタンをタップ
   - LINEトークに `done <taskId>` が送信される
   - 日報モードでタスクが完了扱いになるか確認

4. **スワイプ操作をテスト**
   - タスクカードを左にスワイプ → 完了
   - タスクカードを右にスワイプ → 未達

5. **フィルタ機能をテスト**
   - 「優先度A」ボタンをタップ → Aタスクのみ表示
   - 「期限近い」ボタンをタップ → 3日以内のタスクのみ表示

---

## ステップ7: トラブルシューティング

### LIFFアプリが開かない

**原因1**: LIFF IDが間違っている

**解決策**:
- `public/liff/tasks.html` のLIFF IDを確認
- LINE Developers コンソールでLIFF IDを確認

**原因2**: エンドポイントURLが間違っている

**解決策**:
- LINE Developers コンソールで正しいURLを設定
- `https://your-app.vercel.app/liff/tasks.html` の形式か確認

### タスクが表示されない

**原因**: API エンドポイントにアクセスできない

**解決策**:
- ブラウザの開発者ツールでエラーを確認
- `/api/tasks` エンドポイントが正しく動作しているか確認
- CORSエラーが出ていないか確認

### ボタンをタップしてもメッセージが送信されない

**原因**: `chat_message.write` スコープが有効になっていない

**解決策**:
- LINE Developers コンソールでLIFFの設定を確認
- Scope に `chat_message.write` がチェックされているか確認

---

## オプション設定

### A. LIFF アプリのカスタマイズ

**配色の変更:**

`public/liff/tasks.html` の `<style>` セクションで色を変更：

```css
/* 背景グラデーション */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* ボタンの色 */
.btn-done {
  background: #10b981; /* 緑 */
}

.btn-miss {
  background: #6b7280; /* グレー */
}
```

**フォントの変更:**

```css
body {
  font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, sans-serif;
}
```

### B. 統計情報の追加

`public/liff/tasks.html` のヘッダーに追加情報を表示：

- 週間の完了件数
- 連続記録日数（ストリーク）
- ゴール進捗

### C. 検索機能の追加

タスクを検索できる機能を追加：

```javascript
// 検索フィールドを追加
<input type="text" id="search" placeholder="タスクを検索...">

// 検索処理
function filterBySearch(query) {
  return allTasks.filter(t => 
    t.description.toLowerCase().includes(query.toLowerCase())
  );
}
```

---

## Next.js の静的エクスポート設定

もしNext.jsの静的エクスポートを使用する場合、`next.config.mjs` に以下を追加：

```javascript
const nextConfig = {
  output: 'export', // 静的エクスポート
  trailingSlash: true, // URLの末尾にスラッシュを追加
  images: {
    unoptimized: true // 画像最適化を無効化
  }
};

export default nextConfig;
```

ただし、現在のプロジェクトは API Routes を使用しているため、静的エクスポートは推奨しません。Vercel/Netlify等のサーバーレス環境を使用してください。

---

## チェックリスト

デプロイ前に以下を確認：

- [ ] LIFF IDを取得して `tasks.html` に設定
- [ ] LIFF IDを `rich-menu-config.ts` に設定
- [ ] Vercelにデプロイ完了
- [ ] 環境変数を正しく設定
- [ ] LIFF エンドポイントURLを更新
- [ ] リッチメニューを登録
- [ ] LIFFアプリが開くか確認
- [ ] タスク一覧が表示されるか確認
- [ ] ボタン操作が動作するか確認
- [ ] スワイプ操作が動作するか確認

---

## 参考リンク

- **LINE LIFF ドキュメント**
  https://developers.line.biz/ja/docs/liff/overview/

- **Vercel デプロイガイド**
  https://vercel.com/docs/deployments/overview

- **Next.js デプロイガイド**
  https://nextjs.org/docs/deployment

- **LINE Messaging API**
  https://developers.line.biz/ja/docs/messaging-api/overview/
