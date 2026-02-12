#!/usr/bin/env python3
# ussume.py
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
logger = logging.getLogger('ussume')

class USSSumeScraper:
    def __init__(self):
        self.source_name = "US Šume"
        self.source_id = "us_sume_001"
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
            {"url": "https://ussume.ba/category/novosti/", "type": "novosti"},
            {"url": "https://ussume.ba/licitacije/", "type": "licitacije"}
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
                
                # Find articles
                articles_elem = soup.select('article')
                if not articles_elem:
                    articles_elem = soup.select('.post, .item, .novost, .licitacija')
                
                for article_elem in articles_elem[:20]:
                    article = self.extract_article(article_elem, site['type'])
                    if article and article['title']:
                        if self.save_article(article, counter):
                            articles.append(article)
                            counter += 1
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {site['url']}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem, content_type):
        try:
            # Get title and URL
            title_elem = elem.select_one('h1 a, h2 a, h3 a, .entry-title a, .title a')
            if not title_elem:
                title_elem = elem.select_one('a')
            
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url and not url.startswith('http'):
                url = f"https://ussume.ba{url}" if url.startswith('/') else f"https://ussume.ba/{url}"
            
            # Get content
            content_elem = elem.select_one('.entry-content, .content, .excerpt')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            # Get date
            date_elem = elem.select_one('time, .date, .published, .entry-date')
            date = None
            if date_elem:
                if date_elem.has_attr('datetime'):
                    date = date_elem['datetime']
                else:
                    date = self.clean_text(date_elem.get_text())
            
            # Get image
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://ussume.ba{image_url}" if image_url.startswith('/') else f"https://ussume.ba/{image_url}"
            
            # Format based on type
            if content_type == 'novosti':
                prefix = ""
                type_text = "Novost"
            else:
                prefix = ""
                type_text = "Licitacija / Javna nabavka"
            
            full_content = f"{prefix} {type_text} - US Šume\n\n{content}\n\nIzvor: US Šume d.o.o."
            
            return {
                'title': f"{prefix} {title}",
                'content': full_content,
                'url': url,
                'image_url': image_url,
                'date': date,
                'published': date,
                'content_type': content_type
            }
        except Exception as e:
            logger.error(f"Error extracting article: {e}")
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
    scraper = USSSumeScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
