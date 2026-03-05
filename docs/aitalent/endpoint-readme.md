# DeepSeek API エンドポイント確認用 README

## 目的
ローカルと Vercel (dev/prod) で `/api/test-deepseek` を検証するための手順をまとめています。DeepSeek API Key を環境変数 `DEEPSEEK_API_KEY` に設定したうえで以下を実施してください。

## 環境変数
- `.env.local` (ローカル開発): `DEEPSEEK_API_KEY=<取得済みキー>`
- Vercel Project Settings → Environment Variables: 同キーを `Production` / `Preview` / `Development` すべてに登録し、再デプロイ

## ローカルでの確認
1. 依存関係インストール: `npm install`
2. 開発サーバ起動: `npm run dev`
3. 別ターミナルで cURL を実行:
   ```bash
   curl -X GET http://localhost:3000/api/test-deepseek | jq
   ```
4. 期待値: `{"success":true,"reply":"OK"}` のような JSON が返る
5. エラー時: ターミナルログと `curl -v` でレスポンス本文を確認。`401` → API Key、`500` → DeepSeek側レスポンス、`404` → Next.js が起動していない/ルートが違う可能性

## Preview/Production の確認
1. Vercel Dashboard で最新デプロイの URL (例: `https://ai-agent-manager.vercel.app`) を確認
2. PC/スマホ双方で以下を叩く:
   ```bash
   curl -X GET https://<your-domain>/api/test-deepseek | jq
   ```
   - iOS/Android では `HTTPS` 強制・キャッシュが残ることがあるため、失敗時はプライベートモードまたは `vercel.app` の Preview URL で切り分け
3. `404 Not Found` の場合の主な原因
   - Next.js 依存が不足しており Vercel が静的ホスティング扱い → `package.json` に `next`/`react`/`react-dom` と `scripts` を追加し再デプロイ
   - `app` ディレクトリ構成がルートからズレている → `app/api/...` をルート直下に配置
   - カスタムドメイン設定が完了していない → `Domains` タブで `A/AAAA/CNAME` の伝播を確認 (`vercel domains inspect <domain>`)
4. `500` の場合
   - `vercel logs <deployment-id>` で詳細を見る
   - DeepSeek API レート/モデル名を確認 (`deepseek-reasoner` / `deepseek-v3`)
   - 429/401 の場合はキーと月間クォータを確認

## デバッグチェックリスト
- [ ] `npm run lint` が成功する
- [ ] `npm run build` で Next.js ビルドが通る
- [ ] Vercel 上で `Build & Output` が Framework = `Next.js` になっている
- [ ] `curl https://<domain>/.well-known/vercel/status.json` で 200 が返り、SSL が有効
- [ ] `curl -H "Cache-Control: no-cache" https://<domain>/api/test-deepseek` で毎回 200 を確認

## 参考コマンド
```bash
# Vercel CLI でログを確認
vercel logs <deployment-url> --since 1h

# ドメインの設定状況
vercel domains inspect <domain>
```
