# CanonGate「この端末で全く動かない」デバッグ依頼書

**依頼の意図**: 他端末では CanonGate が動いているが、**この端末（Windows）では全く動かない**。Claude または別セッションのエージェントに、この端末限定で原因を切り分け・修正してほしい。

---

## 1. 環境前提

- **OS**: Windows 10/11
- **レイアウト**: 同じ親フォルダの下に `Canon` と `CanonGate` が並んでいる想定  
  - 例: `c:\databee\Canon` と `c:\databee\CanonGate`
- **起動方法**: `CanonGate_Silent.vbs` で tech/life/dual を選ぶ → 内部で `run_bg.bat` が実行される

---

## 2. 起動フロー（何が動くべきか）

1. **run_bg.bat** が以下を順に実行する:
   - `taskkill` で既存の `python.exe` / `electron.exe` を終了
   - **Commander API** (port 8000): `cd Canon && python scripts\liaison\commander_api.py`
   - **ALE** (Auto-Loop Engine): `cd Canon && python scripts\guardian\auto_loop_engine.py --domain tech`（または life/dual）
   - **Electron**: `npm start -- --domain tech` → `main.js` がウィンドウを開き、**simple_chat.py** を `spawn('python', ['simple_chat.py', ...], { cwd: CanonGate })` で起動

2. **simple_chat.py** は WebSocket で **port 8082**（または `.env`/Commander API の `ws_port`）を listen。UI（index.html）は起動時に `http://localhost:8000/api/canon-gate-config` から `ws_port` を取得して接続する。

3. **VoiceVox** は別途起動し、`http://localhost:50021` で TTS を提供（未起動なら Edge-TTS にフォールバック）。

---

## 3. この端末で確認すべきこと（優先順）

### A. Python が正しく動くか

- コマンドプロンプトで `python --version` が通るか。`py` しかない端末では、`run_bg.bat` や `main.js` の `spawn('python', ...)` が失敗している可能性がある。
- **修正案**: `run_bg.bat` 内の `python` を `py` に変える、または `main.js` の `spawn('python', ...)` を `spawn('py', ...)` に変える。逆に、`py` でしか動かない場合は `python` で統一する。

### B. 作業ディレクトリとパス

- **run_bg.bat** は `%~dp0` = CanonGate のフォルダ。`CANON_ROOT=..\Canon` なので、CanonGate と Canon が**同じ親の下**にないと `scripts\liaison\commander_api.py` が見つからない。
- **main.js** の `spawn('python', ['simple_chat.py'], { cwd: __dirname })` の `__dirname` は **CanonGate** フォルダ。ここに `simple_chat.py` が存在するか確認。

### C. ポート占有

- **8000** (Commander API), **8082** (simple_chat WebSocket), **50021** (VoiceVox) が他プロセスで使われていないか。
- `netstat -ano | findstr "8000 8082 50021"` で確認。既に使われている場合は、該当プロセスを終了するか、.env で別ポートを指定。

### D. ログでどこまで動いているか

- **CanonGate\logs\commander_api.log**  
  - 先頭に `ModuleNotFoundError: No module named 'psutil'` や Traceback があれば、その Python 環境に依存が足りない。
  - `🚀 Canon Commander API started on port 8000` が出ていれば、Commander API は起動できている。
- **CanonGate\logs\ale_tech.log**（または ale_life.log）  
  - `🚀 Canon Auto-Loop Engine (ALE) ... Started` があれば ALE は起動している。
- **CanonGate\system_reports\latest_report.log**  
  - `npm start`（Electron）の標準出力。Electron や `Failed to start Python process` の有無を確認。
- **CanonGate\logs\canon-gate.log** または **alter-ego.log**  
  - simple_chat のログ。`File watcher (HUB mode) started` や `WS Starting server on ... 8082` が出ているか。ここが出ていなければ simple_chat が起動していない（Electron の spawn 失敗の可能性）。

### E. UI の接続先

- simple-mode-desktop の **index.html** は、起動時に `http://localhost:8000/api/canon-gate-config` を叩いて `ws_port`（既定 8082）を取得し、そのポートに WebSocket 接続する。
- 接続できれば「Canon に接続しました」、失敗すると「音声エンジンに接続できません…」と表示される。**この端末で「接続できません」なら、8000 または 8082 のどちらか（または両方）が動いていない。**

### F. 環境変数

- **Canon\.env** に `GROQ_API_KEY` があるか（tech で音声応答する場合）。CanonGate は Canon の `.env` を読む想定。
- **WS_PORT**: 既定 8082。変更している場合は Commander API の `/api/canon-gate-config` と simple_chat の実際の listen ポートが一致しているか。

---

## 4. 依頼してほしいアクション

1. **上記 A〜F をこの端末で順に確認**し、どこで止まっているか（Commander API / ALE / Electron / simple_chat / UI 接続）を特定する。
2. **止まっている箇所を修正**する。  
   - 例: Python が `py` しかない → bat と main.js の起動コマンドを `py` に合わせる。  
   - 例: ポート衝突 → プロセス終了またはポート変更。  
   - 例: パスが違う → CANON_ROOT や cwd をこの端末の配置に合わせる。
3. **再起動手順**を簡潔に記載する（例: 既存の python/electron を終了 → CanonGate_Silent.vbs を実行）。
4. （任意）**「この端末だけ」の差分**（Python の入れ方、Node のバージョン、フォルダ配置など）を README やこのファイルに追記し、次回のため残す。

---

## 5. 参照ファイル一覧

| 役割 | パス |
|------|------|
| 起動バッチ | CanonGate\run_bg.bat |
| 起動 VBS | CanonGate\CanonGate_Silent.vbs |
| Electron エントリ | CanonGate\main.js（ここで simple_chat.py を spawn） |
| simple_chat | CanonGate\simple_chat.py |
| UI | CanonGate\simple-mode-desktop\index.html |
| Commander API | Canon\scripts\liaison\commander_api.py |
| ALE | Canon\scripts\guardian\auto_loop_engine.py |
| 設定例 | Canon\.env（GROQ_API_KEY, WS_PORT 等） |
| ログ | CanonGate\logs\*.log, system_reports\latest_report.log |

---

## 6. 依頼文（そのままコピペ用）

```
CanonGate がこの Windows 端末では全く動きません。他端末では動いています。

CanonGate リポジトリのルートに「DEBUG_THIS_MACHINE.md」があるので、
その「3. この端末で確認すべきこと」に従って、
この端末限定で原因を切り分けし、必要な修正（run_bg.bat / main.js / ポート / パスなど）を実施してください。
修正後、この端末で起動できるよう再起動手順を教えてください。
```

---

*このファイルは、他端末では動くが「この端末でだけ動かない」場合に、Claude や別セッションに渡すための依頼書です。*
