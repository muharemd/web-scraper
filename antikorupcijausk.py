#!/usr/bin/env python3
# antikorupcijausk.py
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
logger = logging.getLogger('antikorupcijausk')

class AntikorupcijaUSKScraper:
    def __init__(self):
        self.source_name = "Antikorupcija USK"
        self.source_id = "antikorupcija_usk_001"
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
            {"url": "https://antikorupcijausk.ba/obavjestenja", "type": "obavjestenja"},
            {"url": "https://antikorupcijausk.ba/novosti", "type": "novosti"},
            {"url": "https://antikorupcijausk.ba/registarusk/imenovani_list.php?page=list", "type": "registar"},
            {"url": "https://antikorupcijausk.ba/registarusk/podaci_o_nosiocu_list.php", "type": "nosioci"}
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
                
                if site['type'] in ['registar', 'nosioci']:
                    # Handle register pages
                    articles.extend(self.scrape_register(soup, site['type']))
                else:
                    # Handle news/announcements
                    articles.extend(self.scrape_content(soup, site['type']))
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error scraping {site['url']}: {e}")
        
        logger.info(f"Scraped {len(articles)} articles from {self.source_name}")
        return articles
    
    def scrape_content(self, soup, content_type):
        articles = []
        
        selectors = [
            '.obavjestenje',
            '.novost',
            '.vijest',
            '.item',
            'article',
            '.post',
            '.vest'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                for item in items[:20]:
                    article = self.extract_article(item, content_type)
                    if article and article['title']:
                        if self.save_article(article):
                            articles.append(article)
                if articles:
                    break
        
        return articles
    
    def scrape_register(self, soup, content_type):
        articles = []
        
        # Find tables in register
        tables = soup.find_all('table')
        for table in tables[:3]:  # Limit to first 3 tables
            rows = table.find_all('tr')
            for row in rows[1:11]:  # First 10 rows after header
                article = self.extract_register_entry(row, content_type)
                if article and article['title']:
                    if self.save_article(article):
                        articles.append(article)
        
        return articles
    
    def extract_article(self, elem, content_type):
        try:
            title_elem = elem.select_one('h1 a, h2 a, h3 a, .title a, a')
            if not title_elem:
                return None
            
            title = self.clean_text(title_elem.get_text())
            url = title_elem.get('href')
            
            if url:
                if url.startswith('/'):
                    url = f"https://antikorupcijausk.ba{url}"
                elif not url.startswith('http'):
                    url = f"https://antikorupcijausk.ba/{url.lstrip('/')}"
            
            content_elem = elem.select_one('.content, .excerpt, .text, p')
            content = self.clean_text(content_elem.get_text()) if content_elem else title
            
            date_elem = elem.select_one('.date, time, .datum')
            date = None
            if date_elem:
                date = self.clean_text(date_elem.get_text())
            
            img_elem = elem.select_one('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src')
                if image_url and image_url.startswith('/'):
                    image_url = f"https://antikorupcijausk.ba{image_url}"
            
            prefixes = {
                'obavjestenja': '',
                'novosti': ''
            }
            
            prefix = prefixes.get(content_type, '')
            
            full_content = f"{content_type.capitalize()} - Antikorupcija USK\n\n{content}\n\nIzvor: Antikorupcija USK"
            
            return {
                'title': title,
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
    
    def extract_register_entry(self, row, content_type):
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None
            
            # Extract name and position
            name = self.clean_text(cells[0].get_text()) if len(cells) > 0 else ""
            position = self.clean_text(cells[1].get_text()) if len(cells) > 1 else ""
            institution = self.clean_text(cells[2].get_text()) if len(cells) > 2 else ""
            
            title = f"Registar imenovanih: {name}"
            if position:
                title += f" - {position}"
            
            content = f"📋 Registar imenovanih lica - Antikorupcija USK\n\n"
            content += f"Ime i prezime: {name}\n"
            if position:
                content += f"Funkcija: {position}\n"
            if institution:
                content += f"Institucija: {institution}\n"
            
            content += f"\n📌 Izvor: Antikorupcija USK"
            
            # Generate a fake URL based on data
            url = f"https://antikorupcijausk.ba/registar/imenovani/{hashlib.md5(name.encode()).hexdigest()[:8]}"
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'image_url': None,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'published': datetime.now().strftime('%Y-%m-%d'),
                'content_type': content_type,
                'register_data': {
                    'name': name,
                    'position': position,
                    'institution': institution
                }
            }
        except Exception as e:
            logger.error(f"Error extracting register entry: {e}")
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
    scraper = AntikorupcijaUSKScraper()
    scraper.scrape()

if __name__ == "__main__":
    main()
