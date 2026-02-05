#!/usr/bin/env python3
"""
KC Bihać News Scraper for Facebook Auto-Posting
Scrapes: https://kcbihac.ba/novosti.php
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
BASE_URL = "https://kcbihac.ba/novosti.php"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "kcbihac_state.json"
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
            '.naslov', '.title', '.article-title',
            '.post-title', '.news-title',
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
        
        # Extract content - look for specific patterns for this site
        content = ""
        content_selectors = [
            '.sadrzaj', '.content', '.text',
            '.clanak', '.article', '.post',
            '.vijest', '.news-content',
            'div[class*="sadrzaj"]', 'div[class*="content"]',
            'div[class*="clanak"]', 'div[class*="vijest"]'
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
            # Look for main content area
            main_selectors = [
                '#main', '#content', '#sadrzaj',
                'main', 'article',
                'div.container', 'div.wrapper',
                'table[width="100%"]'  # Common in older PHP sites
            ]
            
            for selector in main_selectors:
                elem = soup.select_one(selector)
                if elem:
                    # Remove navigation and other non-content elements
                    for tag in elem(['script', 'style', 'iframe', 'nav', 'menu', 'form']):
                        tag.decompose()
                    
                    # Remove tables that might be layout tables
                    for table in elem.find_all('table'):
                        if table.get('width') == '100%' or table.get('cellpadding'):
                            # Might be layout table, skip
                            continue
                    
                    text = clean_text(elem.get_text())
                    if len(text) > 150:
                        content = text
                        break
        
        # Last resort: extract paragraphs
        if len(content) < 100:
            paragraphs = soup.find_all('p')
            meaningful_paras = []
            for p in paragraphs:
                text = clean_text(p.get_text())
                if len(text) > 30 and not any(word in text.lower() for word in ['copyright', 'sva prava', 'design', 'menu', 'home']):
                    meaningful_paras.append(text)
            
            if meaningful_paras:
                content = ' '.join(meaningful_paras[:5])
        
        # Extract date
        date = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            '.datum', '.date', '.vrijeme', '.time',
            '.objavljeno', '.published',
            'td[align="right"]', 'td[valign="top"]',  # Common in table layouts
            'font[size="1"]', 'span[class*="datum"]',
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
                        # Look for date patterns
                        patterns = [
                            r'\d{2}\.\d{2}\.\d{4}',  # DD.MM.YYYY
                            r'\d{4}-\d{2}-\d{2}',     # YYYY-MM-DD
                            r'\d{2}/\d{2}/\d{4}',     # DD/MM/YYYY
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, date_text)
                            if match:
                                found_date = match.group(0)
                                # Convert DD.MM.YYYY to YYYY-MM-DD
                                if '.' in found_date:
                                    day, month, year = found_date.split('.')
                                    date = f"{year}-{month}-{day}"
                                elif '/' in found_date:
                                    day, month, year = found_date.split('/')
                                    date = f"{year}-{month}-{day}"
                                else:
                                    date = found_date
                                break
                        
                        if date != datetime.now().strftime("%Y-%m-%d"):
                            break
        
        # Extract image
        image_url = None
        img_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'img[src*="slike"]',  # Common for images directory
            'img[src*="images"]',
            'img[src*="upload"]',
            '.slika img', '.image img',
            'img[border="0"]',  # Common in older sites
            'img:not([src*="icon"]):not([src*="logo"])'  # Any image not icon/logo
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
                elems = soup.select(selector)
                for elem in elems:
                    if elem.get('src'):
                        img_src = elem.get('src')
                        # Skip tiny images (likely icons)
                        if (img_src and 
                            not any(word in img_src.lower() for word in ['icon', 'logo', 'spacer', 'pixel']) and
                            not img_src.endswith(('.gif', '.ico'))):
                            image_url = urljoin(news_url, img_src)
                            break
                if image_url:
                    break
        
        # If no image found, use site logo as fallback
        if not image_url:
            logo_selectors = [
                'img[src*="logo"]',
                'img[alt*="logo"]',
                'img[title*="logo"]',
                'img[src*="banner"]'
            ]
            for selector in logo_selectors:
                elem = soup.select_one(selector)
                if elem and elem.get('src'):
                    image_url = urljoin(news_url, elem.get('src'))
                    break
        
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
        "source_name": "Kantonalni centar",        "content_hash": content_hash,
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
        
        # Strategy 1: Look for links in common news containers
        # This site might use tables or divs for layout
        link_patterns = [
            r'novosti\.php\?',  # novosti.php?id=123
            r'clanak\.php\?',   # clanak.php?id=456
            r'vijest\.php\?',   # vijest.php?id=789
            r'\/novosti\/',     # /novosti/some-article
            r'index\.php\?.*id=', # index.php?id=123&page=novosti
        ]
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            link_text = clean_text(link.get_text())
            
            # Skip empty or non-news links
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue
            
            # Check if it's a news link
            is_news_link = False
            
            # Check URL patterns
            for pattern in link_patterns:
                if re.search(pattern, href, re.I):
                    is_news_link = True
                    break
            
            # Check link text for news indicators
            if not is_news_link and len(link_text) > 10:
                news_keywords = ['vijest', 'novost', 'clanak', 'objava', 'obavijest', 'news', 'article']
                if any(keyword in link_text.lower() for keyword in news_keywords):
                    is_news_link = True
            
            # Check if it's not the current page or navigation
            if is_news_link and href != 'novosti.php' and not href.startswith('http'):
                full_url = urljoin(BASE_URL, href)
                if full_url not in news_links and full_url != BASE_URL:
                    news_links.append(full_url)
                    print(f"  Found link: {link_text[:50]}... -> {href}")
        
        # Strategy 2: Look for tables that might contain news (common in PHP sites)
        if len(news_links) < 5:
            print("Looking for news in tables...")
            tables = soup.find_all('table')
            for table in tables:
                # Check if table might contain news (has multiple rows/cells)
                rows = table.find_all('tr')
                if len(rows) > 2:
                    for row in rows:
                        links = row.find_all('a', href=True)
                        for link in links:
                            href = link.get('href')
                            if href and any(pattern in href for pattern in ['?id=', 'clanak', 'vijest']):
                                full_url = urljoin(BASE_URL, href)
                                if full_url not in news_links:
                                    news_links.append(full_url)
        
        # Strategy 3: Look for pagination to get more news
        pagination_links = soup.find_all('a', href=re.compile(r'novosti\.php\?.*strana=|.*page=|.*start=', re.I))
        if pagination_links and len(news_links) < 10:
            print("Found pagination, checking next page...")
            for page_link in pagination_links[:2]:  # Check first 2 pagination links
                page_text = page_link.get_text().strip()
                if page_text in ['2', '>>', 'next', 'dalje']:
                    page_url = urljoin(BASE_URL, page_link.get('href'))
                    try:
                        response2 = requests.get(page_url, headers=HEADERS, timeout=10)
                        soup2 = BeautifulSoup(response2.content, 'html.parser')
                        
                        # Extract links from page 2
                        for link in soup2.find_all('a', href=re.compile(r'novosti\.php\?|clanak\.php\?', re.I)):
                            href = link.get('href')
                            if href:
                                full_url = urljoin(BASE_URL, href)
                                if full_url not in news_links:
                                    news_links.append(full_url)
                    except:
                        print("Could not fetch additional page")
        
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
        print(f"  Content length: {len(news_details['content'])} chars")
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
    print("🚀 KC Bihać News Scraper")
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
