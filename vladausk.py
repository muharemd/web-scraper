#!/usr/bin/env python3
"""
VLADA USK News Scraper - RSS-like logic
Scans vladausk.ba/v4/ page and extracts actual news articles with images
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import hashlib
from datetime import datetime
import re
from urllib.parse import urljoin
import time
import sys

# Configuration
BASE_URL = "https://vladausk.ba/v4/"
NOVOSTI_URL = "https://vladausk.ba/v4/vrsta/novosti"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "vladausk_state.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

SCRIPT_NAME = os.path.basename(sys.argv[0])
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_content_hash(content):
    if not content:
        return ""
    clean_content = ' '.join(content.split()).lower()
    return hashlib.md5(clean_content.encode()).hexdigest()[:12]

def load_scraped_data():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('scraped_hashes', []))
    return set()

def save_scraped_data(content_hashes):
    state = {
        'scraped_hashes': list(content_hashes),
        'last_run': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def clean_text(text):
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('\r\n', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_image_from_article(soup):
    """Extract image URL from article HTML"""
    # Try to find image in common locations
    img = soup.find('img', src=re.compile(r'vladausk\.ba.*\.(jpg|jpeg|png|gif)'))
    if img and img.get('src'):
        img_url = img['src']
        if not img_url.startswith('http'):
            img_url = urljoin(BASE_URL, img_url)
        return img_url
    return None

def extract_date_from_text(text):
    """Extract date from text in DD.MM.YYYY format"""
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime("%Y-%m-%d")

def extract_news_from_page(url, page_name=""):
    """Extract actual news articles from vladausk.ba page using RSS-like logic"""
    try:
        print(f"Fetching {page_name}: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        news_items = []
        
        # Look for article links that point to actual news (/novost/...)
        # This is similar to how RSS.app identifies actual news vs navigation
        article_links = soup.find_all('a', href=re.compile(r'/novost/[^/]+/\d+'))
        
        print(f"Found {len(article_links)} potential article links")
        
        seen_urls = set()
        
        for link in article_links:
            article_url = link.get('href')
            if not article_url:
                continue
                
            # Make absolute URL
            if not article_url.startswith('http'):
                article_url = urljoin(BASE_URL, article_url)
            
            # Skip duplicates
            if article_url in seen_urls:
                continue
            seen_urls.add(article_url)
            
            # Extract title from link or nearby heading
            title = clean_text(link.get_text())
            
            # If title is too short, look for h3 or h2 nearby
            if len(title) < 20:
                parent = link.find_parent(['div', 'article', 'li'])
                if parent:
                    heading = parent.find(['h3', 'h2', 'h4'])
                    if heading:
                        title = clean_text(heading.get_text())
            
            # Skip if still no good title
            if len(title) < 20 or title.lower() == 'vlada usk':
                continue
            
            print(f"  Processing: {title[:60]}...")
            
            # Extract description/content from nearby div
            description = ""
            parent = link.find_parent(['div', 'article'])
            if parent:
                # Look for paragraph or div with content
                content_elem = parent.find(['p', 'div'], class_=lambda x: x and 'content' in str(x).lower())
                if not content_elem:
                    content_elem = parent.find('p')
                if content_elem:
                    description = clean_text(content_elem.get_text())
            
            # Extract image
            image_url = None
            if parent:
                img = parent.find('img', src=re.compile(r'\.(jpg|jpeg|png|gif)'))
                if img and img.get('src'):
                    image_url = img['src']
                    if not image_url.startswith('http'):
                        image_url = urljoin(BASE_URL, image_url)
            
            # Extract date from parent container
            date = datetime.now().strftime("%Y-%m-%d")
            if parent:
                parent_text = parent.get_text()
                date = extract_date_from_text(parent_text)
            
            news_items.append({
                'title': title,
                'content': description if description else title,
                'date': date,
                'url': article_url,
                'image_url': image_url
            })
        
        print(f"\nFound {len(news_items)} valid news articles from {page_name}")
        return news_items
        
    except Exception as e:
        print(f"Error extracting news from {page_name}: {e}")
        import traceback
        traceback.print_exc()
        return []

def format_for_facebook(news_item):
    """Format the news data for Facebook post"""
    # Create ID from title hash
    post_id = hashlib.md5(news_item['title'].encode()).hexdigest()[:8]
    
    # Generate content hash
    content_hash = generate_content_hash(news_item['content'])
    
    # Format content
    fb_content = f"{news_item['title']}\n\n"
    
    if len(news_item['content']) > 700:
        fb_content += news_item['content'][:700] + "..."
    else:
        fb_content += news_item['content']
    
    # Add source info
    fb_content += f"\n\nIzvor: Vlada Unsko-sanskog kantona"
    
    # Create JSON structure
    fb_post = {
        "title": news_item['title'],
        "id": post_id,
        "content": fb_content,
        "url": news_item['url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "Vlada USK",
        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": news_item['date']
    }
    
    # Add image if available
    if news_item.get('image_url'):
        fb_post['image_url'] = news_item['image_url']
    
    return fb_post, post_id, content_hash

def scrape_latest_news():
    ensure_dirs()
    scraped_hashes = load_scraped_data()
    new_posts = []
    
    # Extract news from both main page and novosti page (RSS-like logic)
    all_news_items = []
    
    # Scrape main page
    main_items = extract_news_from_page(BASE_URL, "main page")
    all_news_items.extend(main_items)
    
    # Scrape novosti page
    novosti_items = extract_news_from_page(NOVOSTI_URL, "novosti page")
    all_news_items.extend(novosti_items)
    
    if not all_news_items:
        print("No news articles found!")
        return []
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_items = []
    for item in all_news_items:
        if item['url'] not in seen_urls:
            seen_urls.add(item['url'])
            unique_items.append(item)
    
    print(f"\nProcessing {len(unique_items)} unique news articles...")
    
    counter = 1
    
    for news_item in unique_items:
        print(f"\nArticle {counter}: {news_item['title'][:60]}...")
        print(f"  Date: {news_item['date']}")
        print(f"  Content length: {len(news_item['content'])} chars")
        
        # Format for Facebook
        fb_post, post_id, content_hash = format_for_facebook(news_item)
        
        print(f"  Content hash: {content_hash}")
        
        # Check for duplicate content
        if content_hash in scraped_hashes:
            print(f"  ⚠️  Duplicate content detected")
            continue
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"{SCRIPT_NAME_HASH}-{timestamp}-{counter:03d}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(fb_post, f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ Saved: {filename}")
            
            # Update tracking
            scraped_hashes.add(content_hash)
            new_posts.append({
                'filename': filename,
                'title': news_item['title'],
                'post_id': post_id,
                'content_length': len(news_item['content'])
            })
            
            counter += 1
            
        except Exception as e:
            print(f"  ❌ Error saving: {e}")
    
    # Save state
    save_scraped_data(scraped_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New posts created: {len(new_posts)}")
    
    return new_posts

def main():
    print("=" * 60)
    print("🚀 VLADA USK News Scraper - RSS-like Logic")
    print("=" * 60)
    print(f"Script: {SCRIPT_NAME}")
    print(f"Script hash: {SCRIPT_NAME_HASH}")
    print(f"Target 1: {BASE_URL}")
    print(f"Target 2: {NOVOSTI_URL}")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)
    
    new_posts = scrape_latest_news()
    
    if new_posts:
        print("\n📋 NEW POSTS CREATED:")
        for post in new_posts:
            print(f"  📄 {post['filename']}")
            print(f"    {post['title'][:70]}...")
            print(f"    🆔 {post['post_id']}")
            print()
    else:
        print("\nℹ️  No new posts found.")
    
    print(f"✅ Check the '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)

if __name__ == "__main__":
    main()
