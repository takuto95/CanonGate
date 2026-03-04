# Alter-Ego Mascot (LiveMode)

音声再生とマスコット表示用のブラウザUIです。**必ず以下の順で起動してください。**

## 起動順序

1. **先に** `C:\databee\LiveTalkAiAgent\DebugStart.bat` を実行  
   → チャット脳（WebSocket 8080）が起動するまで待つ  
   → 「--- Listening... ---」と出たらOK

2. **そのあと** このフォルダの `start_web_mascot.bat` をダブルクリック  
   → ローカルサーバーが立ち上がり、ブラウザで http://localhost:8000 が開きます

## 注意

- **フォルダを開くだけでは起動しません。** 必ず `start_web_mascot.bat` を実行してください。
- 音声はこのブラウザタブで再生されます。タブを閉じたり「切断」すると音は出ません。
- 最初に「スタート」ボタンを押すと音声が有効になります（ブラウザの仕様）。
