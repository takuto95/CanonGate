# LiveTalk 簡易モード — デスクトップ版（Electron）

ブラウザではなく **Electron** のデスクトップ窓で簡易モードを開きます。**1 コマンド**で **simple_chat.py**（会話エンジン）を起動し、窓を開きます。

## 前提

- **Node.js** と **Python 3**
- ルートで `pip install -r requirements.txt` 済み（simple_chat.py の依存関係）
- **Ollama** がインストール済みで、必要なら `ollama run llama3.2` 済み

## 起動（1 コマンド）

```powershell
cd LiveTalkAiAgent\simple-mode-desktop
npm install
npm start
```

- Electron が **simple_chat.py** をバックグラウンドで起動します（約2秒後に窓が表示されます）。
- 小窓に図形＋音声ON/OFF の簡易モード UI が表示され、WebSocket (localhost:8080) で simple_chat.py と通信します。
- アプリを終了すると simple_chat.py も終了します。

## ルートから起動

LiveTalkAiAgent のルートで:

```powershell
npm run simple-mode
```

（ルートの package.json に `"simple-mode": "npm start --prefix simple-mode-desktop"` を追加済み）

## まとめ

| やること | コマンド |
|----------|----------|
| 初回のみ | `cd simple-mode-desktop` → `npm install` |
| 起動 | `npm start`（simple-mode-desktop 内）または ルートで `npm run simple-mode` |

**注意**: 窓を出すには **Electron を起動**（`npm start`）してください。`python simple_chat.py` だけでは窓は出ません。

---

## 音が聞こえないとき

1. **画面を一度クリックする**  
   ブラウザの仕様で、ユーザー操作がないと音声再生がブロックされます。窓内の**円**または「ここか円をクリック…」の部分を**1回クリック**してから話しかけてください。

2. **「音声」トグルが ON か確認**  
   緑になっていれば ON です。OFF（グレー）のときは音は出ません。

3. **Windows の再生デバイス**  
   音声は **Windows の既定の再生デバイス**（スピーカー／ヘッドホン）から出ます。  
   - タスクバー右のスピーカーアイコン → 再生デバイスが意図したものか確認  
   - 別の機器（HDMI・ Bluetooth）が既定になっていないか確認

4. **音量**  
   - アプリ側の音量は特に変更していません。Windows のミキサーで「Electron」や「LiveTalk」の音量がミュート／小さいか確認してください。

5. **接続後の案内**  
   - 窓を開いて接続が始まると「接続したよ。画面を一度クリックすると、私の声が聞こえるよ。」と流れます。**その前に一度、円か画面をクリック**しておくと、この案内が聞けて音声の確認になります。

6. **OpenShokz など特定のデバイスに音を出したい**  
   - 窓内の **「🔊 出力: 既定」** をクリックし、システムのデバイス選択で **OpenShokz**（または使いたいスピーカー）を選んでください。選んだデバイスは次回起動時も記憶されます。  
   - 選択肢が出ない環境では、**Windows の設定 → サウンド → 再生** で OpenShokz を **既定のデバイス** にしてください。
