#!/usr/bin/env python3
"""
BIHAMK RSS importer for Facebook auto-posting.

- Fetches BIHAMK traffic RSS feed
- Parses traffic updates
- Generates JSON files in facebook_ready_posts/
- Avoids duplicates via content_hash
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

# BIHAMK Traffic RSS feed
FEED_URL = "https://bihamk.ba/spi/stanje-na-cesti-u-bih/rss"

# If you need cookies (Cloudflare etc.), point this to your cookies.txt
COOKIES_FILE = os.path.expanduser(
    "~/snap/newsboat/current/.newsboat/cookies.txt"
)

OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "rss_import_state.json"

# Source identifiers
SOURCE_NAME = "BIHAMK - Stanje na cesti"
SCRIPT_NAME = os.path.basename(sys.argv[0])
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]

# Max content length for Facebook text
MAX_CONTENT_LEN = 800

# ============================================

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(text):
    if not text:
        return ""
    # Decode HTML entities first
    text = html.unescape(text)
    # Replace newlines and multiple spaces
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
            "counters": {},  # date -> last counter
            "last_run": None,
            "script_name": SCRIPT_NAME,
            "script_hash": SCRIPT_NAME_HASH,
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("scraped_urls", [])
    data.setdefault("content_hashes", [])
    data.setdefault("counters", {})
    return data


def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    state["script_name"] = SCRIPT_NAME
    state["script_hash"] = SCRIPT_NAME_HASH
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def fetch_rss_xml():
    """
    Fetch RSS XML using curl + cookies.
    """
    cmd = ["curl", "-s", "-L", FEED_URL]
    if os.path.exists(COOKIES_FILE):
        cmd[1:1] = ["-b", COOKIES_FILE]

    try:
        xml = subprocess.check_output(cmd, timeout=30)
        return xml
    except Exception as e:
        print(f"[ERROR] fetching RSS via curl: {e}")
        return b""


def parse_rss_entries(xml_bytes):
    feed = feedparser.parse(xml_bytes)
    return feed.entries or []


def extract_image_from_entry(entry):
    """BIHAMK traffic feed doesn't typically have images"""
    return None


def get_entry_date(entry):
    # BIHAMK feed uses pubDate
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    
    # Try pubDate directly
    if hasattr(entry, "pubDate"):
        # Extract date from string like "Tue, 11 Mar 2025 14:30:00 +0100"
        patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}\.\d{2}\.\d{4}",
            r"(\d{1,2})\s+(\w+)\s+(\d{4})",  # 11 Mar 2025
        ]
        
        pub_date_str = entry.pubDate
        
        for pattern in patterns:
            m = re.search(pattern, pub_date_str)
            if m:
                if pattern == r"(\d{1,2})\s+(\w+)\s+(\d{4})":
                    day, month_str, year = m.groups()
                    month_map = {
                        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                    }
                    month = month_map.get(month_str, '01')
                    return f"{year}-{month}-{day.zfill(2)}"
                else:
                    return m.group(0)
    
    # Fallback: today
    return datetime.now().strftime("%Y-%m-%d")


def format_bihamk_traffic_post(entry):
    """Format BIHAMK traffic entry for Facebook"""
    
    # Title from RSS
    title = clean_text(getattr(entry, "title", "") or "Saobraćajna informacija")
    
    # URL - BIHAMK entries might not have links, use feed URL
    url = getattr(entry, "link", "") or FEED_URL
    
    # ID: short hash of URL (like in your example)
    post_id = hashlib.md5(url.encode()).hexdigest()[:8] if url else hashlib.md5(
        title.encode()
    ).hexdigest()[:8]
    
    # Description/content
    description = getattr(entry, "description", "") or ""
    content = clean_text(description)
    
    # Format for Facebook - match your example format
    if not content:
        fb_content = f"{title}"
    else:
        # Clean and format the content
        content = re.sub(r'<[^>]+>', '', content)  # Remove HTML tags
        content = html.unescape(content)
        
        # Use the title as first line, then content
        fb_content = f"{title}\n\n{content}"
        
        # Truncate if too long
        if len(fb_content) > MAX_CONTENT_LEN:
            fb_content = fb_content[:MAX_CONTENT_LEN] + "..."
    
    # Add footer exactly like your example
    fb_content += f"\n\n📺 Izvor: {SOURCE_NAME}"
    fb_content += f"\n🔗 Pročitaj više: {url}"
    
    # Date for filename
    date_str = get_entry_date(entry)
    
    # Content hash - 12 chars like in your example
    content_hash = generate_content_hash(fb_content)[:12]
    
    # Create JSON exactly matching your example format
    fb_post = {
        "title": title,
        "id": post_id,
        "content": fb_content,
        "url": url,
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": date_str
    }
    
    # BIHAMK typically doesn't have images, but if it does, add it
    image_url = extract_image_from_entry(entry)
    if image_url:
        fb_post["image_url"] = image_url
    
    return fb_post, post_id, content_hash, url


def get_next_counter(state, date_str):
    counters = state.get("counters", {})
    last = counters.get(date_str, 0)
    next_val = last + 1
    counters[date_str] = next_val
    state["counters"] = counters
    return next_val


def import_bihamk_rss():
    print(f"Script: {SCRIPT_NAME} (hash: {SCRIPT_NAME_HASH})")
    print(f"Time:   {datetime.now()}")
    print(f"Feed:   BIHAMK Traffic Updates")
    print("=" * 60)

    ensure_dirs()
    state = load_state()
    scraped_urls = set(state.get("scraped_urls", []))
    content_hashes = set(state.get("content_hashes", []))

    xml = fetch_rss_xml()
    if not xml:
        print("No RSS data fetched.")
        return []

    entries = parse_rss_entries(xml)
    if not entries:
        print("No entries found in RSS.")
        return []

    print(f"Found {len(entries)} traffic updates.")
    new_posts = []

    processed = 0
    for entry in entries:
        processed += 1
        print(f"\n[{processed}/{len(entries)}] Processing traffic update...")

        fb_post, post_id, content_hash, url = format_bihamk_traffic_post(entry)

        print(f"  Title: {fb_post['title'][:60]}...")
        print(f"  Date:  {fb_post['date']}")
        print(f"  Hash:  {content_hash}")

        # Skip if content hash already seen
        if content_hash and content_hash in content_hashes:
            print("  ⚠️ Duplicate content (hash), skipping.")
            if url:
                scraped_urls.add(url)
            continue

        # Skip if URL already processed (if exists)
        if url and url in scraped_urls:
            print("  ⏩ Already processed (URL)")
            continue

        # Filename based on date + counter
        date_str = fb_post.get("date") or datetime.now().strftime("%Y-%m-%d")
        date_compact = date_str.replace("-", "")
        counter = get_next_counter(state, date_str)
        filename = f"{SCRIPT_NAME_HASH}-{date_compact}-{counter:03d}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(fb_post, f, indent=2, ensure_ascii=False)

            print(f"  ✅ Saved: {filename}")

            if url:
                scraped_urls.add(url)
            if content_hash:
                content_hashes.add(content_hash)

            new_posts.append({
                "filename": filename,
                "title": fb_post["title"],
                "url": url or "N/A",
                "post_id": post_id,
                "date": date_str,
            })

        except Exception as e:
            print(f"  ❌ Error saving file: {e}")

    # Update state
    state["scraped_urls"] = list(scraped_urls)
    state["content_hashes"] = list(content_hashes)
    save_state(state)

    print("\n" + "=" * 60)
    print("Import completed.")
    print(f"New traffic posts created: {len(new_posts)}")

    return new_posts


def main():
    print("=" * 60)
    print("🚗 BIHAMK Traffic RSS Import Feeder")
    print("=" * 60)
    print(f"Script:          {SCRIPT_NAME}")
    print(f"Script hash:     {SCRIPT_NAME_HASH}")
    print(f"Feed URL:        {FEED_URL}")
    print(f"Output directory:{os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)

    new_posts = import_bihamk_rss()

    if new_posts:
        print("\n📋 NEW TRAFFIC POSTS CREATED:")
        for post in new_posts:
            print(f"  📄 {post['filename']}")
            print(f"    {post['title'][:70]}...")
            print(f"    📅 {post['date']}")
            if post['url'] != "N/A":
                print(f"    🔗 {post['url']}")
            print()
    else:
        print("\nℹ️  No new traffic posts created.")

    print(f"✅ Check the '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)


if __name__ == "__main__":
    main()
