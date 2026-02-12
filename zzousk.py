#!/usr/bin/env python3
# zzousk.py
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
logger = logging.getLogger('zzousk')

class ZZOUSKScraper:
    def __init__(self):
        self.source_name = "ZZO USK"
        self.source_id = "zzo_usk_001"
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
            {"url": "https://www.zzousk.ba/novosti", "type": "novosti"},
            {"url": "https://www.zzousk.ba/dokumenti/9", "type": "javni_pozivi"},
            {"url": "https://www.zzousk.ba/dokumenti/11", "type": "konkursi"}
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
                    'article',
                    '.dokument',
                    'tr'
                ]
                
                for selector in selectors:
                    items = soup.select(selector)
                    if items:
                        for item in items[:20]:
                            article = self.extract_article(item, site['type'])
                            if article and article['title']:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                        if articles:
                            break
                
                # If no structured items, look for links
                if not articles:
                    links = soup.find_all('a', href=True)
                    for link in links:
                        article = self.extract_article_from_link(link, site['type'])
                        if article:
                            if self.save_article(article, counter):
                                articles.append(article)
                                counter += 1
                                if len(articles) >= 15:
                                    break
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {site['url']}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem, content_type):
        try:
            # Get title and URL
            link = elem.find('a')
            if not link:
                return None
            
            title = self.clean_text(link.get_text())
            url = link.get('href')
            
            if not title or len(title) < 5:
                return None
            
            if url:
                if url.startswith('/'):
                    url = f"https://www.zzousk.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://www.zzousk.ba/{url.lstrip('/')}"
            
            # Get date if available
            date = None
            date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', elem.get_text())
            if date_match:
                date = date_match.group()
            
            # Format based on type
            prefixes = {
                'novosti': ('', 'Novost'),
                'javni_pozivi': ('', 'Javni poziv'),
                'konkursi': ('', 'Konkurs / Oglas')
            }
            
            prefix, type_label = prefixes.get(content_type, ('', 'Dokument'))
            
            content = f"{type_label} - ZZO USK\n\n{title}\n\n"
            
            # Add additional info
            if content_type != 'novosti':
                content += f"Rok / Datum: {date if date else 'Pogledajte na linku'}\n\n"
            
            content += f"Izvor: Zavod zdravstvenog osiguranja USK"
            
            return {
                'title': title,
                'content': content,
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
            
            # Skip non-content links
            if url.startswith('#') or 'javascript' in url or 'mailto:' in url:
                return None
            
            title = self.clean_text(link.get_text())
            if len(title) < 10:
                return None
            
            if url.startswith('/'):
                url = f"https://www.zzousk.ba{url}"
            elif not url.startswith('http'):
                url = f"https://www.zzousk.ba/{url.lstrip('/')}"
            
            return {
                'title': title,
                'content': f"{title}\n\nIzvor: ZZO USK\nPročitaj više: {url}",
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
    scraper = ZZOUSKScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
