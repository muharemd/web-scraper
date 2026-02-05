#!/usr/bin/env python3
"""
KBBihac News Scraper for Facebook Auto-Posting
Scrapes: https://www.kbbihac.ba/novosti
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
BASE_URL = "https://www.kbbihac.ba/novosti"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "kbbihac_state.json"
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
            '.article-title', '.post-title', '.entry-title',
            '.title', '.page-title',
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
        
        # Extract content
        content = ""
        content_selectors = [
            'article',
            'main',
            '.article-content', '.post-content', '.entry-content',
            '.content', '.text',
            '.single-content', '.blog-content',
            'div[class*="content"]', 'div[class*="article"]'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove unwanted elements
                for tag in elem(['script', 'style', 'iframe', 'nav', 'footer', 'header', 'aside', 'form']):
                    tag.decompose()
                
                text = clean_text(elem.get_text())
                if len(text) > 100:
                    content = text
                    break
        
        # If no content found, try broader approach
        if len(content) < 100:
            # Remove all script/style elements
            for tag in soup(['script', 'style', 'iframe', 'nav', 'header', 'footer']):
                tag.decompose()
            
            # Try to find main content
            main_elem = soup.find('main') or soup.find('article') or soup.find('div', {'role': 'main'})
            if main_elem:
                content = clean_text(main_elem.get_text())
            else:
                # Last resort: get body text
                content = clean_text(soup.get_text())
        
        # Extract date
        date = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            'time',
            '.date', '.post-date', '.article-date', '.published',
            '.created', '.datetime',
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            'span[class*="date"]', 'div[class*="date"]'
        ]
        
        for selector in date_selectors:
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'article:published_time'}) or soup.find('meta', {'name': 'date'})
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
            '.featured-image img',
            '.post-thumbnail img',
            '.article-image img',
            '.single-image img',
            'img.wp-post-image',
            'figure img',
            'img[src*="upload"]',
            'img[src*="image"]'
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
        
        # If no image found, look for site logo
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
        "source_name": "Kantonalna bolnica",        "content_hash": content_hash,
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
        
        # Strategy 1: Look for article links in common containers
        article_containers = [
            'article', '.post', '.news-item', '.article-item',
            '.blog-item', '.item', '.card', '.news-card'
        ]
        
        for container in article_containers:
            articles = soup.select(f'{container} a[href]')
            if articles:
                print(f"Found articles in {container} container")
                for article in articles[:15]:  # Limit to 15
                    href = article.get('href')
                    if href:
                        full_url = urljoin(BASE_URL, href)
                        # Filter for actual article pages
                        if ('/novosti/' in full_url or '/clanak/' in full_url) and full_url not in news_links:
                            news_links.append(full_url)
        
        # Strategy 2: Look for all links containing news/article patterns
        if len(news_links) < 5:
            all_links = soup.find_all('a', href=True)
            for link in all_links[:30]:  # Check first 30 links
                href = link.get('href')
                if href and any(pattern in href.lower() for pattern in ['novosti', 'clanak', 'news', 'article']):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in news_links and full_url != BASE_URL:
                        news_links.append(full_url)
        
        # Strategy 3: Look for pagination to get more articles
        pagination = soup.find(['ul', 'div'], class_=re.compile(r'pagination|pager', re.I))
        if pagination and len(news_links) < 10:
            print("Found pagination, checking for more pages...")
            # Look for page 2 link
            page2_links = pagination.find_all('a', href=True)
            for link in page2_links:
                link_text = link.get_text().strip()
                if link_text in ['2', 'next', '»', '>']:
                    page2_url = urljoin(BASE_URL, link.get('href'))
                    try:
                        response2 = requests.get(page2_url, headers=HEADERS, timeout=10)
                        soup2 = BeautifulSoup(response2.content, 'html.parser')
                        
                        # Extract links from page 2
                        for link2 in soup2.find_all('a', href=re.compile(r'novosti|clanak', re.I)):
                            href2 = link2.get('href')
                            if href2:
                                full_url2 = urljoin(BASE_URL, href2)
                                if full_url2 not in news_links:
                                    news_links.append(full_url2)
                    except:
                        print("Could not fetch page 2")
                    break
        
        # Remove duplicates and limit
        unique_links = []
        seen = set()
        for link in news_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        print(f"Found {len(unique_links)} unique news links")
        return unique_links[:10]  # Limit to 10 articles
        
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
        
        # Debug info
        print(f"  Title: {news_details['title'][:60]}...")
        print(f"  Content: {len(news_details['content'])} chars")
        print(f"  Content hash: {content_hash}")
        
        # Check for duplicate content
        if content_hash in content_hashes:
            print(f"  ⚠️  Duplicate content detected")
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
        
        # Be polite to the server
        time.sleep(2)
    
    # Save state
    save_scraped_data(scraped_urls, content_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New posts created: {len(new_posts)}")
    
    return new_posts

def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 KB Bihać News Scraper")
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
