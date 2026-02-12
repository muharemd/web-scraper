#!/usr/bin/env python3
# grad-cazin.py
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
logger = logging.getLogger('gradcazin')

class GradCazinScraper:
    def __init__(self):
        self.source_name = "Grad Cazin"
        self.source_id = "grad_cazin_001"
        self.output_dir = Path("/home/bihac-danas/web-scraper/facebook_ready_posts/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate script name hash for filenames
        script_name = os.path.basename(sys.argv[0])
        self.script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.url = "https://gradcazin.gov.ba/novosti"
    
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
            
            # Try multiple selectors for news items
            selectors = [
                '.novost',
                '.news-item',
                '.post',
                'article',
                '.item',
                '.vest',
                '.objava'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    for item in items:
                        article = self.extract_article(item)
                        if article and article['title']:
                            if self.save_article(article, counter):
                                articles.append(article)
                                counter += 1
                    if articles:
                        break
            
            # If no articles found with selectors, try to find by common patterns
            if not articles:
                # Look for links with dates
                links = soup.find_all('a', href=True)
                for link in links:
                    if any(term in link.text.lower() for term in ['novost', 'obavještenje', 'javni', 'odluka']):
                        article = self.extract_article_from_link(link)
                        if article:
                            if self.save_article(article, counter):
                                articles.append(article)
                                counter += 1
            
        except Exception as e:
            logger.error(f"Error scraping: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem):
        try:
            # Find title and link
            title_elem = elem.select_one('h2 a, h3 a, .title a, a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url.startswith('/'):
                url = f"https://gradcazin.gov.ba{url}"
            elif not url.startswith('http'):
                url = f"https://gradcazin.gov.ba/{url.lstrip('/')}"
            
            # Get content
            content_elem = elem.select_one('.content, .excerpt, .text, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            # Get date
            date_elem = elem.select_one('.date, time, .datum, .published')
            date = None
            if date_elem:
                date = self.clean_text(date_elem.get_text())
            
            # Get image
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = f"https://gradcazin.gov.ba{image_url}"
            
            # Add source attribution
            content = f"{content}\n\nIzvor: Grad Cazin"
            
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
    
    def extract_article_from_link(self, link):
        """Fallback method to extract article from direct link"""
        try:
            url = link.get('href')
            if not url:
                return None
            
            if url.startswith('/'):
                url = f"https://gradcazin.gov.ba{url}"
            elif not url.startswith('http'):
                url = f"https://gradcazin.gov.ba/{url.lstrip('/')}"
            
            title = self.clean_text(link.get_text())
            if len(title) < 10:  # Too short, probably not an article
                return None
            
            return {
                'title': title,
                'content': f"{title}\n\nIzvor: Grad Cazin\nPročitaj više: {url}",
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d')
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
    scraper = GradCazinScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
