# Render Cron Jobs デプロイガイド

このBotをRenderのCron Jobsで毎日朝7時に実行するためのセットアップガイドです。

## 前提条件

- Renderアカウント（https://render.com）
- Discord BotトークンとチャンネルID

## デプロイ手順

### 1. GitHubリポジトリにプッシュ

```bash
cd ~/Desktop/projects/tenkaippin-bot
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. RenderでCron Jobを作成

1. [Render Dashboard](https://dashboard.render.com/)にログイン
2. 「New +」→「Cron Job」を選択
3. 以下の設定を行う：
   - **Name**: `tenkaippin-news-crawler`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python cron_job.py`
   - **Schedule**: `0 7 * * *` (毎日朝7時 UTC)
   - **Branch**: `main` (または使用しているブランチ名)

### 3. 履歴の永続化設定（推奨：GitHub Gist - 完全無料）

**重要**: RenderのCron Jobsでは各実行が独立コンテナのため、ファイルに保存した履歴は失われます。GitHub Gistを使用することで、完全無料で履歴を永続化できます。

#### GitHub Gistのセットアップ

1. **GitHub Personal Access Tokenを作成**
   - https://github.com/settings/tokens にアクセス
   - 「Generate new token (classic)」をクリック
   - **Note**: `tenkaippin-bot-history`（任意）
   - **Expiration**: 無期限または長期間
   - **Scopes**: `gist` のみチェック
   - 「Generate token」をクリックしてトークンをコピー（一度しか表示されません）

2. **Gistを作成**
   - https://gist.github.com/ にアクセス
   - **Filename**: `posted_history.json`
   - **Content**: `{"history": {}}`
   - 「Create public gist」または「Create secret gist」をクリック
   - 作成後、URLからGist IDをコピー
     - 例: `https://gist.github.com/username/abc123def456` → `abc123def456`

### 4. 環境変数の設定

Render Dashboardで、作成したCron Jobの「Environment」セクションで以下を設定：

```
DISCORD_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id
GITHUB_TOKEN=your_github_personal_access_token
GIST_ID=your_gist_id
DAYS_TO_CHECK=7
HISTORY_RETENTION_DAYS=90
```

**注意**: 
- `GITHUB_TOKEN`と`GIST_ID`を設定すると、GitHub Gistを使用して履歴を永続化します（推奨）
- 設定しない場合、履歴は一時ストレージに保存され、再デプロイ時に失われる可能性があります
- PostgreSQLを使用したい場合は、`DATABASE_URL`を設定することも可能です（GitHub Gistより優先度が低い）

### 4. タイムゾーンの調整

RenderのCron JobsはUTC時間で動作します。日本時間（JST）の朝7時に実行したい場合：

- **JST 7:00 = UTC 22:00（前日）**
- Scheduleを `0 22 * * *` に設定

または、夏時間を考慮する場合は：
- **JST 7:00 = UTC 22:00（前日）** または **UTC 23:00（前日）**

### 5. デプロイの確認

1. Render DashboardでCron Jobの「Logs」を確認
2. 初回実行時にエラーがないか確認
3. Discordチャンネルに投稿が来るか確認

## ファイル構成

- `cron_job.py` - Cron Jobs用のエントリーポイント（1回実行して終了）
- `tenkaippin_bot.py` - メインのBotスクリプト（共通ロジック）
- `render.yaml` - Render設定ファイル（オプション）

## トラブルシューティング

### Cron Jobが実行されない

- Scheduleの設定を確認（Cron形式: `分 時 日 月 曜日`）
- Render Dashboardの「Logs」でエラーを確認
- 環境変数が正しく設定されているか確認

### Discordに投稿されない

- Discord Botトークンが正しいか確認
- チャンネルIDが正しいか確認
- Botがサーバーに招待されているか確認
- Botに必要な権限があるか確認

### パッケージのインストールエラー

- `requirements.txt`の内容を確認
- Renderのビルドログを確認

## ローカルテスト

Cron Jobの動作をローカルでテストする場合：

```bash
python cron_job.py
```

## 注意事項

- Renderの無料プランでは、Cron Jobの実行時間に制限がある場合があります
- 履歴ファイル（`posted_history.json`）はRenderの一時ストレージに保存されます
- より永続的な保存が必要な場合は、外部データベース（PostgreSQL等）の使用を検討してください


