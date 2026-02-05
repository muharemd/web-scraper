#!/usr/bin/env python3
"""
Vodovod Bihać Utility Scraper for Facebook Auto-Posting
Scrapes: https://www.vodovod-bihac.ba/
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
BASE_URL = "https://www.vodovod-bihac.ba/"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "vodovod_bihac_state.json"
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

def extract_announcement_details(announcement_url):
    """Extract details from an announcement page"""
    try:
        print(f"  Fetching: {announcement_url}")
        response = requests.get(announcement_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title - utility announcements often have specific structure
        title = "Obavještenje Vodovoda Bihać"
        title_selectors = [
            'h1', 'h2', 'h3',
            '.naslov', '.title', '.article-title',
            '.obavijest-title', '.announcement-title',
            'meta[property="og:title"]'
        ]
        
        for selector in title_selectors:
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'og:title'})
                if elem:
                    title_text = elem.get('content', '')
                    if title_text and "vodovod" in title_text.lower():
                        title = clean_text(title_text)
                        break
            else:
                elem = soup.select_one(selector)
                if elem:
                    title_text = clean_text(elem.get_text())
                    if title_text and len(title_text) > 10:
                        title = title_text
                        break
        
        # For utility sites, content is often directly in the page
        content = ""
        content_selectors = [
            '.content', '.text', '.article',
            '.obavijest', '.announcement',
            '.vijest', '.post',
            'div[itemprop="articleBody"]',
            'main', 'article'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove unwanted elements
                for tag in elem(['script', 'style', 'iframe', 'nav', 'footer', 'header', 'aside', 'form']):
                    tag.decompose()
                
                text = clean_text(elem.get_text())
                if len(text) > 50:
                    content = text
                    break
        
        # If no structured content found, get all meaningful text
        if len(content) < 100:
            # Look for paragraphs and lists (common for utility announcements)
            paragraphs = soup.find_all(['p', 'li', 'div'])
            meaningful_text = []
            
            for elem in paragraphs:
                text = clean_text(elem.get_text())
                # Filter out navigation, menus, etc.
                if (len(text) > 30 and 
                    not any(word in text.lower() for word in ['menu', 'home', 'contact', 'copyright', 'sva prava']) and
                    not re.match(r'^[\d\W]+$', text)):
                    meaningful_text.append(text)
            
            if meaningful_text:
                content = ' '.join(meaningful_text[:10])
        
        # Extract date - crucial for utility announcements
        date = datetime.now().strftime("%Y-%m-%d")
        date_selectors = [
            '.datum', '.date', '.objavljeno',
            '.published', '.vrijeme', '.time',
            'time', 'span.date', 'div.date',
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
                        # Look for date patterns common in Bosnian
                        patterns = [
                            r'\d{2}\.\d{2}\.\d{4}',  # DD.MM.YYYY
                            r'\d{4}-\d{2}-\d{2}',     # YYYY-MM-DD
                            r'\d{2}/\d{2}/\d{4}',     # DD/MM/YYYY
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, date_text)
                            if match:
                                found_date = match.group(0)
                                # Convert to YYYY-MM-DD
                                if '.' in found_date:
                                    day, month, year = found_date.split('.')
                                    if len(day) == 2 and len(month) == 2:  # DD.MM.YYYY
                                        date = f"{year}-{month}-{day}"
                                    else:  # Might be YYYY.MM.DD
                                        date = found_date.replace('.', '-')
                                elif '/' in found_date:
                                    day, month, year = found_date.split('/')
                                    date = f"{year}-{month}-{day}"
                                else:
                                    date = found_date
                                break
        
        # Extract image - utility sites might have logos or diagrams
        image_url = None
        img_selectors = [
            'meta[property="og:image"]',
            '.featured-image img',
            '.post-image img',
            'img[src*="vod"]',
            'img[alt*="vodovod"]',
            'img[title*="vod"]',
            'img:not([src*="icon"]):not([src*="logo"])'
        ]
        
        for selector in img_selectors:
            if selector.startswith('meta'):
                elem = soup.find('meta', {'property': 'og:image'})
                if elem:
                    img_src = elem.get('content', '')
                    if img_src:
                        image_url = urljoin(announcement_url, img_src)
                        break
            else:
                elem = soup.select_one(selector)
                if elem and elem.get('src'):
                    img_src = elem.get('src')
                    if img_src:
                        image_url = urljoin(announcement_url, img_src)
                        break
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'url': announcement_url,
            'image_url': image_url,
            'source': 'Vodovod Bihać',
            'type': 'utility_announcement'
        }
        
    except Exception as e:
        print(f"  Error extracting details: {e}")
        return None

def format_for_facebook(announcement_data):
    """Format the utility announcement for Facebook post"""
    # Create ID from URL hash
    post_id = hashlib.md5(announcement_data['url'].encode()).hexdigest()[:8]
    
    # Generate content hash
    content_hash = generate_content_hash(announcement_data['content'])
    
    # Format content specifically for utility announcements
    fb_content = f"🚨 VAŽNA OBAVIJEST 🚨\n"
    fb_content += f"📅 Datum: {announcement_data['date']}\n\n"
    
    # Add the announcement content
    if len(announcement_data['content']) > 700:
        fb_content += announcement_data['content'][:700] + "..."
    else:
        fb_content += announcement_data['content']
    
    # Add utility-specific information
    fb_content += f"\n\n💧 Izvor: Vodovod Bihać"
    fb_content += f"\n🔗 Više informacija: {announcement_data['url']}"
    fb_content += f"\n📞 Za pitanja: Pogledajte službeni sajt"
    fb_content += f"\n#VodovodBihac #Vodosnabdijevanje #Bihac"
    
    # Create JSON structure
    fb_post = {
        "title": announcement_data['title'],
        "id": post_id,
        "content": fb_content,
        "url": announcement_data['url'],
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": "Vodovod Bihać",        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": announcement_data['date'],
        "type": "utility_announcement",
        "hashtags": ["VodovodBihac", "Vodosnabdijevanje", "Bihac"]
    }
    
    if announcement_data.get('image_url'):
        fb_post["image_url"] = announcement_data['image_url']
    
    return fb_post, post_id, content_hash

def scrape_announcement_links():
    """Scrape the main page for utility announcement links"""
    try:
        print(f"Scraping Vodovod Bihać: {BASE_URL}")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        announcement_links = []
        
        # Strategy 1: Look for announcement/notice links
        # Utility sites often have sections like "Obavijesti", "Vijesti", "Aktuelno"
        print("Looking for utility announcements...")
        
        # Common utility site link patterns
        announcement_patterns = [
            'obavijest', 'obavjest', 'vijest', 'novost',
            'aktuelno', 'aktualno', 'news', 'announcement',
            'prekidi', 'planirani', 'održavanje', 'servis'
        ]
        
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            link_text = clean_text(link.get_text())
            link_lower = link_text.lower()
            
            # Skip empty or non-announcement links
            if not href or href.startswith(('#', 'javascript:', 'mailto:')):
                continue
            
            # Check if it's an announcement link
            is_announcement = False
            
            # Check link text for announcement keywords
            for pattern in announcement_patterns:
                if pattern in link_lower and len(link_text) > 5:
                    is_announcement = True
                    break
            
            # Check URL pattern
            if not is_announcement and href:
                href_lower = href.lower()
                for pattern in announcement_patterns:
                    if pattern in href_lower:
                        is_announcement = True
                        break
            
            if is_announcement:
                # Make URL absolute
                if not href.startswith('http'):
                    full_url = urljoin(BASE_URL, href)
                else:
                    full_url = href
                
                if full_url not in announcement_links and full_url != BASE_URL:
                    announcement_links.append(full_url)
                    print(f"  Found announcement: {link_text[:50]}...")
        
        # Strategy 2: Look for date-stamped items (common in utility announcements)
        date_pattern = re.compile(r'\d{2}\.\d{2}\.\d{4}')
        all_text = soup.get_text()
        dates = date_pattern.findall(all_text)
        
        if dates and len(announcement_links) < 3:
            print(f"Found {len(dates)} date stamps, site might have news feed")
            # This site might have announcements directly on main page
            # We'll handle this in the main function
        
        # Remove duplicates
        unique_links = []
        seen = set()
        for link in announcement_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        print(f"Total announcement links: {len(unique_links)}")
        return unique_links[:8]  # Limit to 8 announcements
        
    except Exception as e:
        print(f"Error scraping announcement links: {e}")
        return []

def extract_from_main_page():
    """Extract announcements directly from main page if no separate pages"""
    try:
        print("Extracting announcements from main page content...")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        announcements = []
        
        # Look for announcement sections
        announcement_sections = soup.find_all(['div', 'section', 'article'], 
                                             class_=re.compile(r'obavijest|vijest|novost|aktuel|news', re.I))
        
        if announcement_sections:
            print(f"Found {len(announcement_sections)} announcement sections")
            
            for i, section in enumerate(announcement_sections[:5]):  # Limit to 5
                # Extract title
                title_elem = section.find(['h2', 'h3', 'h4', 'strong', 'b'])
                title = "Obavještenje Vodovoda Bihać"
                if title_elem:
                    title = clean_text(title_elem.get_text())
                
                # Extract content
                content = clean_text(section.get_text())
                
                # Extract date
                date = datetime.now().strftime("%Y-%m-%d")
                date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', content)
                if date_match:
                    day, month, year = date_match.group(0).split('.')
                    date = f"{year}-{month}-{day}"
                
                # Create pseudo-URL
                title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                pseudo_url = f"{BASE_URL}#announcement_{title_hash}"
                
                announcements.append({
                    'title': title,
                    'content': content,
                    'date': date,
                    'url': pseudo_url,
                    'image_url': None,
                    'source': 'Vodovod Bihać',
                    'type': 'utility_announcement',
                    'from_main_page': True
                })
        
        return announcements
        
    except Exception as e:
        print(f"Error extracting from main page: {e}")
        return []

def scrape_latest_announcements():
    """Main scraping function for utility announcements"""
    print(f"Script: {SCRIPT_NAME} (hash: {SCRIPT_NAME_HASH})")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    ensure_dirs()
    scraped_urls, content_hashes = load_scraped_data()
    new_posts = []
    
    # Try to get announcement links first
    announcement_links = scrape_announcement_links()
    
    if announcement_links:
        # Process individual announcement pages
        print(f"\nProcessing {len(announcement_links)} announcement pages...")
        
        counter = 1
        
        for announcement_url in announcement_links:
            print(f"\n[{counter}/{len(announcement_links)}] Checking: {announcement_url}")
            
            # Skip if already scraped
            if announcement_url in scraped_urls:
                print("  ⏩ Already processed")
                counter += 1
                continue
            
            # Extract details
            announcement_details = extract_announcement_details(announcement_url)
            if not announcement_details:
                print("  ❌ Could not extract details")
                counter += 1
                continue
            
            print(f"  Title: {announcement_details['title'][:60]}...")
            print(f"  Date: {announcement_details.get('date', 'N/A')}")
            
            # Format for Facebook
            fb_post, post_id, content_hash = format_for_facebook(announcement_details)
            
            print(f"  Content hash: {content_hash}")
            
            # Check for duplicate content
            if content_hash in content_hashes:
                print(f"  ⚠️  Duplicate content detected")
                scraped_urls.add(announcement_url)
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
                scraped_urls.add(announcement_url)
                content_hashes.add(content_hash)
                new_posts.append({
                    'filename': filename,
                    'title': announcement_details['title'],
                    'url': announcement_url,
                    'post_id': post_id
                })
                
            except Exception as e:
                print(f"  ❌ Error saving: {e}")
            
            counter += 1
            time.sleep(2)
    
    else:
        # If no individual pages, extract from main page
        print("\nNo individual announcement pages found, extracting from main page...")
        announcements = extract_from_main_page()
        
        if announcements:
            print(f"\nProcessing {len(announcements)} announcements from main page...")
            
            counter = 1
            
            for announcement in announcements:
                print(f"\n[{counter}/{len(announcements)}] {announcement['title'][:60]}...")
                print(f"  Date: {announcement['date']}")
                print(f"  Content: {len(announcement['content'])} chars")
                
                # Format for Facebook
                fb_post, post_id, content_hash = format_for_facebook(announcement)
                
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
                    content_hashes.add(content_hash)
                    new_posts.append({
                        'filename': filename,
                        'title': announcement['title'],
                        'url': announcement['url'],
                        'post_id': post_id
                    })
                    
                except Exception as e:
                    print(f"  ❌ Error saving: {e}")
                
                counter += 1
    
    # Save state
    save_scraped_data(scraped_urls, content_hashes)
    
    print(f"\n" + "=" * 60)
    print(f"Scraping completed!")
    print(f"New announcements posted: {len(new_posts)}")
    
    return new_posts

def main():
    """Main entry point"""
    print("=" * 60)
    print("🚰 Vodovod Bihać Utility Announcement Scraper")
    print("=" * 60)
    print(f"Script: {SCRIPT_NAME}")
    print(f"Script hash: {SCRIPT_NAME_HASH}")
    print(f"Target: {BASE_URL}")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)
    
    new_posts = scrape_latest_announcements()
    
    if new_posts:
        print("\n📋 NEW ANNOUNCEMENTS CREATED:")
        for post in new_posts:
            print(f"  📄 {post['filename']}")
            print(f"    {post['title'][:70]}...")
            print(f"    🔗 {post['url']}")
            print()
    else:
        print("\nℹ️  No new announcements found.")
    
    print(f"✅ Check the '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)

if __name__ == "__main__":
    main()
