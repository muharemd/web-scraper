#!/usr/bin/env python3
"""
DžBihac News Scraper - IMPROVED VERSION with better title extraction
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
BASE_URL = "https://www.dzbihac.com/index.php/bs/medija-centar/novosti/oglasi"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "dzbihac_state.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Get script name hash for file naming
SCRIPT_NAME = os.path.basename(sys.argv[0])
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]

def ensure_dirs():
    """Create necessary directories"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_content_hash(content):
    """Generate a hash from content to detect duplicates"""
    if not content:
        return ""
    clean_content = ' '.join(content.split()).lower()
    return hashlib.md5(clean_content.encode()).hexdigest()[:12]

def load_scraped_data():
    """Load previously scraped data"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('scraped_urls', [])), set(data.get('content_hashes', []))
    return set(), set()

def save_scraped_data(scraped_urls, content_hashes):
    """Save scraped data to state file"""
    state = {
        'scraped_urls': list(scraped_urls),
        'content_hashes': list(content_hashes),
        'last_run': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME,
        'script_hash': SCRIPT_NAME_HASH
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return ""
    text = ' '.join(text.split())
    text = text.replace('\r\n', ' ').replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_news_details(news_url):
    """Extract full details from a news article page - IMPROVED for dzbihac.com"""
    try:
        print(f"  Fetching: {news_url}")
        response = requests.get(news_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # IMPROVED TITLE EXTRACTION for dzbihac.com
        title = "No Title"
        
        # Strategy 1: Look for title in common locations
        title_selectors = [
            'h1', 'h2', 
            '.article-title', '.item-title', '.title',
            '.page-title', '.contentheading',
            'div.item-page h2',  # Common in Joomla
            'div.blog-item h2',
            'h2 a',  # Sometimes title is in h2 with link
            'div#content h2'  # Title in content area
        ]
        
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title_text = clean_text(elem.get_text())
                if title_text and len(title_text) > 5 and title_text != "No Title":
                    title = title_text
                    print(f"    Found title: {title[:60]}...")
                    break
        
        # Strategy 2: Extract from URL if no title found
        if title == "No Title":
            # Try to extract title from URL slug
            match = re.search(r'/(\d+)-(.+)$', news_url)
            if match:
                title_from_url = match.group(2).replace('-', ' ').title()
                title = clean_text(title_from_url)
                print(f"    Extracted title from URL: {title}")
        
        # Extract content
        content = ""
        
        # Common content selectors for Joomla sites
        content_selectors = [
            'div.item-page',  # Most likely for dzbihac.com
            'div.article-content',
            'div.article-body',
            'div.content',
            'div.post-content',
            'div.entry-content',
            'div[itemprop="articleBody"]',
            'div#content div'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Remove unwanted elements
                for tag in content_elem(['script', 'style', 'iframe', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                
                # Get text
                text = content_elem.get_text()
                if len(text.strip()) > 50:
                    content = clean_text(text)
                    print(f"    Found content ({len(content)} chars)")
                    break
        
        # Fallback: look for paragraphs
        if len(content) < 100:
            paragraphs = soup.find_all('p')
            meaningful_paragraphs = []
            for p in paragraphs:
                text = clean_text(p.get_text())
                if len(text) > 20:
                    meaningful_paragraphs.append(text)
            
            if meaningful_paragraphs:
                content = ' '.join(meaningful_paragraphs[:5])
        
        # Extract date
        date = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            'time',
            '.created', '.published', '.date',
            'span[class*="date"]',
            'dd.create',
            'meta[property="article:published_time"]'
        ]
        
        for selector in date_selectors:
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'article:published_time'})
                if elem:
                    date_text = elem.get('content', '')
                    if date_text:
                        match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                        if match:
                            date = match.group(0)
                        break
            else:
                elem = soup.select_one(selector)
                if elem:
                    date_text = clean_text(elem.get_text())
                    if date_text:
                        match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                        if match:
                            date = match.group(0)
                        break
        
        # Extract image
        image_url = None
        img_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'div.article-image img',
            'div.item-image img',
            'img[src*="images/stories"]',  # Common in Joomla
            'img.intro-image',
            'img.full-image',
            'img[title*="' + title[:20] + '"]' if title != "No Title" else None
        ]
        
        for selector in img_selectors:
            if not selector:
                continue
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'og:image'}) or soup.find('meta', {'name': 'twitter:image'})
                if elem:
                    img_src = elem.get('content', '')
                    if img_src:
                        image_url = urljoin(news_url, img_src)
                        break
            else:
                elem = soup.select_one(selector)
                if elem and elem.get('src'):
                    img_src = elem.get('src')
                    if img_src:
                        image_url = urljoin(news_url, img_src)
                        break
        
        # If no specific image found, use site logo as fallback
        if not image_url:
            logo_elem = soup.find('img', src=re.compile(r'logo', re.I))
            if logo_elem and logo_elem.get('src'):
                image_url = urljoin(news_url, logo_elem.get('src'))
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'url': news_url,
            'image_url': image_url
        }
        
    except Exception as e:
        print(f"  Error extracting details: {e}")
        return None

def format_for_facebook(news_data):
    """Format the news data for Facebook post"""
    # Create ID from URL hash
    post_id = hashlib.md5(news_data['url'].encode()).hexdigest()[:8]
    
    # Generate content hash
    content_hash = generate_content_hash(news_data['content'])
    
    # Format content
    if len(news_data['content']) > 800:
        fb_content = news_data['content'][:800] + "..."
    else:
        fb_content = news_data['content']
    
    # Add "Read more" link
    if fb_content:
        fb_content += f"\n\nRead more: {news_data['url']}"
    
    # Create JSON structure
    fb_post = {
        "title": news_data['title'],
        "id": post_id,
        "content": fb_content,
        "url": news_data['url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "Dom zdravlja Bihać",        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat()
    }
    
    if news_data.get('image_url'):
        fb_post["image_url"] = news_data['image_url']
    if news_data.get('date'):
        fb_post["date"] = news_data['date']
    
    return fb_post, post_id, content_hash

def scrape_news_links():
    """Scrape the main page for news links"""
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        news_links = []
        
        print(f"Looking for news links on: {BASE_URL}")
        
        # Look for the blog/items section (common in Joomla)
        item_sections = [
            'div.blog', 'div.items', 'div.item-list',
            'div.news', 'div.articles', 'div.category'
        ]
        
        for section in item_sections:
            section_elem = soup.select_one(section)
            if section_elem:
                print(f"Found section: {section}")
                # Get all article links in this section
                links = section_elem.find_all('a', href=re.compile(r'/index\.php/bs/medija-centar/novosti/'))
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(BASE_URL, href)
                        if full_url not in news_links:
                            news_links.append(full_url)
        
        # If no sections found, find all article links
        if not news_links:
            print("No sections found, searching for all article links...")
            article_links = soup.find_all('a', href=re.compile(r'/index\.php/bs/medija-centar/novosti/'))
            for link in article_links:
                href = link.get('href')
                if href:
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in news_links:
                        news_links.append(full_url)
        
        # Remove duplicates and limit
        unique_links = []
        seen = set()
        for link in news_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        print(f"Found {len(unique_links)} unique news links")
        return unique_links[:10]  # Limit to 10
        
    except Exception as e:
        print(f"Error scraping news links: {e}")
        return []

def scrape_latest_news():
    """Main scraping function"""
    print(f"Script: {SCRIPT_NAME} (hash: {SCRIPT_NAME_HASH})")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    ensure_dirs()
    scraped_urls, content_hashes = load_scraped_data()
    new_posts = []
    
    # Get news links
    news_links = scrape_news_links()
    
    if not news_links:
        print("No news links found!")
        return []
    
    print(f"\nProcessing {len(news_links)} links...")
    
    counter = 1
    processed = 0
    
    for news_url in news_links:
        processed += 1
        print(f"\n[{processed}/{len(news_links)}] Checking: {news_url}")
        
        # Skip if already scraped
        if news_url in scraped_urls:
            print("  ⏩ Already processed")
            continue
        
        # Extract details
        news_details = extract_news_details(news_url)
        if not news_details:
            print("  ❌ Could not extract details")
            continue
        
        # Format for Facebook
        fb_post, post_id, content_hash = format_for_facebook(news_details)
        
        # Check for duplicate content
        if content_hash in content_hashes:
            print(f"  ⚠️  Duplicate content")
            scraped_urls.add(news_url)
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
            
            counter += 1
            
        except Exception as e:
            print(f"  ❌ Error saving: {e}")
        
        # Polite delay
        time.sleep(1)
    
    # Save state
    save_scraped_data(scraped_urls, content_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New posts created: {len(new_posts)}")
    
    return new_posts

def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 DŽ BIHAC News Scraper - IMPROVED")
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
