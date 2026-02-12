#!/usr/bin/env python3
# pufbih.py
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
logger = logging.getLogger('pufbih')

class PUFBIHScraper:
    def __init__(self):
        self.source_name = "PU FBIH"
        self.source_id = "pu_fbih_001"
        self.output_dir = Path("/home/bihac-danas/web-scraper/facebook_ready_posts/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate script name hash for filenames
        script_name = os.path.basename(sys.argv[0])
        self.script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.url = "https://www.pufbih.ba/objave/list"
    
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
        try:
            logger.info(f"Scraping {self.url}")
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for table with announcements
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    article = self.extract_article_from_row(row)
                    if article and article['title']:
                        if self.save_article(article, counter):
                            articles.append(article)
                            counter += 1
            
            # Also look for list items
            list_items = soup.select('li')
            for item in list_items:
                if not articles or len(articles) < 20:
                    article = self.extract_article_from_list(item)
                    if article and article['title']:
                        if self.save_article(article, counter):
                            articles.append(article)
                            counter += 1
            
        except Exception as e:
            logger.error(f"Error scraping: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article_from_row(self, row):
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None
            
            # Find title and URL
            link = row.find('a')
            if not link:
                return None
            
            title = self.clean_text(link.get_text())
            url = link.get('href')
            
            if url:
                if url.startswith('/'):
                    url = f"https://www.pufbih.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://www.pufbih.ba/{url.lstrip('/')}"
            
            # Get date from cells
            date = None
            for cell in cells:
                cell_text = cell.get_text().strip()
                if re.search(r'\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}', cell_text):
                    date = cell_text
                    break
            
            # Determine type
            content = f"Objava PU FBIH\n\n"
            if 'javni' in title.lower() or 'konkurs' in title.lower():
                content = f"Javni poziv / Konkurs\n\n"
            elif 'nabav' in title.lower():
                content = f"Javna nabavka\n\n"
            elif 'odluka' in title.lower():
                content = f"Odluka\n\n"
            
            content += f"{title}\n\n"
            content += f"Izvor: PU FBIH"
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': None,
                'date': date,
                'published': date,
                'type': 'announcement'
            }
        except Exception as e:
            logger.error(f"Error extracting from row: {e}")
            return None
    
    def extract_article_from_list(self, item):
        try:
            link = item.find('a')
            if not link:
                return None
            
            title = self.clean_text(link.get_text())
            if len(title) < 10:
                return None
            
            url = link.get('href')
            if url:
                if url.startswith('/'):
                    url = f"https://www.pufbih.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://www.pufbih.ba/{url.lstrip('/')}"
            
            return {
                'title': title,
                'content': f"{title}\n\nIzvor: PU FBIH\nPročitaj više: {url}",
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'type': 'announcement'
            }
        except Exception as e:
            logger.error(f"Error extracting from list: {e}")
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
    scraper = PUFBIHScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
