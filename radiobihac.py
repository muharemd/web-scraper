#!/usr/bin/env python3
"""
Radio Bihać News Scraper for Facebook Auto-Posting
Scrapes: https://www.radiobihac.com
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
BASE_URL = "https://www.radiobihac.com"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "radiobihac_state.json"
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
    """Extract full details from a news article page"""
    try:
        print(f"  Fetching: {news_url}")
        response = requests.get(news_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = "No Title"
        title_selectors = [
            'h1', 'h2', 'h3',
            '.article-title', '.post-title', '.news-title',
            '.title', '.naslov',
            'meta[property="og:title"]',
            'title'
        ]
        
        for selector in title_selectors:
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'og:title'})
                if elem:
                    title = clean_text(elem.get('content', ''))
                    if title and title != "No Title":
                        break
            else:
                elem = soup.select_one(selector)
                if elem:
                    title_text = clean_text(elem.get_text())
                    if title_text and title_text != "No Title":
                        title = title_text
                        break
        
        # Extract content - Radio Bihać specific
        content = ""
        content_selectors = [
            '.article-content', '.post-content', '.news-content',
            '.content', '.text', '.clanak',
            'div[itemprop="articleBody"]',
            '.entry-content', '.vijest-content'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove unwanted elements
                for tag in elem(['script', 'style', 'iframe', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                
                text = clean_text(elem.get_text())
                if len(text) > 100:
                    content = text
                    break
        
        # If no content found, try broader approach
        if len(content) < 100:
            # Look for main content area
            main_elem = soup.find('main') or soup.find('article') or soup.find('div', {'role': 'main'})
            if main_elem:
                for tag in main_elem(['script', 'style', 'iframe', 'nav', 'aside']):
                    tag.decompose()
                content = clean_text(main_elem.get_text())
        
        # Extract date from the page
        date = datetime.now().strftime("%Y-%m-%d")
        
        # Look for date in various formats
        date_selectors = [
            'time',
            '.date', '.post-date', '.article-date',
            '.published', '.vrijeme',
            'meta[property="article:published_time"]',
            'span.date', 'div.date'
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
                        # Look for various date formats
                        patterns = [
                            r'\d{2}\.\d{2}\.\d{4}',  # DD.MM.YYYY
                            r'\d{4}-\d{2}-\d{2}',     # YYYY-MM-DD
                            r'\d{4}\.\d{2}\.\d{2}',   # YYYY.MM.DD
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, date_text)
                            if match:
                                found_date = match.group(0)
                                # Convert DD.MM.YYYY to YYYY-MM-DD
                                if found_date.count('.') == 2:
                                    parts = found_date.split('.')
                                    if len(parts[0]) == 4:  # YYYY.MM.DD
                                        date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                                    else:  # DD.MM.YYYY
                                        date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                                else:
                                    date = found_date
                                break
        
        # Extract image
        image_url = None
        img_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.featured-image img',
            '.post-thumbnail img',
            '.article-image img',
            'img.wp-post-image',
            'figure img',
            'img[src*="upload"]'
        ]
        
        for selector in img_selectors:
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
        
        # Fallback to site logo
        if not image_url:
            logo_elem = soup.find('img', src=re.compile(r'logo', re.I))
            if logo_elem and logo_elem.get('src'):
                image_url = urljoin(news_url, logo_elem.get('src'))
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'url': news_url,
            'image_url': image_url,
            'source': 'Radio Bihać'
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
    
    # Format content for Facebook
    if len(news_data['content']) > 800:
        fb_content = news_data['content'][:800] + "..."
    else:
        fb_content = news_data['content']
    
    # Add source and read more
    if fb_content:
        fb_content += f"\n\n📻 Izvor: Radio Bihać"
        fb_content += f"\n🔗 Pročitaj više: {news_data['url']}"
    
    # Create JSON structure
    fb_post = {
        "title": news_data['title'],
        "id": post_id,
        "content": fb_content,
        "url": news_data['url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "Radio Bihać",        "content_hash": content_hash,
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
        print(f"Scraping Radio Bihać: {BASE_URL}")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        news_links = []
        
        # Strategy 1: Look for article links in the "AKTUELNO" section
        # The site shows date-stamped news items
        print("Looking for news articles...")
        
        # Find all links that might be news articles
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            link_text = clean_text(link.get_text())
            
            # Skip empty or non-article links
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue
            
            # Check if it's likely a news article
            is_news_article = False
            
            # Check link text length and content
            if len(link_text) > 20 and not any(word in link_text.lower() for word in ['emisija', 'program', 'kontakt', 'o nama']):
                is_news_article = True
            
            # Check URL pattern
            if any(pattern in href.lower() for pattern in ['clanak', 'vijest', 'novost', 'news', 'article']):
                is_news_article = True
            
            if is_news_article:
                # Make URL absolute
                if not href.startswith('http'):
                    full_url = urljoin(BASE_URL, href)
                else:
                    full_url = href
                
                if full_url not in news_links and full_url != BASE_URL:
                    news_links.append(full_url)
                    print(f"  Found: {link_text[:60]}...")
        
        # Strategy 2: Look for date-stamped items (like in the provided content)
        # The content shows dates like "02.02.2026" followed by text
        date_pattern = re.compile(r'\d{2}\.\d{2}\.\d{4}')
        all_text = soup.get_text()
        
        # Find dates in text and extract following content
        dates = date_pattern.findall(all_text)
        print(f"Found {len(dates)} date stamps on page")
        
        # If we found dates but not many links, the site might use a different structure
        if len(news_links) < 5 and len(dates) > 0:
            print("Site might use a single-page news feed, extracting from main page...")
            # Extract news directly from main page content
            return []  # We'll handle this differently below
        
        # Remove duplicates
        unique_links = []
        seen = set()
        for link in news_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        print(f"Total unique article links: {len(unique_links)}")
        return unique_links[:10]  # Limit to 10 articles
        
    except Exception as e:
        print(f"Error scraping news links: {e}")
        return []

def extract_news_from_main_page():
    """Extract news directly from the main page (if no separate article pages)"""
    try:
        print("Extracting news from main page content...")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        news_items = []
        
        # Get all text
        all_text = soup.get_text()
        
        # Look for date patterns followed by content
        date_pattern = re.compile(r'(\d{2}\.\d{2}\.\d{4})\s+(.+?)(?=\d{2}\.\d{2}\.\d{4}|$)', re.DOTALL)
        
        matches = list(date_pattern.finditer(all_text))
        print(f"Found {len(matches)} news items by date pattern")
        
        for i, match in enumerate(matches[:10]):  # Limit to 10
            date_str = match.group(1)
            content = match.group(2).strip()
            
            # Clean up content
            content = clean_text(content)
            
            # Extract title (first sentence or first 100 chars)
            if len(content) > 100:
                title = content[:100].split('.')[0] + '...'
            else:
                title = content
            
            # Convert date format
            day, month, year = date_str.split('.')
            date = f"{year}-{month}-{day}"
            
            # Create a pseudo-URL for tracking
            title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
            pseudo_url = f"{BASE_URL}#news_{title_hash}"
            
            news_items.append({
                'title': title,
                'content': content,
                'date': date,
                'url': pseudo_url,
                'image_url': None,
                'source': 'Radio Bihać',
                'from_main_page': True
            })
        
        return news_items
        
    except Exception as e:
        print(f"Error extracting from main page: {e}")
        return []

def scrape_latest_news():
    """Main scraping function"""
    print(f"Script: {SCRIPT_NAME} (hash: {SCRIPT_NAME_HASH})")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    ensure_dirs()
    scraped_urls, content_hashes = load_scraped_data()
    new_posts = []
    
    # Try to get news links first
    news_links = scrape_news_links()
    
    if news_links:
        # Process individual article pages
        print(f"\nProcessing {len(news_links)} article pages...")
        
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
            time.sleep(2)
    
    else:
        # If no individual article pages, extract from main page
        print("\nNo individual article pages found, extracting from main page...")
        news_items = extract_news_from_main_page()
        
        if news_items:
            print(f"\nProcessing {len(news_items)} news items from main page...")
            
            counter = 1
            
            for news_item in news_items:
                print(f"\n[{counter}/{len(news_items)}] {news_item['title'][:60]}...")
                print(f"  Date: {news_item['date']}")
                print(f"  Content: {len(news_item['content'])} chars")
                
                # Format for Facebook
                fb_post, post_id, content_hash = format_for_facebook(news_item)
                
                print(f"  Content hash: {content_hash}")
                
                # Check for duplicate content
                if content_hash in content_hashes:
                    print(f"  ⚠️  Duplicate content detected")
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
                    if not news_item.get('from_main_page', False):
                        scraped_urls.add(news_item['url'])
                    content_hashes.add(content_hash)
                    new_posts.append({
                        'filename': filename,
                        'title': news_item['title'],
                        'url': news_item['url'],
                        'post_id': post_id
                    })
                    
                except Exception as e:
                    print(f"  ❌ Error saving: {e}")
                
                counter += 1
    
    # Save state
    save_scraped_data(scraped_urls, content_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New posts created: {len(new_posts)}")
    
    return new_posts

def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 Radio Bihać News Scraper")
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
