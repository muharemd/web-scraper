#!/usr/bin/env python3
"""
FENA RSS Feed Scraper for Facebook Auto-Posting
Scrapes: https://fena.ba/rss
Filters for Bihać/USK region news
"""

import feedparser
import json
import hashlib
from datetime import datetime
import os
import sys
import re

# Configuration
FEED_URL = "https://fena.ba/rss"
OUTPUT_DIR = "facebook_ready_posts"
STATE_FILE = "fena_rss_state.json"
SOURCE_NAME = "FENA"

SCRIPT_NAME = os.path.basename(sys.argv[0])
SCRIPT_NAME_HASH = hashlib.md5(SCRIPT_NAME.encode()).hexdigest()[:12]

# Keywords for filtering - USK, Bihać, Una-Sana region
BIHAC_KEYWORDS = {
    # Cities and municipalities
    'bihać', 'bihac', 'biha', 'bihacu', 'bihaću',
    'cazin', 'cazinu',
    'bužim', 'buzim', 'bužimu', 'buzimu',
    'velika kladuša', 'v. kladuša', 'kladuša', 'velikakladuša',
    'sanski most', 'sanskimost', 'sanski',
    'bosanska krupa', 'b.krupa', 'krupa', 'bosanskakrupa',
    'ključ', 'kljuc',
    
    # Canton names
    'unsko-sanski', 'unskosanski', 'usk',
    'una-sana', 'unosanski', 'unskog', 'unskom',
    'kanton 1',
    
    # Regional terms
    'krajina', 'bihaćka', 'bihacka', 'cazinska',
    'cazinska krajina', 'bihaćko', 'bihacko',
    
    # Institutions in the region
    'univerzitet u bihaću', 'unbi',
    'općina bihać', 'opcina bihac',
    'grad bihać', 'grad bihac',
    'vlada usk', 'vladausk',
    'skupština usk', 'skupstina usk',
    'zzousk', 'zavod zdravstvenog',
    'ceste usk', 'cesteusk',
    'vodovod bihać', 'vodovod bihac',
    'rtv usk', 'rtvusk',
    'radio bihać', 'radio bihac',
    'usnkrajina', 'uskrajina',
    
    # Events and locations
    'rijeka una', 'nacionalni park una', 'np una',
    'ostrožac', 'ostrozac',
    
    # Common words in context
    'bihaćani', 'bihacani',
    'krajišnici', 'krajsnici',
    'iz bihaća', 'iz bihaca',
    'u bihaću', 'u bihacu'
}

# Exclude keywords (articles to skip)
EXCLUDE_KEYWORDS = {
    'beograd', 'sarajevo', 'zagreb', 'beč', 'bec', 'berlin',
    'njemačka', 'njemacka', 'amerika', 'sjedinjene',
    'rusija', 'ukrajina', 'kina', 'japan',
}

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_content_hash(content):
    if not content:
        return ""
    clean_content = ' '.join(content.split()).lower()
    return hashlib.md5(clean_content.encode()).hexdigest()[:12]

def load_scraped_data():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('content_hashes', []))
    return set()

def save_scraped_data(content_hashes):
    state = {
        'content_hashes': list(content_hashes),
        'last_run': datetime.now().isoformat(),
        'script_name': SCRIPT_NAME
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def clean_html(html_text):
    """Remove HTML tags and clean text"""
    if not html_text:
        return ""
    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', html_text)
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def normalize_text(text):
    """Normalize text for keyword matching"""
    if not text:
        return ""
    # Convert to lowercase
    text = text.lower()
    # Remove diacritics
    text = text.replace('ć', 'c').replace('č', 'c').replace('đ', 'dj')
    text = text.replace('š', 's').replace('ž', 'z')
    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_relevant(title, summary="", categories=None):
    """Check if article is relevant to Bihac/USK region"""
    
    # Normalize text for matching
    full_text = f"{title} {summary}"
    if categories:
        full_text += " " + " ".join(categories)
    
    normalized_text = normalize_text(full_text)
    
    # Check exclude keywords first
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in normalized_text:
            return False
    
    # Check for Bihac/USK keywords
    for keyword in BIHAC_KEYWORDS:
        if keyword.lower() in normalized_text:
            return True
    
    # Check for specific patterns
    patterns = [
        r'kanton[^\w]?(?:[^\w]?\d+)?[^\w]?1',  # Kanton 1
        r'una[-\s]sana',
        r'unsko[-\s]sanski',
        r'usk[\s\.]',  # USK as separate word
        r'bihac[aiu]',
        r'cazin[au]',
        r'buzim[au]',
        r'kladu[sz]a',
        r'sanski[\s-]most',
        r'bosanska[\s-]krupa',
        r'krajina',
    ]
    
    for pattern in patterns:
        if re.search(pattern, normalized_text, re.IGNORECASE):
            return True
    
    return False

def parse_date(date_str):
    """Parse RSS date to YYYY-MM-DD format"""
    if not date_str:
        return datetime.now().strftime('%Y-%m-%d')
    
    try:
        # Try to parse RSS date format
        from email.utils import parsedate_to_datetime
        pub_date = parsedate_to_datetime(date_str)
        return pub_date.strftime('%Y-%m-%d')
    except:
        # Try alternative formats
        try:
            # Try ISO format
            pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return pub_date.strftime('%Y-%m-%d')
        except:
            # Return today as fallback
            return datetime.now().strftime('%Y-%m-%d')

def extract_image(entry):
    """Extract image URL from entry"""
    # Check media content
    if hasattr(entry, 'media_content'):
        for media in entry.media_content:
            if media.get('url'):
                return media['url']
    
    # Check enclosures
    if hasattr(entry, 'enclosures'):
        for enclosure in entry.enclosures:
            if enclosure.get('type', '').startswith('image'):
                return enclosure.get('href', '')
    
    # Check links
    if hasattr(entry, 'links'):
        for link in entry.links:
            if link.get('type', '').startswith('image'):
                return link.get('href', '')
    
    # Check content for img tags
    if hasattr(entry, 'content'):
        for content in entry.content:
            if content.get('value'):
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content['value'])
                if img_match:
                    return img_match.group(1)
    
    # Check summary for img tags
    if hasattr(entry, 'summary'):
        img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
        if img_match:
            return img_match.group(1)
    
    return None

def detect_region(text):
    """Detect specific region/city from text"""
    text_lower = text.lower()
    
    if 'bihać' in text_lower or 'bihac' in text_lower:
        return 'Bihać'
    elif 'cazin' in text_lower:
        return 'Cazin'
    elif 'bužim' in text_lower or 'buzim' in text_lower:
        return 'Bužim'
    elif 'kladuša' in text_lower:
        return 'Velika Kladuša'
    elif 'sanski most' in text_lower:
        return 'Sanski Most'
    elif 'bosanska krupa' in text_lower:
        return 'Bosanska Krupa'
    elif 'ključ' in text_lower:
        return 'Ključ'
    else:
        return 'Unsko-sanski kanton'

def format_for_facebook(entry, article_number):
    """Format article data for Facebook posting"""
    try:
        title = entry.get('title', '')
        url = entry.get('link', '')
        
        # Get summary
        summary = ''
        if hasattr(entry, 'summary'):
            summary = clean_html(entry.summary)
        elif hasattr(entry, 'description'):
            summary = clean_html(entry.description)
        
        # Get full content if available
        content = summary
        if hasattr(entry, 'content'):
            for c in entry.content:
                if c.get('value'):
                    content = clean_html(c.value)
                    break
        
        # Get categories
        categories = []
        if hasattr(entry, 'tags'):
            categories = [tag.get('term', '') for tag in entry.tags if tag.get('term')]
        elif hasattr(entry, 'category'):
            categories = [entry.category] if entry.category else []
        
        # Get image
        image_url = extract_image(entry)
        
        # Get publication date
        published = ''
        if hasattr(entry, 'published'):
            published = entry.published
        elif hasattr(entry, 'updated'):
            published = entry.updated
        elif hasattr(entry, 'created'):
            published = entry.created
        
        date = parse_date(published)
        
        # Determine region/city for better context
        region = detect_region(f"{title} {summary}")
        
        # Build content with source attribution
        full_content = f"{title}\n\n"
        full_content += f"{content}\n\n"
        if region:
            full_content += f"📍 {region}\n"
        full_content += f"📌 Izvor: {SOURCE_NAME}"
        
        # Generate ID from URL
        article_id = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Generate content hash for deduplication
        content_hash = generate_content_hash(full_content)
        
        return {
            'title': title,
            'id': article_id,
            'content': full_content,
            'url': url,
            'image_url': image_url,
            'date': date,
            'published': "",
            'source': SCRIPT_NAME_HASH,
            'source_name': SOURCE_NAME,
            'content_hash': content_hash,
            'scheduled_publish_time': None,
            'scraped_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"  Error formatting article: {e}")
        return None

def save_article(article_data, article_number):
    """Save article to JSON file"""
    try:
        # Format date for filename: YYYYMMDD
        date_str = article_data['date'].replace('-', '')
        
        # Generate filename: script_hash-date-number.json
        filename = f"{SCRIPT_NAME_HASH}-{date_str}-{article_number:03d}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(article_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ Saved: {filename}")
        return True
    except Exception as e:
        print(f"  ✗ Error saving article: {e}")
        return False

def main():
    print("=" * 60)
    print(f"FENA RSS Scraper - {SOURCE_NAME}")
    print("=" * 60)
    
    ensure_dirs()
    
    # Load previously scraped content hashes
    scraped_hashes = load_scraped_data()
    print(f"Loaded {len(scraped_hashes)} previously scraped articles")
    
    new_articles = 0
    article_counter = 1
    
    try:
        print(f"\nFetching FENA RSS feed: {FEED_URL}")
        feed = feedparser.parse(FEED_URL)
        
        if feed.bozo:  # Check for parsing errors
            print(f"⚠️  Feed parsing warning: {feed.bozo_exception}")
        
        print(f"Total entries in feed: {len(feed.entries)}\n")
        
        # Process all entries
        for entry in feed.entries:
            try:
                # Get title and summary
                title = entry.get('title', '')
                summary = ''
                if hasattr(entry, 'summary'):
                    summary = clean_html(entry.summary)
                elif hasattr(entry, 'description'):
                    summary = clean_html(entry.description)
                
                # Get categories
                categories = []
                if hasattr(entry, 'tags'):
                    categories = [tag.get('term', '') for tag in entry.tags if tag.get('term')]
                elif hasattr(entry, 'category'):
                    categories = [entry.category] if entry.category else []
                
                # Check if article is relevant
                if not is_relevant(title, summary, categories):
                    continue
                
                print(f"Found relevant: {title[:60]}...")
                
                # Format article data
                article_data = format_for_facebook(entry, article_counter)
                if not article_data:
                    continue
                
                # Get content hash for deduplication
                content_hash = article_data['content_hash']
                
                # Skip if already scraped
                if content_hash in scraped_hashes:
                    print(f"  ⊘ Skipped (already scraped)")
                    continue
                
                # Save article
                if save_article(article_data, article_counter):
                    scraped_hashes.add(content_hash)
                    new_articles += 1
                    article_counter += 1
                
            except Exception as e:
                print(f"  ✗ Error processing entry: {e}")
                continue
        
    except Exception as e:
        print(f"\n✗ Error scraping FENA feed: {e}")
    
    # Save updated state
    save_scraped_data(scraped_hashes)
    
    print("\n" + "=" * 60)
    print(f"✅ Scraping completed")
    print(f"   New articles: {new_articles}")
    print(f"   Total tracked: {len(scraped_hashes)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
