#!/usr/bin/env python3
# sanartv.py
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
logger = logging.getLogger('sanartv')

class SanArtTVScraper:
    def __init__(self):
        self.source_name = "SanArt TV"
        self.source_id = "sanart_tv_001"
        self.output_dir = Path("/home/bihac-danas/web-scraper/facebook_ready_posts/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate script name hash for filenames
        script_name = os.path.basename(sys.argv[0])
        self.script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.url = "https://sanartv.ba/"
    
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
            
            # Find articles using various selectors
            selectors = [
                '.jeg_post',
                'article.post',
                '.post-item',
                'article',
                '.jeg_postblock_content',
                '.news-item'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                logger.info(f"Found {len(items)} items with selector '{selector}'")
                if items:
                    for item in items[:25]:  # Process up to 25 items
                        article = self.extract_article(item)
                        if article and article.get('title') and len(article['title']) > 5:
                            if self.save_article(article, counter):
                                articles.append(article)
                                counter += 1
                    if articles:
                        logger.info(f"Successfully extracted {len(articles)} articles with selector '{selector}'")
                        break
            
            # Alternative: Look for direct links in article containers
            if not articles:
                logger.info("Trying alternative method: direct links")
                news_containers = soup.select('.jeg_posts, .content-inner, main, .site-content')
                for container in news_containers:
                    links = container.find_all('a', href=True)
                    for link in links[:30]:
                        href = link.get('href', '')
                        if 'sanartv.ba' in href and not any(x in href for x in ['#', 'javascript', 'category', 'tag', '.jpg', '.png']):
                            article = self.extract_article_from_link(link)
                            if article and article.get('title') and len(article['title']) > 5:
                                if self.save_article(article, counter):
                                    articles.append(article)
                                    counter += 1
                    if articles:
                        break
            
        except Exception as e:
            logger.error(f"Error scraping: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def extract_article(self, elem):
        try:
            # Get title and URL - try different selectors
            title_elem = elem.select_one('h3 a, h2 a, h1 a, .jeg_post_title a, a[href*="sanartv.ba"]')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            # Skip if no title or invalid URL
            if not title or not url:
                return None
            
            # Filter out navigation links (categories, tags, etc.)
            if any(x in url for x in ['#', 'javascript', '/category/', '/tag/', '/author/', '/emisije/', '/o-nama', '/kontakt']):
                return None
            
            if url.startswith('/'):
                url = f"https://sanartv.ba{url}"
            elif not url.startswith('http'):
                url = f"https://sanartv.ba/{url.lstrip('/')}"
            
            # Get content/excerpt
            content_elem = elem.select_one('.jeg_post_excerpt, .content, .excerpt, .text, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else ""
            
            # Get date
            date_elem = elem.select_one('.jeg_meta_date, time, .date, .datum, .published')
            date = None
            if date_elem:
                date_text = self.clean_text(date_elem.get_text())
                # Try to extract date from text
                if date_text:
                    date = date_text
            
            # Get image
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src')
                if image_url:
                    if image_url.startswith('/'):
                        image_url = f"https://sanartv.ba{image_url}"
                    elif image_url.startswith('//'):
                        image_url = f"https:{image_url}"
            
            # Build content with title if no excerpt
            if not content:
                content = title
            
            return {
                'title': title,
                'content': f"SanArt TV - Sanski Most\n\n{content}\n\nIzvor: SanArt TV",
                'url': url,
                'image_url': image_url,
                'date': date,
                'published': date
            }
        except Exception as e:
            logger.error(f"Error extracting article: {e}")
            return None
    
    def extract_article_from_link(self, link):
        try:
            url = link.get('href')
            if not url:
                return None
            
            # Filter out navigation and non-article links
            if any(x in url.lower() for x in ['#', 'javascript', '/category/', '/tag/', '/author/', '/emisije/', '/o-nama', '/kontakt', '.jpg', '.png', '.pdf']):
                return None
            
            # Get title from link text or title attribute
            title = self.clean_text(link.get_text())
            if not title or len(title) < 5:
                title = link.get('title', '')
                if title:
                    title = self.clean_text(title)
            
            # Skip if title is too short or invalid
            if not title or len(title) < 5:
                return None
            
            # Normalize URL
            if url.startswith('/'):
                url = f"https://sanartv.ba{url}"
            elif not url.startswith('http'):
                url = f"https://sanartv.ba/{url.lstrip('/')}"
            
            # Get image from parent or sibling elements
            image_url = None
            parent = link.find_parent(['article', 'div'])
            if parent:
                img_elem = parent.select_one('img')
                if img_elem:
                    image_url = img_elem.get('data-src') or img_elem.get('src')
                    if image_url:
                        if image_url.startswith('/'):
                            image_url = f"https://sanartv.ba{image_url}"
                        elif image_url.startswith('//'):
                            image_url = f"https:{image_url}"
            
            return {
                'title': title,
                'content': f"SanArt TV - Sanski Most\n\n{title}\n\nIzvor: SanArt TV\nPročitaj više: {url}",
                'url': url,
                'image_url': image_url,
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
    scraper = SanArtTVScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
