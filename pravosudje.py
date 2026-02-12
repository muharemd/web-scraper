#!/usr/bin/env python3
# pravosudje.py
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
logger = logging.getLogger('pravosudje')

class PravosudjeScraper:
    def __init__(self):
        self.source_name = "Pravosudje BiH"
        self.source_id = "pravosudje_bih_001"
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
            "https://pravosudje.ba/vstvfo/B/1/kategorije-vijesti/6919/6968/6947",
            "https://pravosudje.ba/vstvfo/B/1/kategorije-vijesti/6919/6968/6946",
            "https://opsud-bihac.pravosudje.ba/vstvfo/B/17/grupe-vijesti/305",
            "https://opsud-bihac.pravosudje.ba/vstvfo/B/17/kategorije-vijesti/4196/4205/118576"
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
        
        for url in self.urls:
            try:
                logger.info(f"Scraping {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find news items
                news_items = soup.select('.vijest, .news-item, .item, .objava, tr')
                
                for item in news_items[:20]:
                    article = self.extract_article(item, url)
                    if article and article['title']:
                        if self.save_article(article, counter):
                            articles.append(article)
                            counter += 1
                
                # Look for links in content
                if not articles:
                    content_area = soup.select_one('#content, .content, main')
                    if content_area:
                        links = content_area.find_all('a', href=True)
                        for link in links[:15]:
                            article = self.extract_article_from_link(link)
                            if article:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem, base_url):
        try:
            # Get title and URL
            link = elem.find('a')
            if not link:
                return None
            
            title = self.clean_text(link.get_text())
            if len(title) < 5:
                return None
            
            url = link.get('href')
            if url:
                if url.startswith('/'):
                    # Extract base domain
                    domain = re.match(r'(https?://[^/]+)', base_url)
                    if domain:
                        url = f"{domain.group(1)}{url}"
                elif not url.startswith('http'):
                    url = f"{base_url}/{url.lstrip('/')}"
            
            # Get date
            date = None
            date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', elem.get_text())
            if date_match:
                date = date_match.group()
            
            # Determine court type
            court_type = "Sud BiH"
            if "opsud-bihac" in base_url:
                court_type = "Općinski sud Bihać"
            
            content = f"{court_type}\n\n{title}\n\n"
            
            if date:
                content += f"Datum: {date}\n\n"
            
            content += f"Izvor: Pravosudje BiH"
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': None,
                'date': date,
                'published': date,
                'court': court_type
            }
        except Exception as e:
            logger.error(f"Error extracting article: {e}")
            return None
    
    def extract_article_from_link(self, link):
        try:
            url = link.get('href')
            if not url:
                return None
            
            if url.startswith('#') or 'javascript' in url:
                return None
            
            title = self.clean_text(link.get_text())
            if len(title) < 10:
                return None
            
            return {
                'title': title,
                'content': f"{title}\n\nIzvor: Pravosudje BiH\nPročitaj više: {url}",
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'court': 'Sud BiH'
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
    scraper = PravosudjeScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
