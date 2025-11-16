# 天下一品ニュースクローラー & Discord Bot

天下一品のニュースページ（https://www.tenkaippin.co.jp/news/）を毎日クロールし、都内の新店情報が掲載されていればDiscordの特定のサーバー・チャンネルに自動投稿するBotです。

## 機能

- 天下一品のニュースページを自動クロール
- 都内の新店情報を自動検出
- Discordチャンネルへの自動投稿
- 重複投稿の防止（投稿履歴管理）
- 毎日自動実行（24時間ごと）

## セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Discord Botの作成と設定

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 新しいアプリケーションを作成
3. 「Bot」セクションでBotを作成
4. Botトークンをコピー
5. 「OAuth2」→「URL Generator」で以下のスコープを選択：
   - `bot`
   - `Send Messages`
   - `Embed Links`
6. 生成されたURLでBotをサーバーに招待
7. 投稿先のチャンネルIDを取得（Discordの設定で「開発者モード」を有効にし、チャンネルを右クリック→「IDをコピー」）

### 3. 環境変数の設定

`.env.example`を`.env`にコピーし、実際の値を設定してください：

```bash
cp .env.example .env
```

`.env`ファイルを編集：

```
DISCORD_TOKEN=your_actual_discord_bot_token
DISCORD_CHANNEL_ID=your_actual_channel_id

# オプション: チェックする日付範囲（日数）。デフォルトは7日間
DAYS_TO_CHECK=7

# オプション: 投稿履歴の保持期間（日数）。デフォルトは90日間
HISTORY_RETENTION_DAYS=90
```

### 4. Botの起動

```bash
python tenkaippin_bot.py
```

## 実行方法

### 通常実行

```bash
python tenkaippin_bot.py
```

Botは起動後、すぐに一度クロールを実行し、その後24時間ごとに自動的にクロールを実行します。

## 記事の抽出範囲と重複防止

### 抽出範囲

- **デフォルト**: 直近7日以内の記事のみを処理します
- 設定変更: `.env`ファイルの`DAYS_TO_CHECK`で変更可能（例: `DAYS_TO_CHECK=14`で14日間）

### 重複防止機能

1. **投稿履歴管理**: 一度投稿した記事は、タイトルと日付の組み合わせで記録され、再投稿されません
2. **自動クリーンアップ**: 90日以上前の投稿履歴は自動的に削除されます（`HISTORY_RETENTION_DAYS`で変更可能）

### 動作の流れ

1. ニュース一覧から記事を取得
2. **日付フィルタリング**: 直近N日以内の記事のみを抽出（`DAYS_TO_CHECK`で設定）
3. **都内判定**: 新店情報かつ都内の記事を抽出
4. **重複チェック**: 投稿履歴を確認し、未投稿の記事のみを投稿
5. 投稿後、履歴に記録

これにより、毎日同じ記事が投稿されることはありません。

### バックグラウンド実行（Linux/Mac）

```bash
nohup python tenkaippin_bot.py > bot.log 2>&1 &
```

### systemdサービスとして実行（Linux）

`/etc/systemd/system/tenkaippin-bot.service`を作成：

```ini
[Unit]
Description=Tenkaippin News Crawler Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/tenkaippin-bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/tenkaippin-bot/tenkaippin_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

サービスを有効化：

```bash
sudo systemctl enable tenkaippin-bot
sudo systemctl start tenkaippin-bot
```

## ファイル構成

- `tenkaippin_bot.py` - メインのBotスクリプト
- `requirements.txt` - 必要なPythonパッケージ
- `.env` - 環境変数設定（Gitにコミットしないこと）
- `.env.example` - 環境変数のテンプレート
- `posted_history.json` - 投稿履歴（自動生成）
- `tenkaippin_bot.log` - ログファイル（自動生成）

## 都内判定のキーワード

以下のキーワードが含まれるニュースを都内の新店情報として判定します：

- 東京、都内、23区、東京都
- 各区名（新宿、渋谷、池袋、上野、品川など）
- 市名（八王子、立川、武蔵野、三鷹など）

## カスタマイズ

### 都内判定キーワードの追加

`tenkaippin_bot.py`の`TOKYO_KEYWORDS`リストにキーワードを追加できます。

### クロール間隔の変更

`tenkaippin_bot.py`の`@tasks.loop(hours=24)`の部分を変更することで、クロール間隔を調整できます。

例：12時間ごとに実行する場合
```python
@tasks.loop(hours=12)
```

## トラブルシューティング

### Botが起動しない

- `.env`ファイルが正しく設定されているか確認
- DiscordトークンとチャンネルIDが正しいか確認
- Botがサーバーに招待されているか確認
- Botに必要な権限（メッセージ送信、埋め込みリンク）があるか確認

### ニュースが取得できない

- インターネット接続を確認
- 天下一品のサイトがアクセス可能か確認
- ログファイル（`tenkaippin_bot.log`）を確認

### 都内の新店情報が検出されない

- `TOKYO_KEYWORDS`に適切なキーワードが含まれているか確認
- ニュースのタイトルや本文に都内を示すキーワードが含まれているか確認

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 注意事項

- このBotは天下一品の公式サービスではありません
- ウェブスクレイピングは利用規約を遵守してください
- 過度なリクエストを送らないよう注意してください

