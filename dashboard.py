## The /run-rewrite-titles route should be at the end of the file, after all other routes and functions are defined.
import os
import sys
import json
import subprocess
import traceback
import hashlib
import secrets
import bcrypt
import requests
import re
import warnings
from datetime import datetime
from functools import wraps
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, jsonify, redirect, url_for, request, session
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

print(f"DEBUG: Starting dashboard.py with Python: {sys.executable}")


app = Flask(__name__)
# Set a fixed, secure secret key (generated once, keep private)
app.secret_key = 'b1e2c3d4e5f6a7b8againc9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2'
# Set session cookie options for compatibility
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_DOMAIN'] = None

# ===== CONFIGURATION =====
JSON_DIR = "/home/bihac-danas/web-scraper/facebook_ready_posts"
WEBHOOK_URL = "https://hook.eu1.make.com/p1kanqk3w243rnyaio8gbeeiosvhddgb"
WEBHOOK_URL_KONKURSI = os.getenv("WEBHOOK_URL_KONKURSI", "https://hook.eu1.make.com/m910901wp49ecauhcdf2fkn18t49jubt")
USERS_FILE = "/home/bihac-danas/web-scraper/dashboard_users.json"
CUSTOM_SCRAPE_STATE_FILE = "/home/bihac-danas/web-scraper/custom_dashboard_scrape_state.json"

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ===== SECURITY LOGGING =====
ACCESS_LOG = "/home/bihac-danas/web-scraper/dashboard_access.log"
ACTIVITY_LOG = "/home/bihac-danas/web-scraper/dashboard_activity.log"
FAILED_LOGIN_LOG = "/home/bihac-danas/web-scraper/failed_logins.log"

def log_access(ip, username, action, details="", status="SUCCESS"):
    """Log user access attempts"""
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} | {ip} | {username} | {action} | {details} | {status}\n"
    
    try:
        with open(ACCESS_LOG, 'a') as f:
            f.write(log_entry)
    except:
        pass

def log_activity(ip, username, action, details=""):
    """Log user activities"""
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} | {ip} | {username} | {action} | {details}\n"
    
    try:
        with open(ACTIVITY_LOG, 'a') as f:
            f.write(log_entry)
    except:
        pass

def log_failed_login(ip, username, reason):
    """Log failed login attempts"""
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} | {ip} | {username} | {reason}\n"
    
    try:
        with open(FAILED_LOGIN_LOG, 'a') as f:
            f.write(log_entry)
    except:
        pass

def get_client_ip():
    """Get client IP address - SIMPLIFIED VERSION"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    else:
        ip = request.remote_addr
    
    # Simple IP validation
    if ip and len(ip) < 50:  # Basic sanity check
        return ip
    return "0.0.0.0"

# ===== DEEPSEEK API INTEGRATION =====
def load_deepseek_api_key():
    """Load DeepSeek API key from config file"""
    config_file = "/home/bihac-danas/web-scraper/.deepseek_config"
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Handle both "export DEEPSEEK_API_KEY=" and "DEEPSEEK_API_KEY=" formats
                if 'DEEPSEEK_API_KEY=' in line:
                    # Extract the value after the = sign
                    value = line.split('DEEPSEEK_API_KEY=', 1)[1].strip()
                    # Remove quotes if present
                    return value.strip('"').strip("'")
    except Exception as e:
        print(f"ERROR loading API key: {e}")
    return None

def rewrite_single_title(filename):
    """Rewrite title for a single article using DeepSeek API"""
    filepath = os.path.join(JSON_DIR, filename)
    
    try:
        # Load article
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if already rewritten
        if 'title_rewritten' in data and data['title_rewritten']:
            return {'success': False, 'error': 'Title already rewritten'}
        
        # Get API key
        api_key = load_deepseek_api_key()
        if not api_key:
            return {'success': False, 'error': 'API key not found'}
        
        # Extract title and content
        title = data.get('title', '')
        content = data.get('content', '')
        
        # Call DeepSeek API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {
                    'role': 'system',
                    'content': 'Rewrite news titles to be short, catchy, and accurate and please offer only one possibility. All in Bosnian or Croatian language.'
                },
                {
                    'role': 'user',
                    'content': f'Rewrite this title using the article content:\nTitle: {title}\nContent: {content}'
                }
            ]
        }
        
        response = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            return {'success': False, 'error': f'API error: {response.status_code}'}
        
        result = response.json()
        rewritten_title = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if not rewritten_title:
            return {'success': False, 'error': 'No rewritten title received from API'}
        
        # Update JSON file
        data['title_rewritten'] = rewritten_title.strip()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {
            'success': True,
            'original': title,
            'rewritten': rewritten_title.strip()
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ===== USER MANAGEMENT =====
def load_users():
    """Load users from JSON file"""
    if not os.path.exists(USERS_FILE):
        # Create default admin user
        default_users = {
            "admin": {
                "password_hash": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
                "role": "admin",
                "created_at": datetime.now().isoformat()
            }
        }
        save_users(default_users)
        return default_users
    
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def verify_password(username, password):
    """Verify user credentials"""
    users = load_users()
    if username not in users:
        bcrypt.hashpw(b"dummy", bcrypt.gensalt())
        return False, None
    
    stored_hash = users[username]["password_hash"]
    if bcrypt.checkpw(password.encode(), stored_hash.encode()):
        return True, users[username]["role"]
    return False, None

# Initialize users file
users = load_users()
print(f"Loaded {len(users)} users")

def login_required(f):
    """Decorator to require authentication with logging"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = get_client_ip()
        
        if not session.get('logged_in'):
            log_access(client_ip, "ANONYMOUS", "ACCESS_DENIED", 
                      f"Tried to access {request.path}", "DENIED")
            return redirect(url_for('login', next=request.url))
        
        username = session.get('username', 'UNKNOWN')
        log_access(client_ip, username, "ACCESS_GRANTED", 
                  f"Accessed {request.path}", "SUCCESS")
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with logging"""
    client_ip = get_client_ip()
    
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        log_access(client_ip, username, "LOGIN_ATTEMPT")
        
        if not username or not password:
            log_failed_login(client_ip, username, "MISSING_CREDENTIALS")
            return render_template('login.html', error="Please enter both username and password", now=datetime.now())
        
        is_valid, role = verify_password(username, password)
        
        if is_valid:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = role
            
            log_access(client_ip, username, "LOGIN_SUCCESS", f"Role: {role}", "SUCCESS")
            log_activity(client_ip, username, "USER_LOGIN")
            
            next_page = request.args.get('next', url_for('index'))
            return redirect(next_page)
        else:
            log_failed_login(client_ip, username, "INVALID_CREDENTIALS")
            log_access(client_ip, username, "LOGIN_FAILED", "", "FAILED")
            
            return render_template('login.html', error="Invalid username or password", now=datetime.now())
    
    log_access(client_ip, "ANONYMOUS", "LOGIN_PAGE_VIEW")
    return render_template('login.html', error=None, now=datetime.now())

@app.route('/logout')
def logout():
    """Logout user with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    log_access(client_ip, username, "LOGOUT", "", "SUCCESS")
    log_activity(client_ip, username, "USER_LOGOUT")
    
    session.clear()
    return redirect(url_for('login'))

# ===== DASHBOARD FUNCTIONALITY =====
def get_articles():
    """Get all articles from JSON files"""
    articles = []
    
    if not os.path.exists(JSON_DIR):
        print(f"ERROR: JSON directory not found: {JSON_DIR}")
        return articles
    
    try:
        files = [f for f in os.listdir(JSON_DIR) if f.endswith('.json')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(JSON_DIR, x)), reverse=True)
        
        for filename in files[:50]:
            filepath = os.path.join(JSON_DIR, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Get source name from JSON or infer from filename
                source_name = data.get('source_name', 'Unknown')
                if source_name == 'Unknown':
                    if 'dz' in filename.lower():
                        source_name = 'Dom zdravlja'
                    elif 'vod' in filename.lower():
                        source_name = 'Vodovod'
                    elif 'bihac' in filename.lower():
                        source_name = 'Grad Bihać'
                    elif 'usk' in filename.lower():
                        source_name = 'USK'
                    elif 'krajina' in filename.lower():
                        source_name = 'USN Krajina'
                    elif 'komrad' in filename.lower():
                        source_name = 'Komrad'
                    elif 'radio' in filename.lower():
                        source_name = 'Radio Bihać'
                    elif 'rtv' in filename.lower():
                        source_name = 'RTV USK'
                    elif 'vlada' in filename.lower():
                        source_name = 'Vlada USK'
                    elif 'kb' in filename.lower():
                        source_name = 'Kantonalna bolnica'
                    elif 'kc' in filename.lower():
                        source_name = 'Kantonalni centar'
                
                content = data.get('content', '')
                # Show full content on dashboard
                content_preview = content
                
                articles.append({
                    'filename': filename,
                    'title': data.get('title', 'Nema naslova'),
                    'title_rewritten': data.get('title_rewritten', ''),
                    'content': content,
                    'content_preview': content_preview,
                    'date': data.get('date', 'Unknown'),
                    'published': data.get('published', ''),
                    'published_target': data.get('published_target', ''),
                    'source_name': source_name,
                    'url': data.get('url', '#'),
                    'is_new': not bool(data.get('published')),
                    'image_url': data.get('image_url', '')
                })
                
            except Exception as e:
                print(f"ERROR reading {filename}: {e}")
                continue
                
    except Exception as e:
        print(f"ERROR in get_articles: {e}")
        traceback.print_exc()
    
    return articles

def run_curl_command(json_file_path):
    """Run curl command to post to Facebook"""
    return run_curl_command_for_target(json_file_path, "bihac_danas")


def get_webhook_for_target(target):
    if target == "bihac_danas":
        return WEBHOOK_URL
    if target == "konkursi":
        return WEBHOOK_URL_KONKURSI
    return None


def run_curl_command_for_target(json_file_path, target="bihac_danas"):
    """Run curl command to post to selected Facebook page target"""
    try:
        webhook_url = get_webhook_for_target(target)
        if not webhook_url:
            return {'success': False, 'error': f'Unknown target: {target}'}

        cmd = [
            'curl', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-d', f'@{json_file_path}',
            webhook_url,
            '--max-time', '30'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").replace("\n", " ")).strip()


def _content_hash(text):
    normalized = " ".join(text.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _normalize_text(text):
    value = _clean_text(text).lower()
    return (
        value.replace("ć", "c")
        .replace("č", "c")
        .replace("š", "s")
        .replace("ž", "z")
        .replace("đ", "dj")
    )


def _load_custom_state():
    if os.path.exists(CUSTOM_SCRAPE_STATE_FILE):
        try:
            with open(CUSTOM_SCRAPE_STATE_FILE, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}
    return {}


def _save_custom_state(state):
    with open(CUSTOM_SCRAPE_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)


def _next_output_filename(source_hash):
    date_part = datetime.now().strftime("%Y%m%d")
    existing = [
        name
        for name in os.listdir(JSON_DIR)
        if name.startswith(f"{source_hash}-{date_part}-") and name.endswith(".json")
    ]
    next_num = len(existing) + 1
    return f"{source_hash}-{date_part}-{next_num:03d}.json"


def _extract_article_links(listing_url, html):
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(listing_url).netloc.lower().replace("www.", "")
    links = []
    selectors = [
        "article a[href]",
        "h1 a[href], h2 a[href], h3 a[href]",
        ".post a[href], .news a[href], .entry a[href], .item a[href], tr a[href]",
        "a[href]",
    ]

    for selector in selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            full_url = urljoin(listing_url, href)
            listing_normalized = f"{urlparse(listing_url).scheme}://{urlparse(listing_url).netloc}{urlparse(listing_url).path}".rstrip("/")
            full_normalized = f"{urlparse(full_url).scheme}://{urlparse(full_url).netloc}{urlparse(full_url).path}".rstrip("/")
            if full_normalized == listing_normalized:
                continue
            full_domain = urlparse(full_url).netloc.lower().replace("www.", "")
            if full_domain and base_domain and full_domain != base_domain:
                continue
            lowered = full_url.lower()
            if any(x in lowered for x in ["/feed", "/rss", ".xml", "wp-admin", "logout", "login"]):
                continue
            if any(lowered.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".doc", ".docx"]):
                continue
            if full_url not in links:
                links.append(full_url)
            if len(links) >= 20:
                return links
    return links


def _is_low_quality_article(article):
    title = _normalize_text(article.get("title", ""))
    content = _clean_text(article.get("content", ""))

    blocked_titles = {
        "home",
        "naslovna",
        "pocetna",
        "početna",
    }
    if title in blocked_titles:
        return True
    if len(title) < 6:
        return True
    if len(content) < 120:
        return True
    return False


def _extract_title_content(url, html):
    soup = BeautifulSoup(html, "html.parser")

    title = "Bez naslova"
    for selector in ["h1", "meta[property='og:title']", "title"]:
        if selector.startswith("meta"):
            elem = soup.select_one(selector)
            if elem and elem.get("content"):
                candidate = _clean_text(elem.get("content"))
                if len(candidate) > 4:
                    title = candidate
                    break
        else:
            elem = soup.select_one(selector)
            if elem:
                candidate = _clean_text(elem.get_text(" "))
                if len(candidate) > 4:
                    title = candidate
                    break

    content = ""
    for selector in ["article", ".entry-content", ".post-content", ".article-content", "main", "#content", ".content"]:
        elem = soup.select_one(selector)
        if elem:
            for trash in elem.select("script, style, iframe, nav, footer, header, aside"):
                trash.decompose()
            candidate = _clean_text(elem.get_text(" "))
            if len(candidate) >= 120:
                content = candidate
                break

    if not content:
        paragraphs = [_clean_text(p.get_text(" ")) for p in soup.select("p")[:25]]
        paragraphs = [p for p in paragraphs if len(p) > 35]
        content = _clean_text(" ".join(paragraphs))

    image_url = ""
    for selector in ["meta[property='og:image']", "meta[name='twitter:image']", "article img[src]", "main img[src]", "img[src]"]:
        if selector.startswith("meta"):
            meta = soup.select_one(selector)
            if meta and meta.get("content"):
                image_url = urljoin(url, meta.get("content"))
                break
        else:
            img = soup.select_one(selector)
            if img and img.get("src"):
                image_url = urljoin(url, img.get("src"))
                break

    return {
        "title": title,
        "content": content if content else title,
        "url": url,
        "image_url": image_url,
    }


def _matches_filter(article, filter_terms):
    if not filter_terms:
        return True
    haystack = _normalize_text(f"{article.get('title','')} {article.get('content','')} {article.get('url','')}")
    return any(term in haystack for term in filter_terms)


@app.route('/api/custom-scrape', methods=['POST'])
@login_required
def custom_scrape():
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')

    payload = request.get_json(silent=True) or {}
    target_url = _clean_text(payload.get('url', ''))
    filter_text = _clean_text(payload.get('filter', ''))

    if not target_url:
        return jsonify({'status': 'error', 'message': 'URL is required'}), 400
    if not target_url.startswith(('http://', 'https://')):
        return jsonify({'status': 'error', 'message': 'URL must start with http:// or https://'}), 400

    filter_terms = [_normalize_text(term) for term in re.split(r'[,\n]+', filter_text) if _clean_text(term)]
    source_domain = urlparse(target_url).netloc.replace('www.', '')
    source_name = f"Custom {source_domain}" if source_domain else "Custom Source"
    source_hash = hashlib.md5(f"custom:{target_url}:{'|'.join(filter_terms)}".encode()).hexdigest()[:12]
    state_key = hashlib.md5(f"{target_url}|{'|'.join(filter_terms)}".encode()).hexdigest()

    state = _load_custom_state()
    entry = state.get(state_key, {"scraped_urls": [], "content_hashes": []})
    scraped_urls = set(entry.get("scraped_urls", []))
    content_hashes = set(entry.get("content_hashes", []))

    log_activity(client_ip, username, "CUSTOM_SCRAPE_ATTEMPT", f"URL: {target_url} | Filter: {filter_text}")

    session_http = requests.Session()
    session_http.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        listing_resp = session_http.get(target_url, timeout=25)
        listing_resp.raise_for_status()
        links = _extract_article_links(target_url, listing_resp.text)
        if not links:
            links = [target_url]

        created_files = []
        for link in links[:20]:
            if link in scraped_urls:
                continue

            try:
                article_resp = session_http.get(link, timeout=25)
                article_resp.raise_for_status()
            except Exception:
                continue

            article = _extract_title_content(link, article_resp.text)
            if _is_low_quality_article(article):
                scraped_urls.add(link)
                continue
            if not _matches_filter(article, filter_terms):
                scraped_urls.add(link)
                continue

            content = f"{article['content'][:900]}\n\n📰 Izvor: {source_name}\n🔗 Pročitaj više: {article['url']}"
            c_hash = _content_hash(content)
            if c_hash in content_hashes:
                scraped_urls.add(link)
                continue

            output = {
                "title": article["title"],
                "id": hashlib.md5(article["url"].encode()).hexdigest()[:8],
                "content": content,
                "url": article["url"],
                "scheduled_publish_time": None,
                "published": "",
                "source": source_hash,
                "source_name": source_name,
                "content_hash": c_hash,
                "scraped_at": datetime.now().isoformat(),
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            if article.get("image_url"):
                output["image_url"] = article["image_url"]

            filename = _next_output_filename(source_hash)
            filepath = os.path.join(JSON_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as handle:
                json.dump(output, handle, ensure_ascii=False, indent=2)

            scraped_urls.add(link)
            content_hashes.add(c_hash)
            created_files.append(filename)

        state[state_key] = {
            "target_url": target_url,
            "filter": filter_text,
            "scraped_urls": list(scraped_urls),
            "content_hashes": list(content_hashes),
            "last_run": datetime.now().isoformat(),
        }
        _save_custom_state(state)

        log_activity(client_ip, username, "CUSTOM_SCRAPE_SUCCESS", f"Created: {len(created_files)}")
        return jsonify({
            'status': 'success',
            'message': f'Custom scrape finished. Created {len(created_files)} JSON files.',
            'created_count': len(created_files),
            'created_files': created_files,
        })
    except Exception as exc:
        log_activity(client_ip, username, "CUSTOM_SCRAPE_FAILED", str(exc))
        return jsonify({'status': 'error', 'message': str(exc)}), 500


@app.route('/api/custom-scrape-reset', methods=['POST'])
@login_required
def custom_scrape_reset():
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')

    try:
        if os.path.exists(CUSTOM_SCRAPE_STATE_FILE):
            os.remove(CUSTOM_SCRAPE_STATE_FILE)

        log_activity(client_ip, username, "CUSTOM_SCRAPE_STATE_RESET", "State file cleared")
        return jsonify({
            'status': 'success',
            'message': 'Custom scrape state reset successfully.'
        })
    except Exception as exc:
        log_activity(client_ip, username, "CUSTOM_SCRAPE_STATE_RESET_FAILED", str(exc))
        return jsonify({'status': 'error', 'message': str(exc)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    count = len([f for f in os.listdir(JSON_DIR) if f.endswith('.json')]) if os.path.exists(JSON_DIR) else 0
    
    return jsonify({
        'status': 'ok',
        'service': 'facebook-posting-dashboard',
        'time': datetime.now().isoformat(),
        'article_count': count,
        'authenticated': session.get('logged_in', False)
    })

@app.route('/')
@login_required
def index():
    """Main dashboard page"""
    try:
        articles = get_articles()
        
        # Count all files correctly
        if os.path.exists(JSON_DIR):
            total = 0
            new_count = 0
            published_count = 0
            
            for filename in os.listdir(JSON_DIR):
                if filename.endswith('.json'):
                    total += 1
                    try:
                        with open(os.path.join(JSON_DIR, filename), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if data.get('published'):
                                published_count += 1
                            else:
                                new_count += 1
                    except:
                        pass
        else:
            total = 0
            new_count = 0
            published_count = 0
        
        # Get server IP
        import socket
        try:
            server_ip = socket.gethostbyname(socket.gethostname())
            if server_ip.startswith('127.'):
                # Try to get actual IP if localhost
                server_ip = request.host.split(':')[0]
        except:
            server_ip = request.host.split(':')[0]
        
        # Prepare posts for dashboard.html
        posts = []
        for article in articles:
            posts.append({
                'filename': article.get('filename', ''),
                'title': article.get('title', 'Nema naslova'),
                'title_rewritten': article.get('title_rewritten', ''),
                'summary': article.get('content_preview', '')[:120] + '...' if len(article.get('content_preview', '')) > 120 else article.get('content_preview', ''),
                'image_url': article.get('image_url', ''),
                'source': article.get('source_name', 'Unknown'),
                'time': article.get('date', 'Unknown'),
                'url': article.get('url', '#'),
                'published': article.get('published', ''),
                'published_target': article.get('published_target', '')
            })
        return render_template('dashboard.html', posts=posts, total=total, new_count=new_count, published_count=published_count, server_ip=server_ip, port=8080, now=datetime.now())
            
    except Exception as e:
        print(f"ERROR in index route: {e}")
        traceback.print_exc()
        return render_template('error.html',
            error_type='error',
            title='Dashboard Error',
            message='An error occurred while loading the dashboard.',
            error=str(e)
        ), 500

@app.route('/post/<filename>')
@login_required
def post_article(filename):
    """Post a single article to Facebook with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    target = (request.args.get('target') or 'bihac_danas').strip().lower()
    if target not in ('bihac_danas', 'konkursi'):
        target = 'bihac_danas'
    
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        log_activity(client_ip, username, "POST_FAILED", f"File not found: {filename}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        return render_template('error.html',
            error_type='error',
            title='File Not Found',
            message='The requested article file could not be found.',
            details={'File': filename}
        ), 404
    
    log_activity(client_ip, username, "POST_ATTEMPT", f"File: {filename}, Target: {target}")
    
    result = run_curl_command_for_target(filepath, target)
    
    if result.get('success'):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            data['published'] = datetime.now().isoformat()
            data['published_target'] = target
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"ERROR updating published status: {e}")
        
        log_activity(client_ip, username, "POST_SUCCESS", 
                    f"File: {filename}, Target: {target}")
        
        return redirect(url_for('index'))
    else:
        log_activity(client_ip, username, "POST_FAILED", 
                    f"File: {filename}, Target: {target}, Error: {result.get('stderr', result.get('error', 'Unknown'))[:200]}")
        
        return render_template('error.html',
            error_type='error',
            title='Failed to Post',
            message='An error occurred while posting the article.',
            details={'File': filename},
            error=result.get('stderr', result.get('error', 'Unknown'))
        )

@app.route('/delete/<filename>')
@login_required
def delete_article(filename):
    """Delete an article JSON file with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        log_activity(client_ip, username, "DELETE_FAILED", f"File not found: {filename}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        return render_template('error.html',
            error_type='error',
            title='File Not Found',
            message='The requested article file could not be found.',
            details={'File': filename}
        ), 404
    
    try:
        os.remove(filepath)
        log_activity(client_ip, username, "DELETE_SUCCESS", f"File deleted: {filename}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'success', 'message': 'File deleted'})
        return redirect(url_for('index'))
    except Exception as e:
        log_activity(client_ip, username, "DELETE_FAILED", f"File: {filename}, Error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        return render_template('error.html',
            error_type='error',
            title='Delete Failed',
            message='An error occurred while deleting the article.',
            details={'File': filename},
            error=str(e)
        )

@app.route('/get-article/<filename>')
@login_required
def get_article(filename):
    """Get article JSON data for preview"""
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/post-all-new')
@login_required
def post_all_new():
    """Post all new articles with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    articles = get_articles()
    new_articles = [a for a in articles if a.get('is_new')]
    
    log_activity(client_ip, username, "BULK_POST_ATTEMPT", 
                f"Trying to post {len(new_articles)} articles")
    
    if not new_articles:
        log_activity(client_ip, username, "BULK_POST_FAILED", "No new articles found")
        return render_template('post_results.html', results=[], success_count=0)
    
    results = []
    for article in new_articles:
        filepath = os.path.join(JSON_DIR, article['filename'])
        result = run_curl_command(filepath)
        
        if result.get('success'):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                data['published'] = datetime.now().isoformat()
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
            except:
                pass
        
        results.append({
            'filename': article['filename'],
            'title': article['title'],
            'success': result.get('success', False),
            'error': result.get('stderr', '') if not result.get('success') else ''
        })
    
    success_count = sum(1 for r in results if r['success'])
    
    log_activity(client_ip, username, "BULK_POST_COMPLETE", 
                f"Success: {success_count}/{len(results)}")
    
    return render_template('post_results.html', results=results, success_count=success_count)

@app.route('/run-scrapers')
@login_required
def run_scrapers():
    """Run all scrapers with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    log_activity(client_ip, username, "SCRAPERS_RUN_ATTEMPT")
    
    try:
        result = subprocess.run(
            ['/home/bihac-danas/web-scraper/run_all_scrapers.sh'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            log_activity(client_ip, username, "SCRAPERS_RUN_SUCCESS", 
                        f"Output length: {len(result.stdout)} chars")
        else:
            log_activity(client_ip, username, "SCRAPERS_RUN_FAILED", 
                        f"Exit code: {result.returncode}")
        
        return render_template('scraper_output.html',
                             stdout=result.stdout,
                             stderr=result.stderr,
                             returncode=result.returncode)
    except Exception as e:
        log_activity(client_ip, username, "SCRAPERS_RUN_ERROR", f"Exception: {str(e)}")
        return f"Error: {str(e)}"

@app.route('/list')
@login_required
def list_articles():
    """Simple list view"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    log_activity(client_ip, username, "VIEWED_LIST")
    
    articles = get_articles()
    
    return render_template('list.html', articles=articles)

@app.route('/view-logs')
@login_required
def view_logs():
    """View security logs"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    log_activity(client_ip, username, "VIEWED_LOGS")
    
    # Read log files
    access_log = ""
    activity_log = ""
    failed_logins = ""
    
    try:
        with open(ACCESS_LOG, 'r') as f:
            access_log = f.read()[-10000:]
    except:
        access_log = "No access log found"
    
    try:
        with open(ACTIVITY_LOG, 'r') as f:
            activity_log = f.read()[-10000:]
    except:
        activity_log = "No activity log found"
    
    try:
        with open(FAILED_LOGIN_LOG, 'r') as f:
            failed_logins = f.read()[-10000:]
    except:
        failed_logins = "No failed login log found"
    
    return render_template('logs.html',
                         access_log=access_log,
                         activity_log=activity_log,
                         failed_logins=failed_logins)

@app.route('/refresh')
@login_required
def refresh():
    """Refresh page"""
    return redirect(url_for('index'))

@app.route('/rewrite-title/<filename>', methods=['POST'])
@login_required
def rewrite_title_single(filename):
    """Rewrite title for a single article"""
    client_ip = get_client_ip()
    username = session.get('username', 'Unknown')
    
    log_activity(client_ip, username, "REWRITE_SINGLE_TITLE", f"File: {filename}")
    
    result = rewrite_single_title(filename)
    
    if result['success']:
        return jsonify({
            'status': 'success',
            'message': 'Title rewritten successfully',
            'original': result['original'],
            'rewritten': result['rewritten']
        })
    else:
        return jsonify({
            'status': 'error',
            'message': result['error']
        }), 400

@app.route('/run-rewrite-titles', methods=['POST'])
@login_required
def run_rewrite_titles():
    """Run the rewrite_titles_deepseek.sh script and show result."""
    try:
        result = subprocess.run(["/bin/bash", "rewrite_titles_deepseek.sh"], capture_output=True, text=True, timeout=120)
        output = result.stdout + "\n" + result.stderr
        status = "success" if result.returncode == 0 else "error"
    except Exception as e:
        output = str(e)
        status = "error"
    return render_template('scraper_output.html',
                          output=output,
                          status=status,
                          now=datetime.now(),
                          username=session.get('username', 'Unknown'),
                          client_ip=get_client_ip())

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print("🚀 Facebook Dashboard Starting")
    print(f"{'='*50}")
    print(f"JSON Directory: {JSON_DIR}")
    print(f"Users File: {USERS_FILE}")
    print(f"Server: http://31.31.74.183:8080")
    print(f"{'='*50}")
    print("🔐 Login with credentials from manage_users.sh")
    print(f"{'='*50}\n")
    
    # Create directories
    os.makedirs(JSON_DIR, exist_ok=True)
    
    # Run the app
    app.run(host='0.0.0.0', port=8080, debug=False)
    