# archive — デスクトップ以外の起動方法

デスクトップ版（Electron）を主入口にするため、**ブラウザ起動用**のファイルをここに退避しています。

## 中身

| フォルダ | 説明 |
|----------|------|
| **simple-mode-client/** | 図形UIを **ブラウザ**（http://localhost:8765）で表示する版。`serve.py` でトークン発行＋静的配信。LiveKit 利用時用。 |

## 通常の起動（推奨）

図形だけの簡易モードは **デスクトップの Electron** で起動してください。

- **`simple-mode-desktop/`** に移動 → `npm install`（初回のみ）→ **`npm start`**
- またはルートで **`npm run simple-mode`**

詳細はルートの [README.md](../README.md) を参照。
