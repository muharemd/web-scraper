#!/usr/bin/env python3
"""
Generic RSS importer for Facebook auto-posting.

- Fetches RSS (optionally via curl + cookies)
- Parses items with feedparser
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

import feedparser

# ================== CONFIG ==================

# Example: Klix RSS
FEED_URL = "https://www.klix.ba/rss"

# If you need cookies (Cloudflare etc.), point this to your cookies.txt
COOKIES_FILE = os.path.expanduser(
    "~/snap/newsboat/current/.newsboat/cookies.txt"
)

OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "rss_import_state.json"

# Source identifiers (adjust as you like)
SOURCE_NAME = "Klix.ba"  # Human-readable
# SOURCE_ID will be SCRIPT_NAME_HASH (like in your KC script)

# Max content length for Facebook text
MAX_CONTENT_LEN = 800

# ============================================

SCRIPT_NAME = os.path.basename(sys.argv[0])
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(text):
    if not text:
        return ""
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
    Fetch RSS XML using curl + cookies (like your working terminal command).
    """
    cmd = ["curl", "-s", "-L", FEED_URL]
    if os.path.exists(COOKIES_FILE):
        cmd[1:1] = ["-b", COOKIES_FILE]

    try:
        xml = subprocess.check_output(cmd, timeout=20)
        return xml
    except Exception as e:
        print(f"[ERROR] fetching RSS via curl: {e}")
        return b""


def parse_rss_entries(xml_bytes):
    feed = feedparser.parse(xml_bytes)
    return feed.entries or []


def extract_image_from_entry(entry):
    # Try media:content
    media = getattr(entry, "media_content", None)
    if media and isinstance(media, list):
        for m in media:
            url = m.get("url")
            if url:
                return url

    # Try enclosures
    enclosures = getattr(entry, "enclosures", None)
    if enclosures and isinstance(enclosures, list):
        for e in enclosures:
            url = e.get("href") or e.get("url")
            if url:
                return url

    # Try common fields
    for key in ["image", "image_url", "thumbnail"]:
        if hasattr(entry, key):
            val = getattr(entry, key)
            if isinstance(val, str) and val:
                return val

    return None


def get_entry_date(entry):
    # Try structured published_parsed
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        return dt.strftime("%Y-%m-%d")

    # Try updated_parsed
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6])
        return dt.strftime("%Y-%m-%d")

    # Try raw published string
    for attr in ["published", "updated", "date"]:
        if hasattr(entry, attr):
            raw = getattr(entry, attr)
            if raw:
                # Look for YYYY-MM-DD or DD.MM.YYYY etc.
                patterns = [
                    r"\d{4}-\d{2}-\d{2}",
                    r"\d{2}\.\d{2}\.\d{4}",
                    r"\d{2}/\d{2}/\d{4}",
                ]
                for pattern in patterns:
                    m = re.search(pattern, raw)
                    if m:
                        found = m.group(0)
                        if "." in found:
                            d, mth, y = found.split(".")
                            return f"{y}-{mth}-{d}"
                        if "/" in found:
                            d, mth, y = found.split("/")
                            return f"{y}-{mth}-{d}"
                        return found

    # Fallback: today
    return datetime.now().strftime("%Y-%m-%d")


def format_for_facebook_from_entry(entry):
    # Title
    title = clean_text(getattr(entry, "title", "") or "No Title")

    # URL
    url = getattr(entry, "link", "") or ""

    # ID: short hash of URL
    post_id = hashlib.md5(url.encode()).hexdigest()[:8] if url else hashlib.md5(
        title.encode()
    ).hexdigest()[:8]

    # Content: use summary/description
    raw_content = ""
    for attr in ["summary", "description"]:
        if hasattr(entry, attr):
            raw_content = getattr(entry, attr) or ""
            if raw_content:
                break

    content = clean_text(raw_content)

    # Truncate for Facebook
    if len(content) > MAX_CONTENT_LEN:
        fb_content = content[:MAX_CONTENT_LEN] + "..."
    else:
        fb_content = content

    # Add footer like your RTV example
    if fb_content:
        fb_content += (
            f"\n\n📺 Izvor: {SOURCE_NAME}\n"
            f"🔗 Pročitaj više: {url}"
        )

    # Date
    date_str = get_entry_date(entry)

    # Image
    image_url = extract_image_from_entry(entry)

    # Content hash
    content_hash = generate_content_hash(content)

    fb_post = {
        "title": title,
        "id": post_id,
        "content": fb_content,
        "url": url,
        "scheduled_publish_time": None,
        "published": "",
        "source": SCRIPT_NAME_HASH,
        "source_name": SOURCE_NAME,
        "content_hash": content_hash,
        "scraped_at": datetime.now().isoformat(),
        "date": date_str,
    }

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


def import_rss():
    print(f"Script: {SCRIPT_NAME} (hash: {SCRIPT_NAME_HASH})")
    print(f"Time:   {datetime.now()}")
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

    print(f"Found {len(entries)} RSS entries.")
    new_posts = []

    processed = 0
    for entry in entries:
        processed += 1
        print(f"\n[{processed}/{len(entries)}] Processing entry...")

        fb_post, post_id, content_hash, url = format_for_facebook_from_entry(entry)

        if not url:
            print("  ❌ No URL, skipping.")
            continue

        print(f"  Title: {fb_post['title'][:60]}...")
        print(f"  URL:   {url}")
        print(f"  Hash:  {content_hash}")

        # Skip if URL already processed
        if url in scraped_urls:
            print("  ⏩ Already processed (URL)")
            continue

        # Skip if content hash already seen
        if content_hash and content_hash in content_hashes:
            print("  ⚠️ Duplicate content (hash), skipping.")
            scraped_urls.add(url)
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

            scraped_urls.add(url)
            if content_hash:
                content_hashes.add(content_hash)

            new_posts.append(
                {
                    "filename": filename,
                    "title": fb_post["title"],
                    "url": url,
                    "post_id": post_id,
                }
            )

        except Exception as e:
            print(f"  ❌ Error saving file: {e}")

    # Update state
    state["scraped_urls"] = list(scraped_urls)
    state["content_hashes"] = list(content_hashes)
    save_state(state)

    print("\n" + "=" * 60)
    print("Import completed.")
    print(f"New posts created: {len(new_posts)}")

    return new_posts


def main():
    print("=" * 60)
    print("🚀 RSS Import Feeder")
    print("=" * 60)
    print(f"Script:          {SCRIPT_NAME}")
    print(f"Script hash:     {SCRIPT_NAME_HASH}")
    print(f"Feed URL:        {FEED_URL}")
    print(f"Output directory:{os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)

    new_posts = import_rss()

    if new_posts:
        print("\n📋 NEW POSTS CREATED:")
        for post in new_posts:
            print(f"  📄 {post['filename']}")
            print(f"    {post['title'][:70]}...")
            print(f"    🔗 {post['url']}")
            print()
    else:
        print("\nℹ️  No new posts created.")

    print(f"✅ Check the '{OUTPUT_DIR}' directory for JSON files.")
    print("=" * 60)


if __name__ == "__main__":
    main()

