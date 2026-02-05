#!/usr/bin/env python3
"""
USN Krajina News Scraper
Updated with better content extraction
"""

import requests
import hashlib
import json
import os
import sys
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

class USNKrajinaScraper:
    def __init__(self):
        self.base_url = "https://usnkrajina.com.ba"
        self.script_name = "usnkrajina.py"
        self.script_hash = self.get_script_hash()[:12]
        self.output_dir = "/home/bihac-danas/web-scraper/facebook_ready_posts"
        self.state_file = "usnkrajina_state.json"
        
        # State tracking
        self.scraped_urls = set()
        self.content_hashes = set()
        self.new_posts = []
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load existing state
        self.load_state()
        
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
            return hashlib.md5(b'usnkrajina_scraper').hexdigest()
    
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
        print("📰 USN KRAJINA NEWS SCRAPER")
        print("=" * 60)
        print(f"Script: {self.script_name}")
        print(f"Script hash: {self.script_hash}")
        print(f"Target: {self.base_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"State file: {self.state_file}")
        print(f"Time: {datetime.now()}")
        print("=" * 60)
    
    def fetch_page(self, url):
        """Fetch webpage with better error handling"""
        try:
            print(f"  🌐 Fetching: {url}")
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            # Check if it's HTML
            if 'text/html' in resp.headers.get('Content-Type', ''):
                return resp.text
            else:
                print(f"  ⚠️  Not HTML content: {resp.headers.get('Content-Type')}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error fetching: {e}")
            return None
    
    def find_articles(self, html):
        """Find article links on page"""
        soup = BeautifulSoup(html, 'html.parser')
        article_urls = []
        
        print(f"  🔍 Looking for article links...")
        
        # Try multiple strategies to find articles
        strategies = [
            # Strategy 1: Look for WordPress post links
            lambda: [a['href'] for a in soup.find_all('a', href=True) 
                    if '/20' in a['href'] and self.base_url in a['href'] 
                    and len(a.get_text(strip=True)) > 10],
            
            # Strategy 2: Look for article tags
            lambda: [a['href'] for a in soup.select('article a[href]') 
                    if self.base_url in a['href']],
            
            # Strategy 3: Look for news/post items
            lambda: [a['href'] for a in soup.select('.post a[href], .news-item a[href], .blog-item a[href]') 
                    if self.base_url in a['href']],
            
            # Strategy 4: Look for headings with links
            lambda: [a['href'] for a in soup.select('h2 a[href], h3 a[href]') 
                    if self.base_url in a['href']],
            
            # Strategy 5: Look for any links that look like articles
            lambda: [a['href'] for a in soup.find_all('a', href=re.compile(r'/\d{4}/\d{2}/')) 
                    if self.base_url in a['href']],
        ]
        
        for strategy in strategies:
            try:
                found_urls = strategy()
                for href in found_urls:
                    full_url = urljoin(self.base_url, href)
                    if (full_url not in article_urls and
                        not any(ext in full_url.lower() for ext in ['.jpg', '.png', '.pdf', '.zip'])):
                        article_urls.append(full_url)
                
                if article_urls:
                    print(f"  ✅ Found {len(article_urls)} articles using strategy")
                    break
            except Exception as e:
                continue
        
        # Also check sitemap or recent posts if nothing found
        if not article_urls:
            print(f"  ⚠️  No articles found with selectors, checking for recent posts...")
            # Look for recent posts section
            recent_posts = soup.select('#recent-posts a, .recent-posts a, .widget_recent_entries a')
            for post in recent_posts:
                href = post.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in article_urls:
                        article_urls.append(full_url)
        
        return list(set(article_urls))[:15]
    
    def extract_content(self, soup):
        """Extract article content with multiple strategies"""
        content = ""
        
        # Strategy 1: Look for WordPress content divs
        wp_selectors = [
            '.entry-content',  # WordPress classic
            '.post-content',
            '.article-content',
            '.single-content',
            '.content-area',
            '.main-content',
            'article .content',
            '.post-entry',
            '.td-post-content'  # Newspaper theme
        ]
        
        for selector in wp_selectors:
            elem = soup.select_one(selector)
            if elem:
                print(f"    ✅ Found content with selector: {selector}")
                # Remove unwanted elements
                for tag in elem.select('script, style, nav, footer, .comments, .share, .wp-caption, .ads'):
                    tag.decompose()
                
                content = elem.get_text(strip=True, separator='\n')
                content = re.sub(r'\n\s*\n', '\n\n', content)
                
                if len(content) > 100:
                    return content
        
        # Strategy 2: Look for article tag
        if not content:
            article = soup.find('article')
            if article:
                print(f"    ✅ Found content in <article> tag")
                # Remove unwanted elements
                for tag in article.select('script, style, nav, footer, header, aside'):
                    tag.decompose()
                
                content = article.get_text(strip=True, separator='\n')
                content = re.sub(r'\n\s*\n', '\n\n', content)
        
        # Strategy 3: Look for main content area
        if not content or len(content) < 100:
            main = soup.select_one('main, #main, .main')
            if main:
                print(f"    ✅ Found content in main area")
                # Remove common sidebar/menu elements
                for tag in main.select('script, style, nav, .sidebar, .menu, .widget'):
                    tag.decompose()
                
                content = main.get_text(strip=True, separator='\n')
                content = re.sub(r'\n\s*\n', '\n\n', content)
        
        # Strategy 4: Get all paragraphs and filter
        if not content or len(content) < 100:
            print(f"    ⚠️  Using paragraph collection strategy")
            paragraphs = soup.find_all(['p', 'div'])
            text_parts = []
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                # Filter out short text and navigation/menu items
                if (len(text) > 50 and 
                    not any(word in text.lower() for word in 
                           ['menu', 'home', 'contact', 'copyright', 'privacy', 'terms', 'cookie',
                            'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
                            'search', 'login', 'register', 'subscribe'])):
                    text_parts.append(text)
            
            if text_parts:
                content = '\n\n'.join(text_parts[:15])  # Limit to 15 paragraphs
        
        return content
    
    def extract_image_url(self, soup, url):
        """Extract main image from article"""
        image_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            '.post-thumbnail img',
            '.featured-image img',
            '.entry-content img:first-of-type',
            '.wp-post-image',
            'article img:first-of-type',
            'img[class*="attachment-"]',
            'img.size-full'
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
        
        # Fallback to site logo
        logo = soup.select_one('img[src*="logo"], .logo img, .site-logo img')
        if logo and logo.get('src'):
            return urljoin(url, logo.get('src'))
        
        # Default fallback
        return "https://usnkrajina.com.ba/wp-content/uploads/2021/11/cropped-usn_logo-1.png"
    
    def parse_article(self, url, html):
        """Parse article and return data in required JSON format"""
        soup = BeautifulSoup(html, 'html.parser')
        
        print(f"    📝 Parsing article...")
        
        # 1. Title
        title = "Nema naslova"
        title_selectors = [
            'h1.entry-title',
            'h1.post-title',
            'h1.title',
            'article h1',
            'h1',
            '.page-title',
            'meta[property="og:title"]',
            'title'
        ]
        
        for selector in title_selectors:
            if selector.startswith('meta'):
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    title = meta.get('content')
                    print(f"    ✅ Title from meta: {title[:50]}...")
                    break
            else:
                elem = soup.select_one(selector)
                if elem:
                    title_text = elem.get_text(strip=True)
                    if title_text and len(title_text) > 5:
                        title = title_text
                        print(f"    ✅ Title from {selector}: {title[:50]}...")
                        break
        
        # 2. Generate ID (8 char hex)
        article_id = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 3. Date
        date_str = datetime.now().strftime('%Y-%m-%d')
        date_selectors = [
            'time.entry-date',
            '.post-date',
            '.entry-date',
            '.date',
            'meta[property="article:published_time"]',
            'meta[name="publish_date"]',
            'time[datetime]'
        ]
        
        for selector in date_selectors:
            if selector.startswith('meta'):
                meta = soup.select_one(selector)
                if meta and meta.get('content'):
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta['content'])
                    if date_match:
                        date_str = date_match.group(1)
                        print(f"    ✅ Date from meta: {date_str}")
                        break
            elif selector == 'time[datetime]':
                time_elem = soup.select_one('time[datetime]')
                if time_elem and time_elem.get('datetime'):
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', time_elem['datetime'])
                    if date_match:
                        date_str = date_match.group(1)
                        print(f"    ✅ Date from time tag: {date_str}")
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
                        print(f"    ✅ Date from {selector}: {date_str}")
                        break
        
        # 4. Content
        content = self.extract_content(soup)
        
        if not content or len(content.strip()) < 50:
            print(f"    ⚠️  Warning: Very little content extracted ({len(content)} chars)")
            # Try one more strategy - get body text excluding common elements
            body = soup.find('body')
            if body:
                for tag in body.select('script, style, nav, header, footer, .sidebar, .menu, .widget'):
                    tag.decompose()
                content = body.get_text(strip=True, separator='\n')
                content = re.sub(r'\n\s*\n', '\n\n', content)
                print(f"    ℹ️  Using body text: {len(content)} chars")
        
        # Add "Read more" link
        if content:
            if len(content) > 1500:
                content = content[:1500] + "..."
            content += f"\n\n📖 Pročitajte više: {url}"
        else:
            content = f"Nema dostupnog sadržaja za ovu vijest.\n\n📖 Pročitajte više: {url}"
            print(f"    ⚠️  No content found for this article")
        
        # 5. Content hash (12 chars)
        content_for_hash = f"{title}{content[:1000]}".encode('utf-8')
        content_hash = hashlib.md5(content_for_hash).hexdigest()[:12]
        
        # 6. Image URL
        image_url = self.extract_image_url(soup, url)
        print(f"    🖼️  Image: {image_url[:50]}...")
        
        # Build JSON
        return {
            "title": title,
            "id": article_id,
            "content": content,
            "url": url,
            "scheduled_publish_time": None,
            "published": "",
            "source": self.script_hash,
        "source_name": "USN Krajina",            "content_hash": content_hash,
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
    
    def run(self):
        """Main execution"""
        self.print_header()
        
        print(f"Scraping USN Krajina: {self.base_url}")
        print("Looking for news articles...")
        
        # Start with main page
        main_html = self.fetch_page(self.base_url)
        if not main_html:
            print("❌ Failed to fetch main page")
            self.save_state()
            return
        
        # Find article URLs
        article_urls = self.find_articles(main_html)
        
        # Also check common news sections
        news_sections = ['/novosti/', '/vijesti/', '/aktuelnosti/', '/category/novosti/', '/blog/']
        for section in news_sections:
            section_url = urljoin(self.base_url, section)
            print(f"\n📂 Checking section: {section_url}")
            section_html = self.fetch_page(section_url)
            if section_html:
                section_urls = self.find_articles(section_html)
                article_urls.extend(section_urls)
        
        # Remove duplicates and already scraped URLs
        unique_new_urls = []
        for url in set(article_urls):
            if url not in self.scraped_urls:
                unique_new_urls.append(url)
        
        print(f"\n📊 Found {len(set(article_urls))} total articles")
        print(f"📊 New articles to process: {len(unique_new_urls)}")
        
        if not unique_new_urls:
            print("✅ No new articles found.")
            self.save_state()
            return
        
        print(f"\nProcessing {len(unique_new_urls)} new articles...\n")
        
        for i, url in enumerate(unique_new_urls, 1):
            print(f"\n[{i}/{len(unique_new_urls)}] Processing: {url}")
            
            # Fetch article
            article_html = self.fetch_page(url)
            if not article_html:
                print(f"  ❌ Failed to fetch article")
                continue
            
            # Parse article
            post_data = self.parse_article(url, article_html)
            
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
            print(f"    Title: {post_data['title'][:60]}...")
            print(f"    Date: {post_data['date']}")
            print(f"    Content length: {len(post_data['content'])} chars")
            print(f"    Content hash: {post_data['content_hash']}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("Scraping completed!")
        print(f"New posts saved: {len(self.new_posts)}")
        print(f"Total scraped URLs in state: {len(self.scraped_urls)}")
        print(f"Total content hashes in state: {len(self.content_hashes)}")
        
        if self.new_posts:
            print("\n📋 NEW POSTS CREATED:")
            for filename, post in self.new_posts:
                print(f"\n  📄 {filename}")
                print(f"    {post['title'][:70]}...")
                print(f"    🔗 {post['url']}")
                print(f"    📝 Content: {len(post['content'])} chars")
                if len(post['content']) < 100:
                    print(f"    ⚠️  Warning: Very short content!")
        
        print(f"\n✅ Check the 'facebook_ready_posts' directory for JSON files.")
        
        # Save state
        self.save_state()
        print("=" * 60)

def main():
    scraper = USNKrajinaScraper()
    scraper.run()

if __name__ == "__main__":
    main()
