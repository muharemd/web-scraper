#!/usr/bin/env python3
# npuna.py
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
logger = logging.getLogger('npuna')

class NPUnaScraper:
    def __init__(self):
        self.source_name = "NP Una"
        self.source_id = "np_una_001"
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
            {"url": "https://npuna.com/blog/", "type": "informacije"},
            {"url": "https://npuna.com/smjestajni-kapaciteti/", "type": "smjestaj"}
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
        self.counter = 1  # Initialize counter as instance variable
        
        for site in self.urls:
            try:
                logger.info(f"Scraping {site['url']}")
                response = self.session.get(site['url'], timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                if site['type'] == 'informacije':
                    articles.extend(self.scrape_blog(soup, site['type']))
                else:
                    articles.extend(self.scrape_accommodation(soup, site['type']))
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {site['url']}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def scrape_blog(self, soup, content_type):
        articles = []
        
        # Find blog posts
        selectors = [
            'article',
            '.post',
            '.blog-post',
            '.item',
            '.entry'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                for item in items[:20]:
                    article = self.extract_blog_post(item, content_type)
                    if article and article['title']:
                        if self.save_article(article):
                            articles.append(article)
                if articles:
                    break
        
        return articles
    
    def scrape_accommodation(self, soup, content_type):
        articles = []
        
        # Find accommodation listings
        selectors = [
            '.smjestaj',
            '.kapacitet',
            '.accommodation',
            '.item',
            '.listing'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                for item in items[:20]:
                    article = self.extract_accommodation(item, content_type)
                    if article and article['title']:
                        if self.save_article(article):
                            articles.append(article)
                if articles:
                    break
        
        return articles
    
    def extract_blog_post(self, elem, content_type):
        try:
            title_elem = elem.select_one('h1 a, h2 a, h3 a, .entry-title a, .title a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url:
                if url.startswith('/'):
                    url = f"https://npuna.com{url}"
                elif not url.startswith('http'):
                    url = f"https://npuna.com/{url.lstrip('/')}"
            
            content_elem = elem.select_one('.entry-content, .content, .excerpt, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            date_elem = elem.select_one('time, .date, .published, .entry-date')
            date = None
            if date_elem:
                date = self.clean_text(date_elem.get_text())
            
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = f"https://npuna.com{image_url}"
            
            return {
                'title': title,
                'content': f"Nacionalni park Una\n\n{content}\n\nIzvor: NP Una",
                'url': url,
                'image_url': image_url,
                'date': date,
                'published': date,
                'content_type': content_type
            }
        except Exception as e:
            logger.error(f"Error extracting blog post: {e}")
            return None
    
    def extract_accommodation(self, elem, content_type):
        try:
            title_elem = elem.select_one('h2 a, h3 a, h4 a, .title a, strong a')
            if not title_elem:
                title_elem = elem.select_one('a')
            
            title = self.clean_text(title_elem.get_text()) if title_elem else "Smještajni kapacitet"
            url = title_elem.get('href') if title_elem else None
            
            if url and url.startswith('/'):
                url = f"https://npuna.com{url}"
            
            # Extract accommodation details
            name = self.clean_text(elem.select_one('.naziv, .name').get_text()) if elem.select_one('.naziv, .name') else title
            location = self.clean_text(elem.select_one('.lokacija, .location').get_text()) if elem.select_one('.lokacija, .location') else "NP Una"
            capacity = self.clean_text(elem.select_one('.kapacitet, .capacity').get_text()) if elem.select_one('.kapacitet, .capacity') else ""
            price = self.clean_text(elem.select_one('.cijena, .price').get_text()) if elem.select_one('.cijena, .price') else ""
            
            content = f"Smještaj u NP Una\n\n"
            content += f"Naziv: {name}\n"
            content += f"Lokacija: {location}\n"
            if capacity:
                content += f"Kapacitet: {capacity}\n"
            if price:
                content += f"Cijena: {price}\n"
            
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = f"https://npuna.com{image_url}"
            
            return {
                'title': name,
                'content': content + f"\nIzvor: NP Una",
                'url': url if url else "https://npuna.com/smjestajni-kapaciteti/",
                'image_url': image_url,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'content_type': content_type,
                'accommodation_data': {
                    'name': name,
                    'location': location,
                    'capacity': capacity,
                    'price': price
                }
            }
        except Exception as e:
            logger.error(f"Error extracting accommodation: {e}")
            return None
    
    def save_article(self, article):
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
            filename = f"{self.script_hash}-{timestamp}-{self.counter:03d}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved: {filename}")
            self.counter += 1  # Increment counter after successful save
            return True
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            return False

def main():
    scraper = NPUnaScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
