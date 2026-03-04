# EgoGate (formerly LiveTalkAiAgent) - Alter-Ego Unified Hub

音声・テキストで会話するデスクトップアプリです。マスコット（VRM）表示と TTS はブラウザ／Electron で再生されます。

## 初回セットアップ

1. **npm パッケージ（Electron）のインストール**  
   - デスクトップアプリ起動時に `RunAlterEgo.bat` が自動で `npm install` を実行します。  
   - 手動で行う場合: このフォルダで `npm install`

2. **VRM モデルの用意**  
   - `DownloadVrmModel.bat` を実行 → `mascot-web\test.vrm` にサンプルがダウンロードされます。  
   - または任意の VRM ファイルを `mascot-web\test.vrm` として配置してください。

3. **Python 依存関係**  
   - 初回のみ: `pip install -r requirements.txt`  
   - 詳細は `DebugStart.bat` でエラーになったときに実施してください。

## 起動方法

### 簡易モード（図形のみ・デスクトップ）— 推奨

**Electron** でデスクトップに小窓を出し、図形＋音声ON/OFF で対話するモードです。

- **`cd simple-mode-desktop`** → **`npm install`**（初回のみ）→ **`npm start`**
- またはルートで **`npm run simple-mode`**

Electron が simple_chat.py を自動起動し、約2秒後に窓が表示されます。詳細は **`simple-mode-desktop/README.md`** を参照。

### マスコット版（VRM 表示）

- **`RunAlterEgo.bat`** をダブルクリック  
  - Electron でマスコットウィンドウ＋ Python（simple_chat.py）を起動。約 12 秒後にウィンドウ表示。

### デスクトップ以外の起動（参考）

ブラウザ起動やデバッグ用のファイルは **`archive/`** に移しています。必要なら `archive/README.md` を参照。

## フォルダ構成

| ファイル／フォルダ | 説明 |
|-------------------|------|
| **`simple-mode-desktop/`** | **簡易モード（図形）を Electron でデスクトップ起動 — メインの入口** |
| `RunAlterEgo.bat` | マスコット版デスクトップ起動（Electron + Python） |
| `simple_chat.py` | 会話エンジン（Whisper STT, Ollama, Edge TTS, WebSocket） |
| `main.js` | マスコット版 Electron メイン（ルートで npm start 時） |
| `mascot-web/` | マスコット UI（VRM 表示用） |
| `archive/` | デスクトップ以外の起動（ブラウザ版など）を退避。必要時のみ参照。 |

## トラブルシュート

- **Electron の画面（窓）が出てこない**
  - **図形のみ（推奨）**: `cd simple-mode-desktop` → `npm install`（初回のみ）→ **`npm start`**
  - **マスコット版**: ルートで **`RunAlterEgo.bat`** または **`npm start`**
  - `python simple_chat.py` だけでは窓は開きません。Electron が simple_chat.py を自動起動するため、先に手動で simple_chat.py を実行しないでください（ポート競合の原因になります）。

- **言った言葉が正しく認識されない**
  - 音声認識は **Whisper**（デフォルト `small`）です。精度を優先しており、遅いと感じる場合は `set WHISPER_MODEL_SIZE=tiny` で起動すると軽くなります（精度は落ちます）。
  - よく聞き間違える語は **`simple_chat.py`** の **`STT_DRIFT_CORRECTIONS`** に `("聞こえた誤り", "正しい語")` を追加すると補正されます。report やメモに残した「誤認識リスト」をここに反映すると便利です。

- **応答が遅い**
  - **Ollama** はすでに **非同期**（aiohttp ストリーミング）です。**音声認識**はデフォルト `small`（精度優先）。軽くするなら `set WHISPER_MODEL_SIZE=tiny`。
  - まだ遅い場合は **Ollama のモデルを軽くする**と効きます。例: `set OLLAMA_MODEL=tinyllama` または `set OLLAMA_MODEL=phi` で起動してください。

- **音が出ない**  
  - デスクトップアプリの場合はウィンドウで「スタート」をクリックしてから利用してください。  
  - ブラウザ起動の場合は、mascot-web を開いたタブで「スタート」を押し、WebSocket が接続されていることを確認してください。

- **ポート 8080 が使われている**  
  - `simple_chat.py` の `WS_PORT` を環境変数で変更できます。  
  - 例: `set WS_PORT=8081` のうえで起動。`mascot-web/index.html` の WebSocket のポートも 8081 に合わせて変更してください。

- **VRM が表示されない**  
  - `mascot-web\test.vrm` が存在するか確認し、なければ `DownloadVrmModel.bat` を実行してください。
