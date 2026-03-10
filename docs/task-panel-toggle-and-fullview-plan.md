# CanonGate：右側タスクパネル トグル化＆一画面全体での状態把握

**作成日**: 2026-03-10  
**対象**: CanonGate simple-mode-desktop（HUD）  
**依頼先**: Claude（実装用）

---

## 前提・運用方針（2026-03-10 追記）

- **CLI の実行依頼は Canon に依頼する想定**とする。CanonGate（この HUD）から CLI 実行を依頼する機能は持たない。
- **Canon / ALE（Auto-Loop Engine）が自律的にタスクを動かしてよい**。CanonGate は実行のトリガーを持たず、状態の表示のみ行う。
- 本 UI では「CLI実行済」「評価済」を**状態として表示するだけ**。実行は Canon/ALE が行い、その結果（ファイル移動・メタデータ・ログ等）をバックエンドが検知して payload に載せれば、実装可能である。

---

## 1. 背景・目的

- 現在、CanonGate HUD の**右側**に「MISSION_RADAR」としてタスクが**常時・狭い幅**で表示されている。
- これを次のように変更したい：
  1. **トグルで開閉**できるようにする（右パネルを「少しだけ表示」ではなく、開く/閉じるで切り替え）。
  2. **開いているとき**は、**一ウィンドウ全体**（または右側エリア全体）を使って、タスクの一覧と状態を把握できるようにする。
  3. 把握したい状態：
     - **どのタスクがあるか**
     - **タスク済**（タスクとして登録・認識済み）
     - **CLI実行済**（CLI などで実行済み）
     - **評価済**（評価フェーズ済み）

---

## 2. 現状

- **対象画面**: `CanonGate/simple-mode-desktop/index.html`（Electron で読み込まれる HUD）
- **レイアウト**:
  - 左: Intelligence Stream（チャット・独り言・巡回）
  - 中央: Avatar Core（マスコット・音声・コマンド入力）
  - **右: MISSION_RADAR**（`aside.hud-wing.right-wing`）
    - 幅は CSS で `width: 400px`（`.hud-wing`）
    - カテゴリ: 判断 / 提案 / 実行中(Ego) / 実行中(User) / 要整理
    - 各カードに GO / OK / STOP / DONE / CHECK ボタン
- **タスクデータ**:
  - WebSocket で `{ type: "tasks", tasks: [...] }` を受信
  - 各タスク: `id`, `title`, `category`, `is_work`
  - `category`: `user_decision` | `ego_proposal` | `ego_running` | `user_running` | `needs_org`
- **バックエンド**:
  - `CanonGate/simple_chat.py` の `manual_task_sync()` が GTD フォルダ（`next-actions`, `evaluating` 等）をスキャンし、上記形式でブロードキャストしている。
  - フォルダ・ファイル名から category を推定（例: `evaluating` → `user_decision`、タイトルに【実行中】等で `ego_running` / `user_running` / `needs_org`）。

---

## 3. 要件（実装してほしいこと）

### 3.1 右パネルのトグル開閉

- 右側の MISSION_RADAR パネルを**トグルボタン**で開閉できるようにする。
- **閉じているとき**: 右パネルは非表示（またはごく細い「タブ」だけ表示して、クリックで開く）。
- **開いているとき**: 右パネルを表示（現状の 400px または、開時は可変幅／最大幅を広げて「一画面全体でタスクを見る」に寄せる）。

### 3.2 開いたときの「一画面全体で状態把握」

- パネルを**開いた状態**では、次の情報を**一ウィンドウ（または右エリア全体）**で把握できるようにする：
  - **タスク一覧**（既存のカテゴリ別表示でよいが、見やすくする）
  - **状態の見える化**（以下を表形式・バッジ・列などで表示）：
    - **タスク済**: タスクとして登録済み（一覧に載っている時点で「タスク済」とみなしてよい）
    - **CLI実行済**: 当該タスクが CLI で実行されたか（バックエンドにその情報があれば表示；なければ「未実行」などでよい）
    - **評価済**: 評価フェーズに入っている／済み（現状の `evaluating` フォルダ由来の `user_decision` などと対応可能なら、その旨を表示）

- 既存の操作（GO / OK / STOP / DONE / CHECK）は維持する。

### 3.3 バックエンドの拡張（必要に応じて）

- 現在の `tasks` ペイロードには `id`, `title`, `category`, `is_work` のみ。
- 「CLI実行済」「評価済」を表すには、`simple_chat.py` の `manual_task_sync()` で以下を検討：
  - タスクの取得元フォルダ（`next-actions` vs `evaluating`）を `folder` や `phase` として付与する。
  - Canon/ALE が自律実行した結果が、GTD フォルダの移動・メタデータ・ログなどに記録されていれば、それを読んで `cli_executed` 等を付与する。
- フロントは、これらのフィールドがあれば表示し、なければ「未実施」などで表示する。

**実装可能性**: 上記前提（Canon/ALE が自律実行、CanonGate は表示のみ）であれば、トグル・全面表示・状態表示の実装は可能。バックエンドは「Canon/ALE が書き出す結果をどこで読むか」を決めればよい。

---

## 4. 技術メモ（実装時の参照）

| 項目 | 場所・内容 |
|------|------------|
| HUD HTML | `CanonGate/simple-mode-desktop/index.html` |
| HUD CSS | `CanonGate/simple-mode-desktop/index.css`（`.hud-wing`, `.right-wing`, `#taskDash`） |
| タスク描画 | 同 HTML 内 `renderTasks(tasks)`。`#dash-user_decision` 等にカードを挿入。 |
| タスク受信 | WebSocket `msg.type === 'tasks'` で `renderTasks(msg.tasks)` を呼び出し。 |
| タスク同期 | `simple_chat.py` の `manual_task_sync()`。GTD パス: `.agent/gtd/{work|private}/{next-actions,evaluating}`。 |
| ウィンドウサイズ | `main.js` で `BrowserWindow` 幅 1200, 高さ 850。 |

---

## 5. Claude への依頼文（コピペ用）

以下をそのまま Claude に渡して実装を依頼できます。

---

**依頼文（ここから）**

CanonGate の simple-mode-desktop（HUD）で、右側のタスク表示を次のように変更してください。

1. **トグルで開閉**
   - 右側の MISSION_RADAR パネルを、トグルボタンで開閉できるようにする。閉じているときは右パネルを非表示（または細いタブのみ表示）にし、開いているときは表示する。

2. **開いたときは一画面全体で状態を把握**
   - 開いているとき、右エリア（またはオーバーレイ）で、タスク一覧と次の状態を一覧で把握できるようにする：
     - **タスク済**: タスクとして登録済み
     - **CLI実行済**: CLI 実行済みか（バックエンドで情報があれば表示、なければ「未実行」等でよい）
     - **評価済**: 評価フェーズ済みか（例: evaluating フォルダ由来なら「評価済」と表示）

3. **既存動作の維持**
   - 既存のタスクカードの操作（GO / OK / STOP / DONE / CHECK）と、WebSocket によるタスク同期（`tasks`, `task_status_change`）は維持する。

4. **CLI 実行について**
   - CLI の実行依頼は Canon に依頼する運用のため、CanonGate 側に「CLI を実行する」ボタンや依頼機能は実装しない。表示は「CLI実行済」の状態を見せるのみとする。

5. **バックエンド拡張（必要なら）**
   - `CanonGate/simple_chat.py` の `manual_task_sync()` で、タスクに `folder`（next-actions / evaluating）や `cli_executed` などのフィールドを付与し、フロントで「CLI実行済」「評価済」を表示できるようにする。既存の `id`, `title`, `category`, `is_work` はそのままとする。`cli_executed` は Canon 依頼など外部で実行された結果をどこかで検知できれば付与する（CanonGate から CLI を叩く実装はしない）。

詳細な仕様・ファイル場所は、同一リポジトリの `CanonGate/docs/task-panel-toggle-and-fullview-plan.md` を参照してください。

**依頼文（ここまで）**

---

## 6. 完了条件（DoD）

- [x] 右パネルがトグルで開閉できる（閉じ時は非表示またはタブのみ）。
- [x] 開いているとき、タスク一覧と「タスク済 / CLI実行済 / 評価済」が一画面で把握できる表示になっている。
- [x] 既存のタスク操作（GO / OK / STOP / DONE / CHECK）と WebSocket 同期が動作している。
- [x] 必要に応じて `manual_task_sync()` で payload が拡張され、フロントで状態が表示されている。
