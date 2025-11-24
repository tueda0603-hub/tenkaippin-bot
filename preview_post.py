#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投稿内容をプレビューするスクリプト
実際にDiscordに投稿せずに、投稿される内容を確認できます
"""

import sys
from pathlib import Path
from datetime import datetime

# tenkaippin_bot.pyから必要なクラスをインポート
sys.path.insert(0, str(Path(__file__).parent))
from tenkaippin_bot import (
    TenkaippinCrawler, 
    HistoryManager, 
    HISTORY_FILE, 
    HISTORY_RETENTION_DAYS,
    DAYS_TO_CHECK
)
from dotenv import load_dotenv
import discord

# 環境変数の読み込み
load_dotenv()

def preview_embed(store_info):
    """Embedの内容をプレビュー表示"""
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
    
    # Embedの内容をテキスト形式で表示
    print("=" * 60)
    print("📋 Discord投稿プレビュー")
    print("=" * 60)
    print(f"\n【タイトル】")
    print(embed.title)
    print(f"\n【説明文】")
    print(embed.description)
    print(f"\n【URL】")
    print(embed.url)
    print(f"\n【フィールド】")
    for field in embed.fields:
        print(f"  {field.name}: {field.value}")
    print(f"\n【タイムスタンプ】")
    print(embed.timestamp)
    print("=" * 60)
    print()

def main():
    """メイン処理"""
    print("天下一品ニュース取得中...")
    
    crawler = TenkaippinCrawler()
    history_manager = HistoryManager(HISTORY_FILE, HISTORY_RETENTION_DAYS)
    
    # ニュースを取得
    news_items = crawler.fetch_news()
    
    if not news_items:
        print("❌ ニュース記事が取得できませんでした")
        return
    
    # 直近N日以内の記事をフィルタリング
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=DAYS_TO_CHECK)
    recent_news = []
    
    for item in news_items:
        date_str = item.get('date', '')
        try:
            item_date = datetime.strptime(date_str, '%Y-%m-%d')
            if item_date >= cutoff_date:
                recent_news.append(item)
        except (ValueError, TypeError):
            continue
    
    print(f"✅ {len(recent_news)}件の直近{DAYS_TO_CHECK}日以内の記事を取得\n")
    
    # 都内の新店情報をフィルタリング
    tokyo_stores = []
    for item in recent_news:
        if crawler.is_tokyo_store(item):
            # オープン日がまだ抽出されていない場合、詳細ページから抽出
            if 'opening_date' not in item:
                url = item.get('url')
                if url and url != "https://www.tenkaippin.co.jp/news/":
                    detail_text = crawler.fetch_article_detail(url)
                    if detail_text:
                        opening_date = crawler.extract_opening_date(detail_text)
                        if opening_date:
                            item['opening_date'] = opening_date
                            print(f"✅ オープン日を抽出: {opening_date}")
            
            # 投稿履歴をチェック（プレビューなので実際には投稿しない）
            if not history_manager.is_posted(item):
                tokyo_stores.append(item)
    
    if not tokyo_stores:
        print("都内の新店情報は見つかりませんでした")
        return
    
    print(f"\n✅ {len(tokyo_stores)}件の都内新店情報が見つかりました\n")
    
    # 各記事の投稿内容をプレビュー
    for i, store_info in enumerate(tokyo_stores, 1):
        print(f"\n【記事 {i}/{len(tokyo_stores)}】")
        preview_embed(store_info)
        
        if i < len(tokyo_stores):
            print("\n" + "-" * 60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nプレビューが中断されました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


