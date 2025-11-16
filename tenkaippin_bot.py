#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天下一品ニュースクローラー & Discord Bot
天下一品のニュースページをクロールし、都内の新店情報をDiscordに投稿する
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import tasks
from dotenv import load_dotenv

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tenkaippin_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# 設定
NEWS_URL = "https://www.tenkaippin.co.jp/news/"
HISTORY_FILE = Path("posted_history.json")
# チェックする日付範囲（日数）。この日数以内の記事のみを処理
DAYS_TO_CHECK = int(os.getenv("DAYS_TO_CHECK", "7"))  # デフォルト7日間
# 投稿履歴の保持期間（日数）。この期間を超えた履歴は自動削除
HISTORY_RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "90"))  # デフォルト90日間
TOKYO_KEYWORDS = [
    "東京", "都内", "新宿", "渋谷", "池袋", "上野", "品川", "目黒", "世田谷",
    "大田", "杉並", "練馬", "板橋", "北区", "荒川", "台東", "墨田", "江東",
    "中央", "千代田", "港区", "文京", "足立", "葛飾", "江戸川", "八王子",
    "立川", "武蔵野", "三鷹", "府中", "調布", "町田", "小金井", "小平",
    "日野", "東村山", "国分寺", "国立", "福生", "狛江", "東大和", "清瀬",
    "東久留米", "武蔵村山", "多摩", "稲城", "羽村", "あきる野", "西東京",
    "23区", "東京都"
]

# Discord設定
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))


class TenkaippinCrawler:
    """天下一品ニュースページのクローラー"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_news(self) -> List[Dict]:
        """ニュースページから記事一覧を取得"""
        try:
            response = self.session.get(NEWS_URL, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            # ニュース記事を抽出（ページ構造に応じて調整が必要な場合あり）
            # 日付とタイトルを含む要素を探す
            news_elements = soup.find_all(['li', 'div', 'article'], class_=re.compile(r'news|item|entry', re.I))
            
            # もし特定のクラスが見つからない場合は、より広範囲に検索
            if not news_elements:
                # 日付パターン（YYYY.MM.DD形式）を含む要素を探す
                date_pattern = re.compile(r'\d{4}\.\d{2}\.\d{2}')
                for element in soup.find_all(text=date_pattern):
                    parent = element.find_parent()
                    if parent:
                        news_elements.append(parent)
            
            for element in news_elements:
                try:
                    # 日付を抽出
                    date_text = element.get_text()
                    date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', date_text)
                    if not date_match:
                        continue
                    
                    date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                    
                    # タイトルを抽出
                    title_elem = element.find(['a', 'h3', 'h2', 'h4'])
                    if not title_elem:
                        # テキストからタイトルを抽出
                        title_text = element.get_text(strip=True)
                        # 日付部分を除いたテキストをタイトルとする
                        title = re.sub(r'\d{4}\.\d{2}\.\d{2}\s*', '', title_text).strip()
                    else:
                        title = title_elem.get_text(strip=True)
                    
                    # URLを抽出
                    link_elem = element.find('a', href=True)
                    if link_elem:
                        url = urljoin(NEWS_URL, link_elem['href'])
                    else:
                        url = NEWS_URL
                    
                    if title:
                        news_items.append({
                            'date': date_str,
                            'title': title,
                            'url': url,
                            'text': element.get_text(strip=True)
                        })
                
                except Exception as e:
                    logger.warning(f"記事の解析中にエラー: {e}")
                    continue
            
            # 重複を除去
            seen_titles = set()
            unique_items = []
            for item in news_items:
                if item['title'] not in seen_titles:
                    seen_titles.add(item['title'])
                    unique_items.append(item)
            
            logger.info(f"{len(unique_items)}件のニュース記事を取得しました")
            return unique_items
            
        except Exception as e:
            logger.error(f"ニュース取得エラー: {e}")
            return []
    
    def fetch_article_detail(self, url: str) -> Optional[str]:
        """記事詳細ページから本文を取得"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 本文を取得（一般的な記事本文のセレクタを試す）
            content_selectors = [
                'article', '.article', '.content', '.post-content',
                '.entry-content', 'main', '.main-content'
            ]
            
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    return content.get_text(strip=True)
            
            # セレクタが見つからない場合はbody全体から取得
            body = soup.find('body')
            if body:
                return body.get_text(strip=True)
            
            return None
        except Exception as e:
            logger.warning(f"記事詳細の取得エラー ({url}): {e}")
            return None
    
    def extract_address_from_text(self, text: str) -> Optional[str]:
        """テキストから住所情報を抽出"""
        if not text:
            return None
        
        # 郵便番号パターン（〒123-4567 または 123-4567）
        postal_pattern = r'[〒]?\d{3}-?\d{4}'
        
        # 都道府県パターン（東京都、大阪府など）
        prefecture_pattern = r'[都道府県]+'
        
        # 住所らしいパターンを探す（郵便番号の前後、都道府県の前後）
        # 郵便番号の前後100文字程度を抽出
        postal_matches = list(re.finditer(postal_pattern, text))
        for match in postal_matches:
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 200)
            address_candidate = text[start:end]
            if '東京都' in address_candidate or '東京' in address_candidate:
                return address_candidate
        
        # 都道府県パターンで検索
        prefecture_matches = list(re.finditer(prefecture_pattern, text))
        for match in prefecture_matches:
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 100)
            address_candidate = text[start:end]
            if '東京都' in address_candidate:
                return address_candidate
        
        # 「東京都」が含まれているか直接チェック
        if '東京都' in text:
            # 「東京都」の前後を抽出
            tokyo_index = text.find('東京都')
            if tokyo_index != -1:
                start = max(0, tokyo_index - 20)
                end = min(len(text), tokyo_index + 100)
                return text[start:end]
        
        return None
    
    def extract_opening_date(self, text: str) -> Optional[str]:
        """テキストからオープン日を抽出"""
        if not text:
            return None
        
        # オープン日関連のキーワード（優先順位順）
        opening_keywords = ['オープン日：', 'オープン日', '開店日：', '開店日', 'オープン', '開店']
        
        # 日付パターン（YYYY年MM月DD日(曜日)を含む）
        # 「2025年11月17日(月)」のような形式に対応
        date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日(?:\([月火水木金土日]\))?',  # 2025年11月17日(月) 形式
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # 2025年11月17日 形式
            r'(\d{4})/(\d{1,2})/(\d{1,2})',
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{4})年(\d{1,2})月(\d{1,2})',
        ]
        
        # 各キーワードの周辺を検索（「オープン日：」のような明確なキーワードを優先）
        for keyword in opening_keywords:
            keyword_index = text.find(keyword)
            if keyword_index != -1:
                # キーワードの後ろ300文字を抽出（前は不要）
                start = keyword_index + len(keyword)
                end = min(len(text), start + 300)
                context = text[start:end]
                
                # 日付パターンを検索（キーワードの直後にある日付を優先）
                for pattern in date_patterns:
                    match = re.search(pattern, context)
                    if match:
                        year, month, day = match.groups()[:3]  # 最初の3つのグループ（年、月、日）を取得
                        # YYYY-MM-DD形式に統一
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # キーワードが見つからない場合、「オープン日」という文字列の周辺を検索
        if 'オープン日' in text or '開店日' in text:
            # より広範囲で検索
            for pattern in date_patterns:
                matches = list(re.finditer(pattern, text))
                if matches:
                    # 最初に見つかった日付を返す
                    match = matches[0]
                    year, month, day = match.groups()[:3]
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return None
    
    def is_tokyo_store(self, news_item: Dict) -> bool:
        """ニュースが都内の新店情報かどうかを判定"""
        title = news_item.get('title', '')
        text = news_item.get('text', '')
        combined_text = f"{title} {text}"
        
        # 新店関連のキーワードをチェック
        store_keywords = ['オープン', '開店', '新店', '店舗', '店']
        has_store_keyword = any(keyword in combined_text for keyword in store_keywords)
        
        if not has_store_keyword:
            return False
        
        # まず、タイトル・本文に都内関連のキーワードがあるかチェック
        for keyword in TOKYO_KEYWORDS:
            if keyword in combined_text:
                return True
        
        # タイトル・本文に都内キーワードがない場合、詳細ページをチェック
        url = news_item.get('url')
        if url and url != NEWS_URL:
            logger.info(f"詳細ページをチェック: {title}")
            detail_text = self.fetch_article_detail(url)
            if detail_text:
                # 詳細ページのテキストも含めて判定
                full_text = f"{combined_text} {detail_text}"
                
                # 都内キーワードを再チェック（詳細ページのテキストも含む）
                for keyword in TOKYO_KEYWORDS:
                    if keyword in full_text:
                        # オープン日を抽出してnews_itemに追加
                        opening_date = self.extract_opening_date(detail_text)
                        if opening_date:
                            news_item['opening_date'] = opening_date
                        return True
                
                # 住所情報から判定
                address = self.extract_address_from_text(detail_text)
                if address:
                    if '東京都' in address:
                        logger.info(f"住所情報から都内と判定: {address[:50]}...")
                        # オープン日を抽出してnews_itemに追加
                        opening_date = self.extract_opening_date(detail_text)
                        if opening_date:
                            news_item['opening_date'] = opening_date
                        return True
        
        return False


class HistoryManager:
    """投稿履歴を管理するクラス"""
    
    def __init__(self, history_file: Path, retention_days: int = 90):
        self.history_file = history_file
        self.retention_days = retention_days
        self.history = self.load_history()
        self.cleanup_old_history()
    
    def load_history(self) -> Dict[str, str]:
        """投稿履歴を読み込む（key: 記事のキー, value: 投稿日時のISO形式）"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 旧形式（set）との互換性を保つ
                    posted_items = data.get('posted_items', [])
                    if isinstance(posted_items, list):
                        if posted_items and isinstance(posted_items[0], str):
                            # 旧形式：文字列のリスト → 新形式に変換
                            history = {}
                            for item in posted_items:
                                history[item] = datetime.now().isoformat()
                            return history
                        else:
                            # 新形式：辞書形式
                            return data.get('history', {})
                    return {}
            except Exception as e:
                logger.warning(f"履歴ファイルの読み込みエラー: {e}")
        return {}
    
    def save_history(self):
        """投稿履歴を保存する"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'history': self.history,
                'retention_days': self.retention_days
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"履歴ファイルの保存エラー: {e}")
    
    def cleanup_old_history(self):
        """古い投稿履歴を削除"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        initial_count = len(self.history)
        
        keys_to_remove = []
        for key, posted_at_str in self.history.items():
            try:
                posted_at = datetime.fromisoformat(posted_at_str)
                if posted_at < cutoff_date:
                    keys_to_remove.append(key)
            except (ValueError, TypeError):
                # 無効な日付形式の場合は削除
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.history[key]
        
        if keys_to_remove:
            logger.info(f"古い投稿履歴を{len(keys_to_remove)}件削除しました（{initial_count}件 → {len(self.history)}件）")
            self.save_history()
    
    def is_posted(self, news_item: Dict) -> bool:
        """既に投稿済みかどうかをチェック"""
        # タイトルと日付の組み合わせでユニーク性を判定
        key = f"{news_item.get('date')}_{news_item.get('title')}"
        return key in self.history
    
    def mark_as_posted(self, news_item: Dict):
        """投稿済みとしてマーク"""
        key = f"{news_item.get('date')}_{news_item.get('title')}"
        self.history[key] = datetime.now().isoformat()
        self.save_history()


class DiscordBot(discord.Client):
    """Discord Bot"""
    
    def __init__(self, channel_id: int):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.channel_id = channel_id
        self.crawler = TenkaippinCrawler()
        self.history_manager = HistoryManager(HISTORY_FILE, HISTORY_RETENTION_DAYS)
    
    async def on_ready(self):
        """Botが起動したときの処理"""
        logger.info(f'{self.user}としてログインしました')
        # 毎日のクロールを開始
        self.daily_crawl.start()
    
    @tasks.loop(hours=24)
    async def daily_crawl(self):
        """毎日ニュースをクロールして投稿"""
        await self.crawl_and_post()
    
    @daily_crawl.before_loop
    async def before_daily_crawl(self):
        """初回実行前に待機"""
        await self.wait_until_ready()
        # 起動時にも一度実行
        await self.crawl_and_post()
    
    def filter_recent_news(self, news_items: List[Dict], days: int) -> List[Dict]:
        """指定日数以内の記事のみをフィルタリング"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_items = []
        
        for item in news_items:
            date_str = item.get('date', '')
            try:
                # 日付文字列をパース（YYYY-MM-DD形式を想定）
                item_date = datetime.strptime(date_str, '%Y-%m-%d')
                if item_date >= cutoff_date:
                    filtered_items.append(item)
            except (ValueError, TypeError) as e:
                logger.warning(f"日付のパースエラー: {date_str} - {e}")
                # 日付がパースできない場合は含めない（安全のため）
                continue
        
        logger.info(f"日付フィルタリング: {len(news_items)}件 → {len(filtered_items)}件（直近{days}日以内）")
        return filtered_items
    
    async def crawl_and_post(self):
        """ニュースをクロールして都内の新店情報を投稿"""
        try:
            logger.info("ニュースのクロールを開始します...")
            news_items = self.crawler.fetch_news()
            
            if not news_items:
                logger.warning("ニュース記事が取得できませんでした")
                return
            
            # 直近N日以内の記事のみを処理
            recent_news = self.filter_recent_news(news_items, DAYS_TO_CHECK)
            
            if not recent_news:
                logger.info(f"直近{DAYS_TO_CHECK}日以内の記事が見つかりませんでした")
                return
            
            # 都内の新店情報をフィルタリング（投稿履歴もチェック）
            tokyo_stores = [
                item for item in recent_news
                if self.crawler.is_tokyo_store(item) and not self.history_manager.is_posted(item)
            ]
            
            if not tokyo_stores:
                logger.info("都内の新店情報は見つかりませんでした")
                return
            
            # Discordチャンネルに投稿
            channel = self.get_channel(self.channel_id)
            if not channel:
                logger.error(f"チャンネルID {self.channel_id} が見つかりません")
                return
            
            for store_info in tokyo_stores:
                embed = discord.Embed(
                    title="🏪 天下一品 都内新店情報",
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
                self.history_manager.mark_as_posted(store_info)
                logger.info(f"投稿しました: {store_info['title']}")
                
                # レート制限を避けるため少し待機
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"クロール・投稿処理中にエラー: {e}", exc_info=True)


def main():
    """メイン関数"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKENが設定されていません。.envファイルを確認してください。")
        return
    
    if DISCORD_CHANNEL_ID == 0:
        logger.error("DISCORD_CHANNEL_IDが設定されていません。.envファイルを確認してください。")
        return
    
    bot = DiscordBot(DISCORD_CHANNEL_ID)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
