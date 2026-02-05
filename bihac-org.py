#!/usr/bin/env python3
import requests
import hashlib
import json
import os
import sys
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

class BihacOrgScraper:
    def __init__(self):
        self.base_url = "https://www.bihac.org"
        self.script_name = "bihac-org.py"
        self.script_hash = self.get_script_hash()[:12]
        self.output_dir = "/home/bihac-danas/web-scraper/facebook_ready_posts"
        self.state_file = "bihac_org_state.json"
        
        # URLs to scrape
        self.urls = {
            "gradska_uprava": "https://www.bihac.org/obavijesti",
            "javni_pozivi": "https://www.bihac.org/javni-pozivi"
        }
        
        # State tracking
        self.scraped_urls = set()
        self.content_hashes = set()
        self.new_posts = []
        
        # Create directories
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load existing state
        self.load_state()
        
        # Setup session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
    
    def get_script_hash(self):
        """Get script hash"""
        try:
            with open(__file__, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return hashlib.md5(b'bihac_org_scraper').hexdigest()
    
    def load_state(self):
        """Load state from JSON file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    
                    self.scraped_urls = set(state.get('scraped_urls', []))
                    self.content_hashes = set(state.get('content_hashes', []))
                    
                    print(f"📁 Loaded state: {len(self.scraped_urls)} URLs, {len(self.content_hashes)} hashes")
            except Exception as e:
                print(f"⚠️  Error loading state: {e}")
                self.scraped_urls = set()
                self.content_hashes = set()
        else:
            print("📁 No state file found, starting fresh")
    
    def save_state(self):
        """Save state to JSON file"""
        state = {
            "scraped_urls": list(self.scraped_urls),
            "content_hashes": list(self.content_hashes),
            "last_run": datetime.now().isoformat(),
            "script_name": self.script_name,
            "script_hash": self.script_hash
        }
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"\n💾 State saved to {self.state_file}")
        except Exception as e:
            print(f"❌ Error saving state: {e}")
    
    def print_header(self):
        """Print script header"""
        print("=" * 60)
        print("🏛️  BIHAC.ORG NEWS SCRAPER")
        print("=" * 60)
        print(f"Script: {self.script_name}")
        print(f"Script hash: {self.script_hash}")
        print(f"Target: {self.base_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"State file: {self.state_file}")
        print(f"Time: {datetime.now()}")
        print("=" * 60)
    
    def fetch_page(self, url):
        """Fetch webpage"""
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def find_article_links(self, html, category_url):
        """Find article links on page"""
        soup = BeautifulSoup(html, 'html.parser')
        article_urls = []
        
        # Look for article links - adjust selectors for bihac.org
        selectors = [
            'a[href*="/obavijesti/"]',
            'a[href*="/javni-pozivi/"]',
            'article a',
            '.news-item a',
            '.post a',
            '.item a',
            'h3 a, h4 a',
            '.title a',
            '.entry-title a',
            'a[href*="/20"]'  # Links with year
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(category_url, href)
                    if (self.base_url in full_url and 
                        full_url not in article_urls and
                        not any(ext in full_url.lower() for ext in ['.jpg', '.png', '.pdf', '.zip', '.doc'])):
                        article_urls.append(full_url)
        
        return list(set(article_urls))[:20]  # Increased limit
    
    def extract_image_url(self, soup, url):
        """Extract main image from article"""
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'article img',
            '.post-image img',
            '.featured-image img',
            '.content img:first-of-type',
            'img[src*="upload"]',
            'img[src*="image"]'
        ]
        
        for selector in image_selectors:
            if selector.startswith('meta'):
                meta = soup.select_one(selector)
                if meta:
                    src = meta.get('content')
                    if src:
                        return urljoin(url, src)
            else:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    src = img.get('src')
                    if src:
                        return urljoin(url, src)
        
        # Try to find logo as fallback
        logo = soup.select_one('img[src*="logo"], .logo img')
        if logo and logo.get('src'):
            return urljoin(url, logo.get('src'))
        
        # Default fallback
        return "https://www.bihac.org/images/logo.png"
    
    def parse_article(self, url, html, category):
        """Parse article and return data in required JSON format"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Title
        title = "Obavijest"
        title_selectors = [
            'h1',
            '.page-title',
            '.entry-title',
            '.post-title',
            '.title',
            'article h1',
            'meta[property="og:title"]'
        ]
        
        for selector in title_selectors:
            if selector.startswith('meta'):
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    title = meta.get('content', 'Obavijest')
                    break
            else:
                elem = soup.select_one(selector)
                if elem:
                    title_text = elem.get_text(strip=True)
                    if title_text and len(title_text) > 5:
                        title = title_text
                        break
        
        # 2. Generate ID (8 char hex)
        article_id = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 3. Date
        date_str = datetime.now().strftime('%Y-%m-%d')
        date_selectors = [
            'time',
            '.date',
            '.post-date',
            '.published',
            'meta[property="article:published_time"]',
            'meta[name="publish_date"]'
        ]
        
        for selector in date_selectors:
            if selector.startswith('meta'):
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta['content'])
                    if date_match:
                        date_str = date_match.group(1)
                        break
            else:
                elem = soup.select_one(selector)
                if elem:
                    date_text = elem.get_text(strip=True)
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})', date_text)
                    if date_match:
                        found = date_match.group(1)
                        if '.' in found:
                            day, month, year = found.split('.')
                            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        else:
                            date_str = found
                        break
        
        # 4. Content - IMPROVED SELECTORS
        content = ""
        content_selectors = [
            '.content',
            '.entry-content',
            '.post-content',
            '.article-content',
            'article',
            'main',
            '.post-body',
            '.text',
            '.inner-content',
            '.td-post-content'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                # Remove unwanted elements
                for tag in elem.select('script, style, nav, footer, header, aside, .comments, .share, iframe'):
                    tag.decompose()
                
                # Get text
                content = elem.get_text(strip=True, separator='\n')
                content = re.sub(r'\n\s*\n', '\n\n', content)
                
                if len(content) > 100:
                    break
        
        # If still no content, try to collect paragraphs with better filtering
        if len(content) < 100:
            paragraphs = soup.find_all(['p', 'div'])
            text_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Better filtering
                if (len(text) > 30 and 
                    not any(word in text.lower() for word in
                           ['menu', 'home', 'contact', 'copyright', 'privacy', 'terms', 'cookie',
                            'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
                            'search', 'login', 'register', 'subscribe'])):
                    text_parts.append(text)
            
            if text_parts:
                content = '\n'.join(text_parts[:15])  # Increased limit
        
        # Add category info and "Read more" link
        category_display = category.replace('_', ' ').title()
        
        if len(content) > 1500:
            content = content[:1500] + "..."
        
        if content:
            content += f"\n\n🏛️  Kategorija: {category_display}"
            content += f"\n\n📖 Pročitajte više: {url}"
        else:
            content = f"Obavijest {category_display}\n\n📖 Pročitajte više: {url}"
        
        # 5. Content hash (12 chars)
        content_for_hash = f"{title}{content[:1000]}".encode('utf-8')
        content_hash = hashlib.md5(content_for_hash).hexdigest()[:12]
        
        # 6. Image URL
        image_url = self.extract_image_url(soup, url)
        
        # Build JSON
        return {
            "title": title,
            "id": article_id,
            "content": content,
            "url": url,
            "scheduled_publish_time": None,
            "published": "",
            "source": self.script_hash,
        "source_name": "Grad Bihać",            "content_hash": content_hash,
            "scraped_at": datetime.now().isoformat(),
            "image_url": image_url,
            "date": date_str
        }
    
    def save_post(self, post_data):
        """Save post to facebook_ready_posts"""
        date_part = post_data['date'].replace('-', '')
        source_hash = post_data['source']
        
        # Find existing files
        existing = []
        for f in os.listdir(self.output_dir):
            if f.endswith('.json') and f.startswith(f"{source_hash}-{date_part}"):
                existing.append(f)
        
        # Get next sequence number
        if existing:
            seq_nums = []
            for f in existing:
                try:
                    num_part = f.split('-')[-1].split('.')[0]
                    seq_nums.append(int(num_part))
                except:
                    continue
            next_num = max(seq_nums) + 1 if seq_nums else 1
        else:
            next_num = 1
        
        # Create filename
        filename = f"{source_hash}-{date_part}-{next_num:03d}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def get_category_from_url(self, url):
        """Determine category from URL"""
        if "javni-pozivi" in url:
            return "javni_pozivi"
        elif "obavijesti" in url:
            return "gradska_uprava"
        else:
            # Check which category URL pattern matches
            for category_name, category_url in self.urls.items():
                if category_url in url:
                    return category_name
            return "gradska_uprava"  # default
    
    def run(self):
        """Main execution"""
        self.print_header()
        
        print(f"Scraping Bihać.org categories...")
        
        all_new_urls = []
        
        # Process each category
        for category_name, category_url in self.urls.items():
            print(f"\n📂 Category: {category_name.replace('_', ' ').title()}")
            print(f"   URL: {category_url}")
            
            # Fetch category page
            category_html = self.fetch_page(category_url)
            if not category_html:
                print(f"  ❌ Failed to fetch category page")
                continue
            
            # Find article links
            article_urls = self.find_article_links(category_html, category_url)
            print(f"  Found {len(article_urls)} articles")
            
            # Filter out already scraped URLs
            new_urls = []
            for url in article_urls:
                if url not in self.scraped_urls:
                    new_urls.append(url)
            
            print(f"  New articles: {len(new_urls)}")
            all_new_urls.extend(new_urls)
        
        # Remove duplicates
        all_new_urls = list(set(all_new_urls))
        
        if not all_new_urls:
            print("\n✅ No new articles found.")
            self.save_state()
            return
        
        print(f"\n📊 Total unique new articles to process: {len(all_new_urls)}")
        print(f"\nProcessing articles...\n")
        
        for i, url in enumerate(all_new_urls, 1):
            # Determine category from URL using improved function
            category = self.get_category_from_url(url)
            
            print(f"[{i}/{len(all_new_urls)}] Checking: {url}")
            print(f"  Category: {category.replace('_', ' ').title()}")
            
            # Fetch article
            article_html = self.fetch_page(url)
            if not article_html:
                print(f"  ❌ Failed to fetch")
                continue
            
            # Parse article
            post_data = self.parse_article(url, article_html, category)
            
            # Check for duplicate content
            if post_data['content_hash'] in self.content_hashes:
                print(f"  ⚠️  Duplicate content (hash: {post_data['content_hash']})")
                # Still add URL to scraped list
                self.scraped_urls.add(url)
                continue
            
            # Save to facebook_ready_posts
            filename = self.save_post(post_data)
            
            # Update state
            self.scraped_urls.add(url)
            self.content_hashes.add(post_data['content_hash'])
            self.new_posts.append((filename, post_data))
            
            print(f"  ✅ Saved: {filename}")
            print(f"    Title: {post_data['title'][:50]}...")
            print(f"    Date: {post_data['date']}")
            print(f"    Content length: {len(post_data['content'])} chars")
            print(f"    Content hash: {post_data['content_hash']}\n")
        
        # Print summary
        print("=" * 60)
        print("Scraping completed!")
        print(f"New posts saved: {len(self.new_posts)}")
        print(f"Total scraped URLs in state: {len(self.scraped_urls)}")
        print(f"Total content hashes in state: {len(self.content_hashes)}")
        
        if self.new_posts:
            print("\n📋 NEW POSTS CREATED:")
            for filename, post in self.new_posts:
                category = self.get_category_from_url(post['url'])
                print(f"\n  📄 {filename}")
                print(f"    {post['title'][:60]}...")
                print(f"    🔗 {post['url']}")
                print(f"    🏛️  Category: {category.replace('_', ' ').title()}")
                print(f"    📝 Content: {len(post['content'])} chars")
                if len(post['content']) < 100:
                    print(f"    ⚠️  Warning: Very short content!")
        
        print(f"\n✅ Check the 'facebook_ready_posts' directory for JSON files.")
        
        # Save state
        self.save_state()
        print("=" * 60)

def main():
    scraper = BihacOrgScraper()
    scraper.run()

if __name__ == "__main__":
    main()
