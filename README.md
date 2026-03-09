# CanonGate (formerly EgoGate / LiveTalkAiAgent) - Canon Unified Hub

音声・テキストで会話するデスクトップアプリです。マスコット（VRM）表示と TTS はブラウザ／Electron で再生されます。**Canon** リポジトリの `Canon/` と同階層に配置し、`RunAlterEgo.bat` で起動します。

### Canon / CanonGate を別 Git リポジトリにしている場合

**結論: 影響なし（同じ親フォルダに両方 clone していれば）。**

- Canon と CanonGate は **別々の Git リポジトリ** でよく、コード上は **「同じ親ディレクトリの下に `Canon` と `CanonGate` が並んでいる」** という前提だけ満たせば動きます。
- 例: `c:\work\Canon` と `c:\work\CanonGate` にそれぞれ clone → `RunAlterEgo.bat` の `..\Canon` や、Canon 側の `BASE_DIR.parent / "CanonGate"` が正しく解決します。
- **別々の場所**に clone した場合（例: Canon は `c:\repos\Canon`、CanonGate は `d:\apps\CanonGate`）は、相対パスが壊れます。そのときは環境変数 `CANON_ROOT`（Canon のルート）と `CANONGATE_DIR`（CanonGate のルート）を設定すると、一部スクリプト（例: zaim_guardian）でパスを上書きできます。Commander API や RunAlterEgo.bat は現状「同じ親」前提のままなので、**運用では同じ親の下に両方置く**ことを推奨します。

**参照先（clone 例）**
- Canon: `git clone git@github.com:takuto95/Canon.git`
- CanonGate: `git clone git@github.com:takuto95/CanonGate.git`

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

4. **環境変数（tech ドメイン＝仕事用で音声応答するために必須）**  
   - **`GROQ_API_KEY`**: CanonGate の LLM（クラウド・高速応答）に Groq を使う場合に必須。  
     - 取得: [Groq Console](https://console.groq.com/) でサインアップ → API Keys で「Create API Key」→ 発行されたキーをコピー。  
     - 設定: **`Canon/.env`** に次の 1 行を追加する（CanonGate は起動時に Canon の `.env` も読みに行きます）。  
       ```env
       GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
       ```  
     - 未設定だと音声入力後の LLM 応答でエラーになります。  
   - 任意: `GROQ_MODEL=llama-3.3-70b-versatile`（デフォルトのままでも可）、`WS_PORT=8082`（Commander API とポートを揃えたいとき）。  
   - プライベート（life）のみ使う場合は、Ollama ローカルで完結するため `GROQ_API_KEY` は不要です。

## 起動方法

### 簡易モード（図形のみ・デスクトップ）— 推奨

**Electron** でデスクトップに小窓を出し、図形＋音声ON/OFF で対話するモードです。

- **`cd simple-mode-desktop`** → **`npm install`**（初回のみ）→ **`npm start`**
- またはルートで **`npm run simple-mode`**

Electron が simple_chat.py を自動起動し、約2秒後に窓が表示されます。詳細は **`simple-mode-desktop/README.md`** を参照。

### マスコット版（VRM 表示）

- **`RunAlterEgo.bat`** をダブルクリック（CanonGate 起動）  
  - 同階層の `Canon/` で Commander API と ALE を起動したうえで、Electron でマスコットウィンドウ＋ Python（simple_chat.py）を起動。約 12 秒後にウィンドウ表示。  
  - **ALE はデフォルトで仕事（tech）のみ**。プライベート（life）も回す場合は `RunAlterEgo.bat dual` で起動。
- **`CanonGate_Silent.vbs`** で起動した場合  
  - 起動時に **tech / life / dual** の入力ダイアログが出ます。選んだドメインに応じて ALE と simple_chat が動きます。未入力・Cancel は tech。他端末でプライベートだけ使う場合は **life** を選べばよい。

### デスクトップ以外の起動（参考）

ブラウザ起動やデバッグ用のファイルは **`archive/`** に移しています。必要なら `archive/README.md` を参照。

## フォルダ構成

| ファイル／フォルダ | 説明 |
|-------------------|------|
| **`simple-mode-desktop/`** | **簡易モード（図形）を Electron でデスクトップ起動 — メインの入口** |
| `RunAlterEgo.bat` | CanonGate 起動（Commander API + ALE + Electron + Python） |
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
