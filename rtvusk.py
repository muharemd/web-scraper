#!/usr/bin/env python3
"""
RTV USK News Scraper - WORKING VERSION
Scrapes: https://www.rtvusk.ba/kategorija/kanton-krajina/2
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
BASE_URL = "https://www.rtvusk.ba/kategorija/kanton-krajina/2"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "rtvusk_state.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Get script name hash
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
            return set(data.get('scraped_urls', [])), set(data.get('content_hashes', []))
    return set(), set()

def save_scraped_data(scraped_urls, content_hashes):
    state = {
        'scraped_urls': list(scraped_urls),
        'content_hashes': list(content_hashes),
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

def extract_news_details(news_url):
    try:
        print(f"  Fetching: {news_url}")
        response = requests.get(news_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title - from h1 or h2
        title = "No Title"
        title_elem = soup.find('h1') or soup.find('h2')
        if title_elem:
            title = clean_text(title_elem.get_text())
        
        # Extract content - RTV USK specific
        content = ""
        
        # Look for content divs
        content_selectors = [
            'div.text',
            'div.content',
            'div.entry-content',
            'div.post-content',
            'article',
            'div[itemprop="articleBody"]'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove unwanted elements
                for tag in elem(['script', 'style', 'iframe', 'aside', 'nav', 'form']):
                    tag.decompose()
                
                text = clean_text(elem.get_text())
                if len(text) > 100:
                    content = text
                    break
        
        # Fallback: get all paragraphs
        if len(content) < 100:
            paragraphs = soup.find_all('p')
            meaningful = []
            for p in paragraphs:
                text = clean_text(p.get_text())
                if len(text) > 30 and not any(word in text.lower() for word in ['share', 'facebook', 'twitter', 'komentar']):
                    meaningful.append(text)
            
            if meaningful:
                content = ' '.join(meaningful[:8])
        
        # Extract date
        date = datetime.now().strftime("%Y-%m-%d")
        
        # Look for date in various locations
        date_elem = soup.find('time') or soup.find(class_=re.compile(r'date|datum|vrijeme', re.I))
        if date_elem:
            date_text = clean_text(date_elem.get_text())
            if date_text:
                # Look for date patterns
                match = re.search(r'\d{2}\.\d{2}\.\d{4}', date_text)
                if match:
                    day, month, year = match.group(0).split('.')
                    date = f"{year}-{month}-{day}"
        
        # Extract image
        image_url = None
        img_elem = soup.find('meta', property='og:image') or soup.find('img')
        if img_elem:
            if img_elem.name == 'meta':
                img_src = img_elem.get('content', '')
            else:
                img_src = img_elem.get('src', '')
            
            if img_src:
                image_url = urljoin(news_url, img_src)
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'url': news_url,
            'image_url': image_url,
            'source': 'RTV USK'
        }
        
    except Exception as e:
        print(f"  Error extracting details: {e}")
        return None

def format_for_facebook(news_data):
    post_id = hashlib.md5(news_data['url'].encode()).hexdigest()[:8]
    content_hash = generate_content_hash(news_data['content'])
    
    # Format content
    if len(news_data['content']) > 800:
        fb_content = news_data['content'][:800] + "..."
    else:
        fb_content = news_data['content']
    
    # Add read more link
    if fb_content:
        fb_content += f"\n\n📺 Izvor: RTV USK"
        fb_content += f"\n🔗 Pročitaj više: {news_data['url']}"
    
    # Create JSON
    fb_post = {
        "title": news_data['title'],
        "id": post_id,
        "content": fb_content,
        "url": news_data['url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "RTV USK",        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat()
    }
    
    if news_data.get('image_url'):
        fb_post["image_url"] = news_data['image_url']
    if news_data.get('date'):
        fb_post["date"] = news_data['date']
    
    return fb_post, post_id, content_hash

def scrape_news_links():
    """Scrape news links from h2 elements (as shown in diagnostic)"""
    try:
        print(f"Scraping RTV USK: {BASE_URL}")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all h2 elements - they contain article links
        h2_elements = soup.find_all('h2')
        
        news_links = []
        
        print(f"Found {len(h2_elements)} h2 elements")
        
        for h2 in h2_elements:
            # Find link inside h2 or parent link
            link = h2.find('a')
            if not link:
                # Maybe the h2 itself is inside an <a> tag
                parent_link = h2.find_parent('a')
                if parent_link:
                    link = parent_link
            
            if link and link.get('href'):
                href = link.get('href')
                text = clean_text(link.get_text())
                
                # Skip if empty or not an article
                if not href or not text or len(text) < 10:
                    continue
                
                # Make URL absolute
                if href.startswith('/'):
                    href = urljoin(BASE_URL, href)
                elif not href.startswith('http'):
                    href = urljoin(BASE_URL, href)
                
                # Only include /clanak/ URLs
                if '/clanak/' in href and href not in news_links:
                    news_links.append(href)
                    print(f"  Found: {text[:50]}...")
        
        # Also look for other article links
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href')
            if '/clanak/' in href and href not in news_links:
                full_url = urljoin(BASE_URL, href)
                if full_url not in news_links:
                    news_links.append(full_url)
        
        print(f"Total article links found: {len(news_links)}")
        
        # Return unique links, limit to 10
        unique_links = []
        seen = set()
        for link in news_links[:15]:  # Check first 15
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links
        
    except Exception as e:
        print(f"Error scraping links: {e}")
        return []

def scrape_latest_news():
    ensure_dirs()
    scraped_urls, content_hashes = load_scraped_data()
    new_posts = []
    
    # Get news links
    news_links = scrape_news_links()
    
    if not news_links:
        print("No news links found!")
        return []
    
    print(f"\nProcessing {len(news_links)} articles...")
    
    counter = 1
    
    for news_url in news_links:
        print(f"\n[{counter}/{len(news_links)}] Checking: {news_url}")
        
        # Skip if already scraped
        if news_url in scraped_urls:
            print("  ⏩ Already processed")
            counter += 1
            continue
        
        # Extract details
        news_details = extract_news_details(news_url)
        if not news_details:
            print("  ❌ Could not extract details")
            counter += 1
            continue
        
        print(f"  Title: {news_details['title'][:60]}...")
        print(f"  Content: {len(news_details['content'])} chars")
        
        # Format for Facebook
        fb_post, post_id, content_hash = format_for_facebook(news_details)
        
        print(f"  Content hash: {content_hash}")
        
        # Check for duplicate content
        if content_hash in content_hashes:
            print(f"  ⚠️  Duplicate content detected")
            scraped_urls.add(news_url)
            counter += 1
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
            scraped_urls.add(news_url)
            content_hashes.add(content_hash)
            new_posts.append({
                'filename': filename,
                'title': news_details['title'],
                'url': news_url,
                'post_id': post_id
            })
            
        except Exception as e:
            print(f"  ❌ Error saving: {e}")
        
        counter += 1
        time.sleep(2)  # Be polite
    
    # Save state
    save_scraped_data(scraped_urls, content_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New posts created: {len(new_posts)}")
    
    return new_posts

def main():
    print("=" * 60)
    print("🚀 RTV USK News Scraper - FIXED")
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
            print(f"    🔗 {post['url']}")
            print()
    else:
        print("\nℹ️  No new posts found.")
    
    print(f"✅ Check the '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)

if __name__ == "__main__":
    main()
