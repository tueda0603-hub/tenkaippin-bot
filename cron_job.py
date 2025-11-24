#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Cron Jobs用のスクリプト
毎日1回、ニュースをクロールしてDiscordに投稿する
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# tenkaippin_bot.pyから必要なクラスをインポート
sys.path.insert(0, str(Path(__file__).parent))
from tenkaippin_bot import (
    TenkaippinCrawler, 
    HistoryManager, 
    HISTORY_FILE, 
    HISTORY_RETENTION_DAYS,
    DAYS_TO_CHECK,
    DISCORD_TOKEN,
    DISCORD_CHANNEL_ID
)
import discord
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def run_cron_job():
    """Cron Jobs用のメイン処理"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKENが設定されていません。環境変数を確認してください。")
        sys.exit(1)
    
    if DISCORD_CHANNEL_ID == 0:
        logger.error("DISCORD_CHANNEL_IDが設定されていません。環境変数を確認してください。")
        sys.exit(1)
    
    # Discord Botクライアントを作成
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    crawler = TenkaippinCrawler()
    history_manager = HistoryManager(HISTORY_FILE, HISTORY_RETENTION_DAYS)
    
    @client.event
    async def on_ready():
        """Botが起動したときの処理"""
        logger.info(f'{client.user}としてログインしました')
        
        try:
            # ニュースをクロールして投稿
            logger.info("ニュースのクロールを開始します...")
            news_items = crawler.fetch_news()
            
            if not news_items:
                logger.warning("ニュース記事が取得できませんでした")
                await client.close()
                return
            
            # 直近N日以内の記事のみを処理
            cutoff_date = datetime.now() - timedelta(days=DAYS_TO_CHECK)
            recent_news = []
            
            for item in news_items:
                date_str = item.get('date', '')
                try:
                    item_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if item_date >= cutoff_date:
                        recent_news.append(item)
                except (ValueError, TypeError) as e:
                    logger.warning(f"日付のパースエラー: {date_str} - {e}")
                    continue
            
            logger.info(f"日付フィルタリング: {len(news_items)}件 → {len(recent_news)}件（直近{DAYS_TO_CHECK}日以内）")
            
            if not recent_news:
                logger.info(f"直近{DAYS_TO_CHECK}日以内の記事が見つかりませんでした")
                await client.close()
                return
            
            # 都内の新店情報をフィルタリング（投稿履歴もチェック）
            tokyo_stores = []
            for item in recent_news:
                if crawler.is_tokyo_store(item) and not history_manager.is_posted(item):
                    # オープン日がまだ抽出されていない場合、詳細ページから抽出
                    if 'opening_date' not in item:
                        url = item.get('url')
                        if url and url != "https://www.tenkaippin.co.jp/news/":
                            detail_text = crawler.fetch_article_detail(url)
                            if detail_text:
                                opening_date = crawler.extract_opening_date(detail_text)
                                if opening_date:
                                    item['opening_date'] = opening_date
                                    logger.info(f"オープン日を抽出: {opening_date}")
                    tokyo_stores.append(item)
            
            if not tokyo_stores:
                logger.info("都内の新店情報は見つかりませんでした")
                await client.close()
                return
            
            # Discordチャンネルに投稿
            channel = client.get_channel(DISCORD_CHANNEL_ID)
            if not channel:
                logger.error(f"チャンネルID {DISCORD_CHANNEL_ID} が見つかりません")
                await client.close()
                return
            
            for store_info in tokyo_stores:
                embed = discord.Embed(
                    title="東京に天下一品がオープンするよ！",
                    description=store_info['title'],
                    url=store_info['url'],
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="記事日付", value=store_info['date'], inline=True)
                
                # オープン日がある場合は表示
                opening_date = store_info.get('opening_date')
                if opening_date:
                    embed.add_field(name="オープン日", value=opening_date, inline=True)
                
                embed.add_field(name="詳細", value=f"[記事を読む]({store_info['url']})", inline=True)
                
                await channel.send(embed=embed)
                history_manager.mark_as_posted(store_info)
                logger.info(f"投稿しました: {store_info['title']}")
                
                # レート制限を避けるため少し待機
                await asyncio.sleep(1)
            
            logger.info("クロール・投稿処理が完了しました")
            
        except Exception as e:
            logger.error(f"クロール・投稿処理中にエラー: {e}", exc_info=True)
        finally:
            # データベース接続を閉じる
            if history_manager.db_conn:
                try:
                    history_manager.db_conn.close()
                except:
                    pass
            # Discordクライアントを適切に閉じる
            if not client.is_closed():
                await client.close()
            # HTTPセッションをクリーンアップ
            await asyncio.sleep(0.25)  # 接続が完全に閉じるまで少し待機
    
    # Botを起動
    try:
        await client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("処理が中断されました")
    except Exception as e:
        logger.error(f"Bot起動エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_cron_job())

