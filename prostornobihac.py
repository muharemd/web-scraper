#!/usr/bin/env python3
# prostornobihac.py
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('prostornobihac')

class ProstornoBihacScraper:
    def __init__(self):
        self.source_name = "Prostorno Bihać"
        self.source_id = "prostorno_bihac_001"
        self.output_dir = Path("/home/bihac-danas/web-scraper/facebook_ready_posts/")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate script name hash for filenames
        script_name = os.path.basename(sys.argv[0])
        self.script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.urls = [
            "https://www.prostornobihac.ba/vijesti",
            "https://www.prostornobihac.ba/dokumenti/2"
        ]
    
    def generate_id(self, url):
        """Generate unique ID from URL"""
        return hashlib.md5(url.encode()).hexdigest()[:8]
    
    def generate_content_hash(self, content):
        """Generate hash of content for deduplication"""
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return ""
        return ' '.join(text.strip().split())
    
    def extract_article_vijesti(self, article_elem, base_url):
        """Extract article from vijesti page"""
        try:
            # Get title and link
            title_elem = article_elem.select_one('h3 a')
            if not title_elem:
                title_elem = article_elem.select_one('.title a')
            if not title_elem:
                title_elem = article_elem.select_one('a')
            
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            # Make absolute URL
            if url.startswith('/'):
                url = f"https://www.prostornobihac.ba{url}"
            
            # Get content/excerpt
            content_elem = article_elem.select_one('.excerpt, .content, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            # Get image
            img_elem = article_elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = f"https://www.prostornobihac.ba{image_url}"
            
            # Get date
            date_elem = article_elem.select_one('.date, time')
            date = self.clean_text(date_elem.get_text()) if date_elem else datetime.now().strftime('%Y-%m-%d')
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': image_url,
                'date': date,
                'published': date
            }
        except Exception as e:
            logger.error(f"Error extracting vijesti article: {e}")
            return None
    
    def extract_article_dokumenti(self, article_elem, base_url):
        """Extract article from dokumenti page"""
        try:
            # Get title and link
            title_elem = article_elem.select_one('h3 a')
            if not title_elem:
                title_elem = article_elem.select_one('a')
            
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url.startswith('/'):
                url = f"https://www.prostornobihac.ba{url}"
            
            # Document specific - get file info
            file_type = "Dokument"
            size_elem = article_elem.select_one('.file-size, .size')
            if size_elem:
                file_type += f" - {self.clean_text(size_elem.get_text())}"
            
            # Build content
            content = f"{file_type}\n\n"
            
            excerpt_elem = article_elem.select_one('.excerpt, p')
            if excerpt_elem:
                content += self.clean_text(excerpt_elem.get_text())
            else:
                content += f"Preuzmite dokument na linku: {url}"
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'file_type': file_type
            }
        except Exception as e:
            logger.error(f"Error extracting dokumenti article: {e}")
            return None
    
    def scrape_vijesti(self, url):
        """Scrape vijesti page"""
        articles = []
        try:
            logger.info(f"Scraping vijesti: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find articles - try different selectors
            article_selectors = [
                '.article',
                '.post',
                '.item',
                'article',
                '.vijest',
                '.news-item',
                '.row > div',
                'div[class*="col"]'
            ]
            
            for selector in article_selectors:
                articles_elem = soup.select(selector)
                if articles_elem:
                    for elem in articles_elem:
                        article = self.extract_article_vijesti(elem, url)
                        if article and article['title']:
                            articles.append(article)
                    if articles:
                        break
            
        except Exception as e:
            logger.error(f"Error scraping vijesti {url}: {e}")
        
        return articles
    
    def scrape_dokumenti(self, url):
        """Scrape dokumenti page"""
        articles = []
        try:
            logger.info(f"Scraping dokumenti: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find document items
            doc_selectors = [
                '.document',
                '.file',
                '.dokument',
                'tr',
                'li',
                '.item'
            ]
            
            for selector in doc_selectors:
                docs = soup.select(selector)
                if docs:
                    for doc in docs:
                        article = self.extract_article_dokumenti(doc, url)
                        if article and article['title']:
                            articles.append(article)
                    if articles:
                        break
            
        except Exception as e:
            logger.error(f"Error scraping dokumenti {url}: {e}")
        
        return articles
    
    def scrape(self):
        """Main scraping method"""
        all_articles = []
        counter = 1
        
        for url in self.urls:
            if 'vijesti' in url:
                articles = self.scrape_vijesti(url)
            else:
                articles = self.scrape_dokumenti(url)
            
            for article in articles:
                if self.save_article(article, counter):
                    all_articles.append(article)
                    counter += 1
            
            time.sleep(1)  # Be respectful to the server
        
        logger.info(f"Scraped {len(all_articles)} articles from {self.source_name}")
        return all_articles
    
    def save_article(self, article, counter):
        """Save article to JSON file"""
        try:
            # Add required fields
            article['id'] = self.generate_id(article['url'])
            article['content_hash'] = self.generate_content_hash(article['content'])
            article['scraped_at'] = datetime.now().isoformat()
            article['source'] = self.script_hash
            article['source_name'] = self.source_name
            article['scheduled_publish_time'] = None
            article['published'] = ""
            
            # Ensure date is in YYYY-MM-DD format
            if 'date' in article and article['date']:
                try:
                    # Try to parse and format date
                    if isinstance(article['date'], str):
                        # Remove any extra text and keep just date
                        date_match = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}', article['date'])
                        if date_match:
                            date_str = date_match.group()
                            if '.' in date_str:
                                parts = date_str.split('.')
                                if len(parts) >= 3:
                                    article['date'] = f"{parts[2].strip()}-{parts[1].strip().zfill(2)}-{parts[0].strip().zfill(2)}"
                            else:
                                article['date'] = date_str
                        else:
                            article['date'] = datetime.now().strftime('%Y-%m-%d')
                except:
                    article['date'] = datetime.now().strftime('%Y-%m-%d')
            else:
                article['date'] = datetime.now().strftime('%Y-%m-%d')
            
            # Generate filename with correct format
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{self.script_hash}-{timestamp}-{counter:03d}.json"
            filepath = self.output_dir / filename
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            return False

def main():
    scraper = ProstornoBihacScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
