#!/usr/bin/env python3
"""
Oslobođenje RSS Feed Importer - ALL articles
Fetches ALL articles from Oslobođenje RSS feed
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime
import re
import html
import feedparser

# ================== CONFIG ==================
FEED_URL = "https://www.oslobodjenje.ba/rss.xml"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "oslobodjenje_rss_state.json"
SOURCE_NAME = "Oslobođenje"
SCRIPT_NAME = "oslobodjenje_rss_all.py"
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]
MAX_CONTENT_LEN = 800
# ============================================

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = text.replace("\r\n", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def generate_content_hash(content):
    if not content:
        return ""
    clean = " ".join(content.split()).lower()
    return hashlib.md5(clean.encode()).hexdigest()[:12]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "scraped_urls": [],
            "content_hashes": [],
            "counters": {},
            "last_run": None,
            "script_name": SCRIPT_NAME,
        }
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def fetch_rss():
    """Fetch RSS feed using curl"""
    cmd = ["curl", "-s", "-L", FEED_URL]
    try:
        return subprocess.check_output(cmd, timeout=30)
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return b""

def extract_image(entry):
    """Extract image from RSS entry"""
    # Check media content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'url' in media:
                return media['url']
    
    # Check enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'href' in enc:
                return enc['href']
    
    # Check description for img tags
    if hasattr(entry, 'description'):
        img_match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
        if img_match:
            return img_match.group(1)
    
    return None

def get_entry_date(entry):
    """Extract date from entry"""
    # Try published_parsed first
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    
    # Try updated_parsed
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    
    # Fallback to today
    return datetime.now().strftime("%Y-%m-%d")

def format_post(entry):
    """Format RSS entry for Facebook"""
    # Title
    title = clean_text(getattr(entry, 'title', 'Vijest'))
    
    # URL - THIS SHOULD BE THE ARTICLE URL, NOT RSS FEED
    url = getattr(entry, 'link', '')
    if not url:
        print(f"WARNING: Entry has no URL. Title: {title[:50]}...")
        return None, None, None, None
    
    # ID from URL hash
    post_id = hashlib.md5(url.encode()).hexdigest()[:8]
    
    # Content
    description = getattr(entry, 'description', '')
    content = re.sub(r'<[^>]+>', ' ', description)
    content = html.unescape(content)
    content = clean_text(content)
    
    # Facebook content
    fb_content = f"{title}\n\n{content}" if content else title
    
    # Truncate if needed
    if len(fb_content) > MAX_CONTENT_LEN:
        fb_content = fb_content[:MAX_CONTENT_LEN] + "..."
    
    # Add footer
    fb_content += f"\n\n📺 Izvor: {SOURCE_NAME}"
    if url:
        fb_content += f"\n🔗 Pročitaj više: {url}"
    
    # Date
    date_str = get_entry_date(entry)
    
    # Content hash
    content_hash = generate_content_hash(fb_content)[:12]
    
    # Build post object
    post = {
        "title": title,
        "id": post_id,
        "content": fb_content,
        "url": url,  # This will be the article URL
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": date_str
    }
    
    # Add image if available
    image_url = extract_image(entry)
    if image_url:
        post["image_url"] = image_url
    
    return post, post_id, content_hash, url

def get_next_counter(state, date_str):
    counters = state.get("counters", {})
    last = counters.get(date_str, 0)
    next_val = last + 1
    counters[date_str] = next_val
    state["counters"] = counters
    return next_val

def import_articles():
    print("=" * 60)
    print("📰 Oslobođenje RSS Importer - ALL Articles")
    print(f"Time: {datetime.now()}")
    print(f"Feed URL: {FEED_URL}")
    print("=" * 60)
    
    ensure_dirs()
    state = load_state()
    scraped_urls = set(state.get("scraped_urls", []))
    content_hashes = set(state.get("content_hashes", []))
    
    # Fetch RSS
    print("Fetching RSS feed...")
    xml = fetch_rss()
    if not xml:
        print("ERROR: Could not fetch RSS feed")
        return []
    
    # Parse RSS
    feed = feedparser.parse(xml)
    if not feed.entries:
        print("ERROR: No entries in RSS feed")
        return []
    
    print(f"Found {len(feed.entries)} articles in RSS feed")
    
    new_posts = []
    processed = 0
    
    for entry in feed.entries:
        processed += 1
        print(f"\n[{processed}/{len(feed.entries)}] Processing article...")
        
        result = format_post(entry)
        if result[0] is None:
            print("  ⚠️ Skipping - no URL found")
            continue
            
        fb_post, post_id, content_hash, url = result
        
        print(f"  Title: {fb_post['title'][:60]}...")
        print(f"  URL: {url}")
        print(f"  Date: {fb_post['date']}")
        print(f"  Hash: {content_hash}")
        
        # Check for duplicates
        if url in scraped_urls:
            print("  ⏩ Already processed (URL)")
            continue
            
        if content_hash in content_hashes:
            print("  ⏩ Already processed (content hash)")
            scraped_urls.add(url)
            continue
        
        # Create filename
        date_str = fb_post['date']
        date_compact = date_str.replace("-", "")
        counter = get_next_counter(state, date_str)
        filename = f"{SCRIPT_NAME_HASH}-{date_compact}-{counter:03d}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(fb_post, f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ Saved: {filename}")
            
            scraped_urls.add(url)
            content_hashes.add(content_hash)
            
            new_posts.append({
                "filename": filename,
                "title": fb_post["title"],
                "url": url,
                "date": date_str,
            })
            
        except Exception as e:
            print(f"  ❌ Error saving file: {e}")
    
    # Update state
    state["scraped_urls"] = list(scraped_urls)
    state["content_hashes"] = list(content_hashes)
    save_state(state)
    
    print("\n" + "=" * 60)
    print(f"Import completed. Created {len(new_posts)} new posts.")
    print("=" * 60)
    
    if new_posts:
        print("\n📋 NEW POSTS CREATED:")
        for post in new_posts:
            print(f"  📄 {post['filename']}")
            print(f"    {post['title'][:70]}...")
            print(f"    🔗 {post['url']}")
            print()
    
    return new_posts

def main():
    print("🚀 Starting Oslobođenje RSS Importer")
    print(f"Script: {SCRIPT_NAME}")
    print(f"Script hash: {SCRIPT_NAME_HASH}")
    print(f"Output dir: {os.path.abspath(OUTPUT_DIR)}")
    print(f"State file: {STATE_FILE}")
    
    new_posts = import_articles()
    
    if not new_posts:
        print("ℹ️ No new articles found or all articles already processed.")
    
    print(f"✅ Check '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)

if __name__ == "__main__":
    main()
