#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ニュース取得機能のテストスクリプト
Discord Botを使わずに、ニュース取得機能だけをテストします
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 設定
NEWS_URL = "https://www.tenkaippin.co.jp/news/"
TOKYO_KEYWORDS = [
    "東京", "都内", "新宿", "渋谷", "池袋", "上野", "品川", "目黒", "世田谷",
    "大田", "杉並", "練馬", "板橋", "北区", "荒川", "台東", "墨田", "江東",
    "中央", "千代田", "港区", "文京", "足立", "葛飾", "江戸川", "八王子",
    "立川", "武蔵野", "三鷹", "府中", "調布", "町田", "小金井", "小平",
    "日野", "東村山", "国分寺", "国立", "福生", "狛江", "東大和", "清瀬",
    "東久留米", "武蔵村山", "多摩", "稲城", "羽村", "あきる野", "西東京",
    "23区", "東京都"
]


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


def test_fetch_news():
    """ニュース取得のテスト"""
    print("=" * 60)
    print("天下一品ニュース取得テスト")
    print("=" * 60)
    
    crawler = TenkaippinCrawler()
    
    print("\n[1] ニュース一覧の取得を開始...")
    news_items = crawler.fetch_news()
    
    if not news_items:
        print("❌ ニュース記事が取得できませんでした")
        return
    
    print(f"✅ {len(news_items)}件のニュース記事を取得しました\n")
    
    # 最新5件を表示
    print("[2] 最新5件のニュース:")
    print("-" * 60)
    for i, item in enumerate(news_items[:5], 1):
        print(f"\n{i}. 日付: {item['date']}")
        print(f"   タイトル: {item['title']}")
        print(f"   URL: {item['url']}")
        print(f"   本文（最初の100文字）: {item['text'][:100]}...")
    
    # 新店関連の記事を抽出
    print("\n\n[3] 新店関連の記事を抽出:")
    print("-" * 60)
    store_keywords = ['オープン', '開店', '新店', '店舗', '店']
    store_news = []
    
    for item in news_items:
        combined_text = f"{item['title']} {item['text']}"
        if any(keyword in combined_text for keyword in store_keywords):
            store_news.append(item)
    
    print(f"✅ 新店関連の記事: {len(store_news)}件\n")
    for i, item in enumerate(store_news[:5], 1):
        print(f"{i}. {item['date']} - {item['title']}")
    
    # 都内の新店情報を判定
    print("\n\n[4] 都内の新店情報を判定:")
    print("-" * 60)
    tokyo_stores = []
    
    for item in store_news:
        # 詳細ページを取得してオープン日を抽出（テスト用）
        url = item.get('url')
        if url and url != NEWS_URL:
            detail_text = crawler.fetch_article_detail(url)
            if detail_text:
                # オープン日を抽出
                opening_date = crawler.extract_opening_date(detail_text)
                if opening_date:
                    item['opening_date'] = opening_date
                    print(f"   [DEBUG] オープン日を抽出: {opening_date}")
                else:
                    # デバッグ用：詳細ページの一部を表示
                    if 'オープン日' in detail_text:
                        idx = detail_text.find('オープン日')
                        snippet = detail_text[max(0, idx-20):min(len(detail_text), idx+100)]
                        print(f"   [DEBUG] オープン日周辺のテキスト: {snippet}")
        
        if crawler.is_tokyo_store(item):
            tokyo_stores.append(item)
    
    print(f"✅ 都内の新店情報: {len(tokyo_stores)}件\n")
    for i, item in enumerate(tokyo_stores, 1):
        print(f"{i}. {item['date']} - {item['title']}")
        print(f"   URL: {item['url']}")
        
        # オープン日がある場合は表示
        opening_date = item.get('opening_date')
        if opening_date:
            print(f"   🗓️  オープン日: {opening_date}")
        
        # 詳細ページをチェックした場合はその情報も表示
        if item['url'] != NEWS_URL:
            print(f"   (詳細ページあり)")
    
    # 結果をJSONファイルに保存
    output_file = Path(__file__).parent / "test_results.json"
    results = {
        "total_news": len(news_items),
        "store_news": len(store_news),
        "tokyo_stores": len(tokyo_stores),
        "news_items": news_items[:10],  # 最新10件
        "store_news_items": store_news[:10],
        "tokyo_store_items": tokyo_stores
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n[5] 結果をJSONファイルに保存しました: {output_file}")
    print("=" * 60)
    print("テスト完了！")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_fetch_news()
    except KeyboardInterrupt:
        print("\n\nテストが中断されました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
