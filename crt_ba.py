#!/usr/bin/env python3
# crt_ba.py
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
logger = logging.getLogger('crt_ba')

class CRTBaScraper:
    def __init__(self):
        self.source_name = "CRT Cazin"
        self.source_id = "crt_cazin_001"
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
            "https://crt.ba/",
            "https://crt.ba/category/aktuelnosti/"
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
                
                # Try multiple selectors
                selectors = [
                    'article',
                    '.post',
                    '.aktuelnost',
                    '.news-item',
                    '.vest',
                    '.item'
                ]
                
                for selector in selectors:
                    items = soup.select(selector)
                    if items:
                        for item in items[:15]:
                            article = self.extract_article(item, url)
                            if article and article['title']:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                        if articles:
                            break
                
                # If still no articles, try to find blog posts
                if not articles:
                    blog_posts = soup.select('.blog-post, .entry, .story')
                    for post in blog_posts:
                        article = self.extract_article(post, url)
                        if article and article['title']:
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
            title_elem = elem.select_one('h1 a, h2 a, h3 a, .entry-title a, .title a, a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url:
                if url.startswith('/'):
                    url = f"https://crt.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://crt.ba/{url.lstrip('/')}"
            
            # Get content
            content_elem = elem.select_one('.entry-content, .content, .excerpt, p')
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
                if image_url and image_url.startswith('/'):
                    image_url = f"https://crt.ba{image_url}"
            
            # Add source
            content = f"{content}\n\nIzvor: CRT Cazin"
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': image_url,
                'date': date,
                'published': date
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
    scraper = CRTBaScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
