# Spec: LIFF / リッチメニュー / Flex Message（UX）

## 背景 / 目的
「LINEを開いて探す」を減らし、通知や常時メニューからワンタップで行動を開始できるUXを提供する。

## 運用方針（LIFFファースト）
- **一覧/俯瞰/複数操作はLIFFを正**とする（タスク一覧・ステータス）。
- チャット返信は **短く**、必ず「LIFFで開く」導線（URI/QuickReply/リンク）を併記する。

## リッチメニュー
- 「📋 タスク一覧」ボタンでLIFFを開く
- 画像仕様/座標: `docs/rich-menu-image-guide.md`

## LIFF（タスク一覧）
- **LIFF ID**: `2008835190-F0ZpGhEt`
- 画面: `public/liff/tasks.html`
- 振る舞い（要点）
  - LIFFログイン→profile取得→`/api/tasks?userId=<...>` で todo を取得
  - カード表示、フィルタ表示
  - スワイプ/ボタンで `done <taskId>` / `miss <taskId>` をLINEへ送信

## LIFF（ステータス）
- **LIFF ID**: `2008835190-F0ZpGhEt`（タスク一覧と同一）
- **起動URL**: `https://liff.line.me/2008835190-F0ZpGhEt/status`
  - ※LIFFの `{path}` は `liff.state` として `public/liff/tasks.html` に渡される想定（単一LIFFで画面切替）
- **振る舞い（要点）**
  - LIFFログイン→profile取得→`/api/status?userId=<...>&format=json` でステータス取得
  - 取得した `StatusInfo`（`lib/core/status-service.ts`）をカード表示

## Flex Message（朝の命令）
- 確認手順: `docs/flex-message-test.md`
- postbackボタンで開始/スヌーズ/変更を提供する
 - Flex/返信には可能な範囲で「LIFFで開く」導線を併記する（一覧/ステータスへ迷わず遷移できるようにする）

## 受入条件（Given/When/Then）
- Given: リッチメニューが設定されている
- When: 「📋 タスク一覧」をタップする
- Then: LIFFが開き、todoがカードで表示され、完了/未達報告が送信できる

- Given: リッチメニューが設定されている
- When: 「📊 ステータス」をタップする
- Then: LIFFが開き、`/api/status?format=json` の内容が表示できる

