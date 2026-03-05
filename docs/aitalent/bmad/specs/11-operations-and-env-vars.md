# Spec: 運用（環境変数 / タイムゾーン / デバッグ）

## 背景 / 目的
本システムは外部API（LINE/DeepSeek/Sheets）依存で、運用時の設定ミスが障害に直結する。
協議・引き継ぎのため、必須設定と注意点をまとめる。

## 必須環境変数（要点）
SSoT: `docs/bmad/spec-current.md` の「必須環境変数」

- DeepSeek: `DEEPSEEK_API_KEY`（任意: `DEEPSEEK_MODEL`, `DEEPSEEK_MAX_TOKENS`, `DEEPSEEK_HTTP_LOG*`）
- LINE: `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`, `LINE_USER_ID`
- Sheets: `GOOGLE_CLIENT_EMAIL`, `GOOGLE_PRIVATE_KEY`, `SHEETS_SPREADSHEET_ID`
- Internal Auth: `INTERNAL_API_KEY`

### 開発時の配置（推奨）
- 例: ルートの `.env.example` を参考にし、ローカルは `.env.local` にコピーして設定する
- `.env` は誤コミット防止のためリポジトリ管理しない（`.gitignore` 対象）

## タイムゾーン（注意）
- Vercel CronはUTC基準（`vercel.json`）
- logs.timestampの扱い（UTC/JST）や表示は `docs/bmad/gaps.md` で協議対象

## デバッグ用エンドポイント
- DeepSeek疎通: `/api/test-deepseek`
  - 手順: `docs/endpoint-readme.md`

## ログ/PII（未決定）
- DeepSeek HTTPログの扱い（マスキング/保存範囲）は `docs/bmad/gaps.md` で協議

