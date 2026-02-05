#!/usr/bin/env python3
"""
VLADA USK News Scraper - REFINED VERSION
Extracts only actual news from category page
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
BASE_URL = "https://vladausk.ba/v4/vrsta/kategorija/4"
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

def is_valid_news_title(title):
    """Check if a title is likely to be a news article (not navigation)"""
    title_lower = title.lower()
    
    # Skip navigation/menu items
    skip_keywords = [
        'kontakt', 'adresa', 'telefon', 'e-mail', 'email',
        'web mail', 'glasnik', 'budžet', 'strategija',
        'geografski', 'sistem', 'gis', 'kalendar',
        'preuzimanja', 'rasprave', 'nabavke', 'konkursi',
        'ministarstva', 'kantonalne', 'uprave', 'organizacije',
        'ured', 'borba', 'korupcija'
    ]
    
    for keyword in skip_keywords:
        if keyword in title_lower:
            return False
    
    # Check for news-like patterns
    news_patterns = [
        r'javn[iy]\s+(poziv|oglas|natječaj|konkurs)',
        r'tehničk[oa]\s+ispravk[oa]',
        r'konačn[ae]\s+(list[ae]|rang-list[ae])',
        r'nabavk[ae]\s+uslug[ae]',
        r'prijav[ae]\s+kandidat[ae]',
        r'prijem\s+namještenik[ae]',
        r'zakup\s+',
        r'program\s+',
        r'projekt[aei]\s+',
        r'referent\s+za',
        r'usavršavanj[ae]\s+za\s+\d{4}'
    ]
    
    for pattern in news_patterns:
        if re.search(pattern, title_lower):
            return True
    
    # Also accept titles with dates in them (like "za 2026. godinu")
    if re.search(r'\d{4}\.', title):
        return True
    
    # Titles should be reasonably long (not single words)
    return len(title) > 20

def extract_news_from_category():
    """Extract only actual news articles from category page"""
    try:
        print(f"Fetching category page: {BASE_URL}")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all h3 elements (these seem to contain news titles)
        all_h3 = soup.find_all('h3')
        
        news_items = []
        
        print(f"Found {len(all_h3)} h3 elements, filtering for news...")
        
        for h3 in all_h3:
            title = clean_text(h3.get_text())
            
            # Skip if not a valid news title
            if not is_valid_news_title(title):
                continue
            
            print(f"  Processing: {title[:60]}...")
            
            # Try to find date - look for "Datum:" pattern near the h3
            date = datetime.now().strftime("%Y-%m-%d")
            
            # Strategy 1: Look for sibling with "Datum:"
            next_elem = h3
            for _ in range(5):  # Check next few elements
                next_elem = next_elem.find_next_sibling()
                if not next_elem:
                    break
                
                text = clean_text(next_elem.get_text())
                if 'datum:' in text.lower():
                    # Extract date in format DD.MM.YYYY
                    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                    if match:
                        day, month, year = match.group(1).split('.')
                        date = f"{year}-{month}-{day}"
                    break
            
            # Strategy 2: Look in parent container
            if date == datetime.now().strftime("%Y-%m-%d"):
                parent = h3.find_parent(['div', 'li', 'article'])
                if parent:
                    parent_text = clean_text(parent.get_text())
                    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', parent_text)
                    if match:
                        day, month, year = match.group(1).split('.')
                        date = f"{year}-{month}-{day}"
            
            # Extract content - look for the next paragraph(s)
            content_parts = []
            
            # Start from h3 and collect next siblings until next h3 or empty
            current = h3.find_next_sibling()
            while current and current.name != 'h3':
                if current.name in ['p', 'div']:
                    text = clean_text(current.get_text())
                    # Skip very short texts and date lines
                    if (len(text) > 30 and 
                        'datum:' not in text.lower() and
                        not text.startswith('Objavljeno')):
                        content_parts.append(text)
                current = current.find_next_sibling()
            
            content = ' '.join(content_parts) if content_parts else ""
            
            # If no content found, use title as content
            if not content or len(content) < 50:
                content = title
            
            # Create a unique URL
            title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
            pseudo_url = f"{BASE_URL}#article_{title_hash}"
            
            news_items.append({
                'title': title,
                'content': content,
                'date': date,
                'url': pseudo_url,
                'original_url': BASE_URL
            })
        
        print(f"\nFound {len(news_items)} valid news articles")
        return news_items
        
    except Exception as e:
        print(f"Error extracting news: {e}")
        return []

def format_for_facebook(news_item):
    """Format the news data for Facebook post"""
    # Create ID from title hash
    post_id = hashlib.md5(news_item['title'].encode()).hexdigest()[:8]
    
    # Generate content hash
    content_hash = generate_content_hash(news_item['content'])
    
    # Format content - include date in the post
    fb_content = f"Datum: {news_item['date']}\n\n"
    
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
        "original_url": news_item['original_url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "Vlada USK",        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": news_item['date']
    }
    
    return fb_post, post_id, content_hash

def scrape_latest_news():
    ensure_dirs()
    scraped_hashes = load_scraped_data()
    new_posts = []
    
    # Extract news from category page
    news_items = extract_news_from_category()
    
    if not news_items:
        print("No news articles found!")
        return []
    
    print(f"\nProcessing {len(news_items)} news articles...")
    
    counter = 1
    
    for news_item in news_items:
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
    print("🚀 VLADA USK News Scraper - REFINED")
    print("=" * 60)
    print(f"Script: {SCRIPT_NAME}")
    print(f"Script hash: {SCRIPT_NAME_HASH}")
    print(f"Target: {BASE_URL}")
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
