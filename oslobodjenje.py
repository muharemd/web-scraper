#!/usr/bin/env python3
"""
Scraper for Oslobođenje - searches for Bihać-related articles
"""

import os
import json
import hashlib
import re
import time
from datetime import datetime
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = "/home/bihac-danas/web-scraper/facebook_ready_posts"
BASE_URL = "https://www.oslobodjenje.ba"
SEARCH_URL = "https://www.oslobodjenje.ba/pretraga/"
SEARCH_TERM = "bihac"
SOURCE_NAME = "Oslobođenje"
SOURCE_HASH = hashlib.md5(b"oslobodjenje.py").hexdigest()[:12]

# User-Agent rotation to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

def get_random_user_agent():
    """Return a random user agent"""
    return random.choice(USER_AGENTS)

def create_session():
    """Create a requests session with headers to mimic a real browser"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    return session

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return ""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove special characters that might break JSON
    text = text.replace('"', "'").replace('\n', ' ').replace('\r', ' ')
    return text.strip()

def extract_date(article_soup, article_url):
    """Extract date from article page"""
    try:
        # Try multiple possible date selectors
        date_selectors = [
            'time[datetime]',
            '.date',
            '.article-date',
            '.published',
            '.timestamp',
            'meta[property="article:published_time"]',
            'meta[name="publish_date"]',
            'span.date',
        ]
        
        for selector in date_selectors:
            element = article_soup.select_one(selector)
            if element:
                date_text = element.get('datetime') or element.get('content') or element.get_text()
                if date_text:
                    # Parse date
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                    if date_match:
                        return date_match.group(0)
        
        # Try to find date in URL
        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', article_url)
        if date_match:
            return f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        
        # Default to today
        return datetime.now().strftime('%Y-%m-%d')
        
    except Exception as e:
        logger.warning(f"Could not extract date: {e}")
        return datetime.now().strftime('%Y-%m-%d')

def scrape_article(article_url, session):
    """Scrape individual article page"""
    try:
        logger.info(f"Scraping article: {article_url}")
        
        # Add delay to be polite
        time.sleep(random.uniform(1, 3))
        
        response = session.get(article_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = ""
        title_selectors = ['h1', '.article-title', '.title', 'meta[property="og:title"]']
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get('content') if selector.startswith('meta') else element.get_text()
                if title:
                    title = clean_text(title)
                    break
        
        if not title:
            logger.warning(f"No title found for {article_url}")
            return None
        
        # Extract content
        content = ""
        content_selectors = [
            '.article-content',
            '.content',
            '.post-content',
            'article',
            '.entry-content',
            'div[itemprop="articleBody"]'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                # Remove unwanted elements
                for tag in element.select('script, style, iframe, nav, footer, .share-buttons, .comments'):
                    tag.decompose()
                
                content = element.get_text()
                if content and len(content) > 100:  # Minimum content length
                    content = clean_text(content)
                    break
        
        # If still no content, try to get description
        if not content or len(content) < 100:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                content = clean_text(meta_desc.get('content', ''))
        
        if not content or len(content) < 50:
            logger.warning(f"Insufficient content for {article_url}")
            return None
        
        # Extract date
        date = extract_date(soup, article_url)
        
        # Extract image
        image_url = ""
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.article-image img',
            '.featured-image img',
            'img.wp-post-image'
        ]
        
        for selector in image_selectors:
            element = soup.select_one(selector)
            if element:
                image_url = element.get('content') or element.get('src')
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(BASE_URL, image_url)
                if image_url:
                    break
        
        # Generate content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        # Generate article ID
        article_id = hashlib.md5(f"{article_url}_{date}".encode()).hexdigest()[:8]
        
        return {
            'title': title,
            'content': content,
            'url': article_url,
            'date': date,
            'image_url': image_url,
            'content_hash': content_hash,
            'id': article_id
        }
        
    except Exception as e:
        logger.error(f"Error scraping article {article_url}: {e}")
        return None

def search_articles(session, max_pages=3):
    """Search for articles and return article URLs"""
    articles = []
    
    try:
        for page in range(1, max_pages + 1):
            logger.info(f"Searching page {page} for '{SEARCH_TERM}'")
            
            # Build search URL with pagination
            search_params = f"?search={quote(SEARCH_TERM)}"
            if page > 1:
                search_params += f"&page={page}"
            
            search_page_url = SEARCH_URL + search_params
            
            # Add delay between pages
            if page > 1:
                time.sleep(random.uniform(2, 4))
            
            response = session.get(search_page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links - adjust selectors based on actual page structure
            article_links = []
            
            # Try multiple possible selectors for article links
            link_selectors = [
                'a[href*="/clanak/"]',
                'a[href*="/vijesti/"]',
                '.article a',
                '.news-item a',
                '.search-result a',
                'h2 a',
                'h3 a'
            ]
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and 'clanak' in href or 'vijesti' in href:
                        full_url = urljoin(BASE_URL, href)
                        if full_url not in article_links:
                            article_links.append(full_url)
            
            if not article_links:
                logger.warning(f"No article links found on page {page}")
                break
            
            # Add to articles list
            articles.extend(article_links)
            logger.info(f"Found {len(article_links)} articles on page {page}")
            
            # Check if there are more pages
            next_button = soup.select_one('.next, .pagination-next, a[rel="next"]')
            if not next_button:
                break
        
        # Remove duplicates
        articles = list(dict.fromkeys(articles))
        logger.info(f"Total unique articles found: {len(articles)}")
        
        return articles
        
    except Exception as e:
        logger.error(f"Error searching articles: {e}")
        return []

def check_if_exists(content_hash):
    """Check if article already exists in output directory"""
    if not os.path.exists(OUTPUT_DIR):
        return False
    
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(OUTPUT_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('content_hash') == content_hash:
                        return True
            except:
                continue
    return False

def save_article(article_data):
    """Save article to JSON file"""
    try:
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{SOURCE_HASH}_{timestamp}_{article_data['id']}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Prepare final data structure
        final_data = {
            "title": article_data['title'],
            "id": article_data['id'],
            "content": article_data['content'],
            "url": article_data['url'],
            "scheduled_publish_time": None,
            "published": "",  # Will be filled when posted
            "source": SOURCE_HASH,
            "source_name": SOURCE_NAME,
            "content_hash": article_data['content_hash'],
            "scraped_at": datetime.now().isoformat(),
            "image_url": article_data.get('image_url', ''),
            "date": article_data['date']
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved article: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving article: {e}")
        return False

def main():
    """Main function"""
    logger.info(f"Starting Oslobođenje scraper for '{SEARCH_TERM}'")
    
    # Create session
    session = create_session()
    
    # Search for articles
    article_urls = search_articles(session)
    
    if not article_urls:
        logger.info("No articles found")
        return
    
    # Scrape each article
    new_articles_count = 0
    for url in article_urls:
        try:
            article_data = scrape_article(url, session)
            if article_data:
                # Check if article already exists
                if not check_if_exists(article_data['content_hash']):
                    if save_article(article_data):
                        new_articles_count += 1
                    # Be polite - delay between articles
                    time.sleep(random.uniform(1, 2))
                else:
                    logger.info(f"Article already exists: {article_data['title'][:50]}...")
            else:
                logger.warning(f"Failed to scrape article: {url}")
        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
    
    logger.info(f"Scraping complete. New articles: {new_articles_count}/{len(article_urls)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
