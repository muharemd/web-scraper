#!/usr/bin/env python3
# uino.py
import requests
from bs4 import BeautifulSoup
import json
import hashlib
from datetime import datetime
from pathlib import Path
import re
import time
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('uino')

class UINOScraper:
    def __init__(self):
        self.source_name = "UINO BiH"
        self.source_id = "uino_bih_001"
        self.output_dir = Path("/home/bihac-danas/web-scraper/facebook_ready_posts/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate script name hash for filenames
        script_name = os.path.basename(sys.argv[0])
        self.script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.urls = [
            {"url": "https://www.uino.gov.ba/portal/bs/novosti/", "type": "novosti"},
            {"url": "https://www.uino.gov.ba/portal/bs/oglasi/", "type": "oglasi"}
        ]
    
    def generate_id(self, url):
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def generate_content_hash(self, content):
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def clean_text(self, text):
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def scrape(self):
        articles = []
        counter = 1
        
        for site in self.urls:
            try:
                logger.info(f"Scraping {site['url']}")
                response = self.session.get(site['url'], timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try different selectors
                selectors = [
                    '.novost',
                    '.vijest',
                    '.item',
                    '.article',
                    '.post',
                    'article',
                    '.oglasi-item',
                    '.objava'
                ]
                
                for selector in selectors:
                    items = soup.select(selector)
                    if items:
                        for item in items[:15]:
                            article = self.extract_article(item, site['type'])
                            if article and article['title']:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                        if articles:
                            break
                
                # Look for news blocks
                if not articles:
                    news_blocks = soup.select('.news-list, .list-items, .view-content')
                    for block in news_blocks:
                        links = block.find_all('a', href=True)
                        for link in links:
                            article = self.extract_article_from_link(link, site['type'])
                            if article:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                                    if len(articles) >= 20:
                                        break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {site['url']}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem, content_type):
        try:
            # Find title and link
            title_elem = elem.select_one('h2 a, h3 a, .title a, a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url:
                if url.startswith('/'):
                    url = f"https://www.uino.gov.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://www.uino.gov.ba/{url.lstrip('/')}"
            
            # Get content/excerpt
            content_elem = elem.select_one('.content, .excerpt, .description, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            # Get date
            date_elem = elem.select_one('.date, time, .datum, .created')
            date = None
            if date_elem:
                if date_elem.has_attr('datetime'):
                    date = date_elem['datetime']
                else:
                    date = self.clean_text(date_elem.get_text())
            
            # Add type-specific prefix
            prefix = ""
            type_label = "Novost" if content_type == "novosti" else "Oglas"
            
            full_content = f"{type_label} UINO BiH\n\n{content}\n\nIzvor: UINO BiH"
            
            return {
                'title': title,
                'content': full_content,
                'url': url,
                'image_url': None,
                'date': date,
                'published': date,
                'content_type': content_type
            }
        except Exception as e:
            logger.error(f"Error extracting article: {e}")
            return None
    
    def extract_article_from_link(self, link, content_type):
        try:
            url = link.get('href')
            if not url:
                return None
            
            title = self.clean_text(link.get_text())
            if len(title) < 10:
                return None
            
            if url.startswith('/'):
                url = f"https://www.uino.gov.ba{url}"
            elif not url.startswith('http'):
                url = f"https://www.uino.gov.ba/{url.lstrip('/')}"
            
            return {
                'title': title,
                'content': f"{title}\n\nIzvor: UINO BiH\nPročitaj više: {url}",
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'content_type': content_type
            }
        except Exception as e:
            logger.error(f"Error extracting from link: {e}")
            return None
    
    def save_article(self, article, counter):
        try:
            article['id'] = self.generate_id(article['url'])
            article['content_hash'] = self.generate_content_hash(article['content'])
            article['scraped_at'] = datetime.now().isoformat()
            article['source'] = self.script_hash
            article['source_name'] = self.source_name
            article['scheduled_publish_time'] = None
            article['published'] = ""
            
            if not article.get('date') or article['date'] == '':
                article['date'] = datetime.now().strftime('%Y-%m-%d')
            
            # Generate filename with correct format
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{self.script_hash}-{timestamp}-{counter:03d}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved: {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            return False

def main():
    scraper = UINOScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
