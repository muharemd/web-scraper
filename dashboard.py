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

# ===== MAKE.COM WEBHOOKS =====
def load_make_webhooks():
    """Load Make.com webhook URLs from .make_tokens file"""
    config_file = "/home/bihac-danas/web-scraper/.make_tokens"
    webhooks = {
        'webhook_url': None,
        'webhook_url_konkursi': None
    }
    try:
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                if 'WEBHOOK_URL=' in line:
                    # Extract the value after the = sign
                    value = line.split('WEBHOOK_URL=', 1)[1].strip()
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    # Don't confuse WEBHOOK_URL_KONKURSI with WEBHOOK_URL
                    if 'KONKURSI' in line:
                        webhooks['webhook_url_konkursi'] = value
                    else:
                        webhooks['webhook_url'] = value
    except Exception as e:
        print(f"ERROR loading Make webhooks: {e}")
    return webhooks

# ===== CONFIGURATION =====
BASE_DIR = "/home/bihac-danas/web-scraper"
JSON_DIR = os.path.join(BASE_DIR, "facebook_ready_posts")
FB_PAGES_FILE = os.path.join(BASE_DIR, ".fb_pages.json")
FB_PAGES_PRECONFIGURED_FILE = os.path.join(BASE_DIR, ".fb_pages_preconfigured.json")
APIFY_SCRAPE_SCRIPT = os.path.join(BASE_DIR, "run_apify_facebook_scrape.sh")
WORDPRESS_PUBLISH_SCRIPT = os.path.join(BASE_DIR, "post_to_wp.sh")
APIFY_RESULT_PREFIX = "__APIFY_RESULT__"
WP_RESULT_PREFIX = "__WP_RESULT__"

WP_CATEGORIES = [
    {"id": 28, "name": "Aktuelno", "parent": 0},
    {"id": 20, "name": "Business", "parent": 0},
    {"id": 40, "name": "Elektrodistribucija", "parent": 31},
    {"id": 19, "name": "Foods", "parent": 4},
    {"id": 17, "name": "Games", "parent": 4},
    {"id": 31, "name": "Javni Servisi", "parent": 0},
    {"id": 38, "name": "Komunalno", "parent": 31},
    {"id": 22, "name": "Life Style", "parent": 0},
    {"id": 35, "name": "Najave", "parent": 0},
    {"id": 42, "name": "Obrazovanje", "parent": 31},
    {"id": 36, "name": "Odmor u Bihaću", "parent": 0},
    {"id": 44, "name": "Policija / MUP", "parent": 31},
    {"id": 33, "name": "Posao", "parent": 0},
    {"id": 41, "name": "Pošta", "parent": 31},
    {"id": 32, "name": "Servisi Za Svaki Dan", "parent": 0},
    {"id": 34, "name": "Službene Objave", "parent": 0},
    {"id": 43, "name": "Socijalna zaštita", "parent": 31},
    {"id": 30, "name": "Sport", "parent": 0},
    {"id": 21, "name": "Tech", "parent": 0},
    {"id": 13, "name": "Travel", "parent": 4},
    {"id": 1, "name": "Uncategorized", "parent": 0},
    {"id": 45, "name": "Vatrogasci", "parent": 31},
    {"id": 29, "name": "Vijesti BiH i Regija", "parent": 0},
    {"id": 26, "name": "Vijesti Bihać", "parent": 0},
    {"id": 27, "name": "Vijesti USK", "parent": 0},
    {"id": 39, "name": "Vodovod", "parent": 31},
    {"id": 4, "name": "World", "parent": 0},
    {"id": 37, "name": "Zdravstvo", "parent": 31},
]
WP_CATEGORY_IDS = {str(cat["id"]) for cat in WP_CATEGORIES}
_WP_CATEGORY_NAME_BY_ID = {cat["id"]: cat["name"] for cat in WP_CATEGORIES}
WP_CATEGORY_OPTIONS = []
for cat in WP_CATEGORIES:
    parent_id = cat.get("parent", 0)
    parent_name = _WP_CATEGORY_NAME_BY_ID.get(parent_id, "") if parent_id else ""
    label = f"{parent_name} / {cat['name']}" if parent_name else cat["name"]
    WP_CATEGORY_OPTIONS.append({
        "id": str(cat["id"]),
        "name": cat["name"],
        "parent": parent_id,
        "label": label,
    })


def load_wp_default_category():
    default_category = "36"
    config_file = os.path.join(BASE_DIR, ".wp_config")
    try:
        with open(config_file, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "WP_DEFAULT_CATEGORY=" not in line:
                    continue
                value = line.split("WP_DEFAULT_CATEGORY=", 1)[1].strip().strip('"').strip("'")
                if value.isdigit():
                    return value
    except Exception:
        pass
    return default_category

# Load Make.com webhooks from .make_tokens file
_make_webhooks = load_make_webhooks()
WEBHOOK_URL = _make_webhooks.get('webhook_url')
WEBHOOK_URL_KONKURSI = _make_webhooks.get('webhook_url_konkursi')

USERS_FILE = os.path.join(BASE_DIR, "dashboard_users.json")
CUSTOM_SCRAPE_STATE_FILE = os.path.join(BASE_DIR, "custom_dashboard_scrape_state.json")

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ===== SECURITY LOGGING =====
ACCESS_LOG = os.path.join(BASE_DIR, "dashboard_access.log")
ACTIVITY_LOG = os.path.join(BASE_DIR, "dashboard_activity.log")
FAILED_LOGIN_LOG = os.path.join(BASE_DIR, "failed_logins.log")

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
def get_articles(offset=0, limit=50):
    """Get articles from JSON files with pagination (offset/limit)"""
    articles = []
    
    if not os.path.exists(JSON_DIR):
        print(f"ERROR: JSON directory not found: {JSON_DIR}")
        return articles
    
    try:
        files = [f for f in os.listdir(JSON_DIR) if f.endswith('.json')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(JSON_DIR, x)), reverse=True)
        
        page_files = files[offset:(offset + limit)] if limit else files[offset:]
        for filename in page_files:
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
                    'image_url': data.get('image_url', ''),
                    'wp_published': data.get('wp_published', ''),
                    'wp_url': data.get('wp_url', ''),
                    'wp_post_id': data.get('wp_post_id', ''),
                    'wp_category': data.get('wp_category', ''),
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


def _extract_tagged_json(prefix, text):
    """Parse one JSON payload from a tagged stdout line."""
    for line in (text or "").splitlines():
        if line.startswith(prefix):
            raw_json = line[len(prefix):].strip()
            try:
                return json.loads(raw_json)
            except Exception:
                return None
    return None


def _default_fb_pages_payload():
    return {
        "pages": [],
        "manual_pages": [],
        "preconfigured_pages": [],
        "updated_at": datetime.now().isoformat(),
    }


def _normalize_page_url(url):
    return _clean_text(url).rstrip("/").lower()


def _stable_page_id(name, url, source_file):
    seed = f"{source_file}|{_clean_text(name)}|{_normalize_page_url(url)}"
    return hashlib.md5(seed.encode()).hexdigest()[:16]


def _load_pages_from_file(path, source_file):
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            pages = data.get("pages") if isinstance(data, dict) else None
            if not isinstance(pages, list):
                return []

            cleaned = []
            for page in pages:
                if not isinstance(page, dict):
                    continue
                name = _clean_text(page.get("name", ""))
                url = _clean_text(page.get("url", ""))
                if not name or not url:
                    continue

                cleaned.append({
                    "id": page.get("id") or _stable_page_id(name, url, source_file),
                    "name": name,
                    "url": url,
                    "enabled": bool(page.get("enabled", True)),
                    "created_at": page.get("created_at") or datetime.now().isoformat(),
                    "source_file": source_file,
                })
            return cleaned
    except Exception:
        return []


def _merge_fb_pages(preconfigured_pages, manual_pages):
    merged = {}

    for page in preconfigured_pages:
        key = _normalize_page_url(page.get("url", ""))
        if not key:
            continue
        merged[key] = page

    # Manual pages override same URLs from preconfigured file.
    for page in manual_pages:
        key = _normalize_page_url(page.get("url", ""))
        if not key:
            continue
        merged[key] = page

    return list(merged.values())


def _load_fb_pages_config():
    manual_pages = _load_pages_from_file(FB_PAGES_FILE, "manual")
    preconfigured_pages = _load_pages_from_file(FB_PAGES_PRECONFIGURED_FILE, "preconfigured")
    pages = _merge_fb_pages(preconfigured_pages, manual_pages)

    return {
        "pages": pages,
        "manual_pages": manual_pages,
        "preconfigured_pages": preconfigured_pages,
        "updated_at": datetime.now().isoformat(),
    }


def _save_fb_pages_config(payload):
    cleaned_pages = []
    for page in payload.get("pages", []):
        if not isinstance(page, dict):
            continue

        name = _clean_text(page.get("name", ""))
        url = _clean_text(page.get("url", ""))
        if not name or not url:
            continue

        source_file = page.get("source_file", "manual")
        if source_file == "preconfigured":
            continue

        cleaned_pages.append({
            "id": page.get("id") or _stable_page_id(name, url, "manual"),
            "name": name,
            "url": url,
            "enabled": bool(page.get("enabled", True)),
            "created_at": page.get("created_at") or datetime.now().isoformat(),
        })

    data = {
        "pages": cleaned_pages,
        "updated_at": datetime.now().isoformat(),
    }

    with open(FB_PAGES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    return data


def _is_valid_http_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _get_fb_pages():
    return _load_fb_pages_config().get("pages", [])


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


@app.route('/api/facebook-pages', methods=['GET'])
@login_required
def get_facebook_pages():
    pages = _get_fb_pages()
    return jsonify({
        'status': 'success',
        'pages': pages,
    })


@app.route('/api/facebook-pages', methods=['POST'])
@login_required
def add_facebook_page():
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    payload = request.get_json(silent=True) or {}

    name = _clean_text(payload.get('name', ''))
    url = _clean_text(payload.get('url', ''))
    enabled = bool(payload.get('enabled', True))

    if not name:
        return jsonify({'status': 'error', 'message': 'Page name is required'}), 400
    if not _is_valid_http_url(url):
        return jsonify({'status': 'error', 'message': 'URL must start with http:// or https://'}), 400

    config = _load_fb_pages_config()
    pages = config.get('pages', [])
    manual_pages = config.get('manual_pages', [])
    normalized_urls = {(_clean_text(p.get('url', '')).rstrip('/')).lower() for p in pages}
    if url.rstrip('/').lower() in normalized_urls:
        return jsonify({'status': 'error', 'message': 'This page URL is already in the list'}), 409

    new_page = {
        'id': secrets.token_hex(8),
        'name': name,
        'url': url,
        'enabled': enabled,
        'created_at': datetime.now().isoformat(),
        'source_file': 'manual',
    }
    manual_pages.append(new_page)
    _save_fb_pages_config({'pages': manual_pages})

    log_activity(client_ip, username, 'FB_PAGE_ADDED', f"{name} | {url}")
    return jsonify({
        'status': 'success',
        'message': 'Facebook page source added.',
        'page': new_page,
    })


@app.route('/api/facebook-pages/<page_id>/toggle', methods=['POST'])
@login_required
def toggle_facebook_page(page_id):
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    payload = request.get_json(silent=True) or {}

    config = _load_fb_pages_config()
    pages = config.get('pages', [])
    target_page = next((p for p in pages if p.get('id') == page_id), None)
    if not target_page:
        return jsonify({'status': 'error', 'message': 'Page not found'}), 404

    if target_page.get('source_file') == 'preconfigured':
        return jsonify({
            'status': 'error',
            'message': 'This is a preconfigured page. Edit .fb_pages_preconfigured.json to change it.'
        }), 400

    manual_pages = config.get('manual_pages', [])
    manual_target = next((p for p in manual_pages if p.get('id') == page_id), None)
    if not manual_target:
        return jsonify({'status': 'error', 'message': 'Manual page not found'}), 404

    if 'enabled' in payload:
        manual_target['enabled'] = bool(payload.get('enabled'))
    else:
        manual_target['enabled'] = not bool(manual_target.get('enabled', True))

    _save_fb_pages_config({'pages': manual_pages})
    log_activity(client_ip, username, 'FB_PAGE_TOGGLED', f"{manual_target.get('name', '')} -> {manual_target.get('enabled')}")

    return jsonify({
        'status': 'success',
        'message': 'Facebook page updated.',
        'page': manual_target,
    })


@app.route('/api/facebook-pages/<page_id>', methods=['DELETE'])
@login_required
def delete_facebook_page(page_id):
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')

    config = _load_fb_pages_config()
    pages = config.get('pages', [])
    target_page = next((p for p in pages if p.get('id') == page_id), None)
    if not target_page:
        return jsonify({'status': 'error', 'message': 'Page not found'}), 404

    if target_page.get('source_file') == 'preconfigured':
        return jsonify({
            'status': 'error',
            'message': 'This is a preconfigured page. Edit .fb_pages_preconfigured.json to remove it.'
        }), 400

    manual_pages = config.get('manual_pages', [])
    manual_pages = [p for p in manual_pages if p.get('id') != page_id]
    _save_fb_pages_config({'pages': manual_pages})
    log_activity(client_ip, username, 'FB_PAGE_DELETED', f"{target_page.get('name', '')}")

    return jsonify({
        'status': 'success',
        'message': 'Facebook page removed.',
    })


@app.route('/api/run-apify-scrape', methods=['POST'])
@login_required
def run_apify_scrape():
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    log_activity(client_ip, username, 'APIFY_SCRAPE_ATTEMPT')

    if not os.path.exists(APIFY_SCRAPE_SCRIPT):
        message = f'Apify scrape script not found: {APIFY_SCRAPE_SCRIPT}'
        log_activity(client_ip, username, 'APIFY_SCRAPE_FAILED', message)
        return jsonify({'status': 'error', 'message': message}), 500

    try:
        result = subprocess.run(
            ['/bin/bash', APIFY_SCRAPE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=900,
            cwd=BASE_DIR,
        )
    except Exception as exc:
        log_activity(client_ip, username, 'APIFY_SCRAPE_FAILED', str(exc))
        return jsonify({'status': 'error', 'message': str(exc)}), 500

    parsed = _extract_tagged_json(APIFY_RESULT_PREFIX, result.stdout)
    combined_output = (result.stdout or '')
    if result.stderr:
        combined_output = f"{combined_output}\n{result.stderr}"
    combined_output = combined_output.strip()

    if result.returncode != 0:
        log_activity(client_ip, username, 'APIFY_SCRAPE_FAILED', f"Exit code: {result.returncode}")
        return jsonify({
            'status': 'error',
            'message': 'Apify scrape failed. Check output for details.',
            'output': combined_output[-5000:],
            'returncode': result.returncode,
        }), 500

    created_count = int((parsed or {}).get('created_count', 0))
    created_files = (parsed or {}).get('created_files', [])
    log_activity(client_ip, username, 'APIFY_SCRAPE_SUCCESS', f"Created: {created_count}")

    return jsonify({
        'status': 'success',
        'message': f'Apify scrape finished. Created {created_count} JSON files.',
        'created_count': created_count,
        'created_files': created_files,
        'output': combined_output[-5000:],
    })

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
        per_page = 50
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        offset = (page - 1) * per_page

        articles = get_articles(offset=offset, limit=per_page)
        
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
                'published_target': article.get('published_target', ''),
                'wp_published': article.get('wp_published', ''),
                'wp_url': article.get('wp_url', ''),
                'wp_post_id': article.get('wp_post_id', ''),
                'wp_category': article.get('wp_category', ''),
            })
        wp_default_category = load_wp_default_category()
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template(
            'dashboard.html',
            posts=posts,
            total=total,
            new_count=new_count,
            published_count=published_count,
            server_ip=server_ip,
            port=8080,
            now=datetime.now(),
            wp_categories=WP_CATEGORY_OPTIONS,
            wp_default_category=wp_default_category,
            page=page,
            total_pages=total_pages,
            per_page=per_page,
        )
            
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


@app.route('/publish-wp/<filename>', methods=['POST'])
@login_required
def publish_wordpress_article(filename):
    """Publish one JSON article to WordPress using post_to_wp.sh"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    filepath = os.path.join(JSON_DIR, filename)

    payload = request.get_json(silent=True) if request.is_json else {}
    selected_wp_category = _clean_text(request.form.get('wp_category', ''))
    if not selected_wp_category and isinstance(payload, dict):
        selected_wp_category = _clean_text(str(payload.get('wp_category', '')))
    if selected_wp_category and not selected_wp_category.isdigit():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'WordPress category must be numeric.'}), 400
        return render_template(
            'error.html',
            error_type='error',
            title='Invalid WordPress Category',
            message='WordPress category must be numeric.',
            details={'File': filename, 'Category': selected_wp_category},
        ), 400
    if selected_wp_category and selected_wp_category not in WP_CATEGORY_IDS:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'Selected category is not in the dashboard list.'}), 400
        return render_template(
            'error.html',
            error_type='error',
            title='Invalid WordPress Category',
            message='Selected category is not in the dashboard list.',
            details={'File': filename, 'Category': selected_wp_category},
        ), 400

    if not os.path.exists(filepath):
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", f"File not found: {filename}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        return render_template(
            'error.html',
            error_type='error',
            title='File Not Found',
            message='The requested article file could not be found.',
            details={'File': filename}
        ), 404

    if not os.path.exists(WORDPRESS_PUBLISH_SCRIPT):
        msg = f'WordPress script not found: {WORDPRESS_PUBLISH_SCRIPT}'
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': msg}), 500
        return render_template(
            'error.html',
            error_type='error',
            title='WordPress Script Missing',
            message='WordPress publish script was not found.',
            error=msg,
        ), 500

    log_activity(client_ip, username, "WP_PUBLISH_ATTEMPT", f"File: {filename}, Category: {selected_wp_category or 'default'}")

    command = ['/bin/bash', WORDPRESS_PUBLISH_SCRIPT, filepath]
    if selected_wp_category:
        command.append(selected_wp_category)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=BASE_DIR,
        )
    except Exception as exc:
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", str(exc))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'status': 'error', 'message': str(exc)}), 500
        return render_template(
            'error.html',
            error_type='error',
            title='WordPress Publish Error',
            message='An exception occurred while publishing to WordPress.',
            details={'File': filename},
            error=str(exc),
        ), 500

    combined_output = (result.stdout or '')
    if result.stderr:
        combined_output = f"{combined_output}\n{result.stderr}"
    parsed = _extract_tagged_json(WP_RESULT_PREFIX, result.stdout)

    if result.returncode != 0:
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", f"File: {filename}, Exit code: {result.returncode}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'WordPress publish failed.',
                'output': combined_output[-5000:],
                'returncode': result.returncode,
            }), 500
        return render_template(
            'error.html',
            error_type='error',
            title='WordPress Publish Failed',
            message='An error occurred while publishing the article to WordPress.',
            details={'File': filename},
            error=combined_output[-5000:],
        ), 500

    try:
        with open(filepath, 'r', encoding='utf-8') as handle:
            data = json.load(handle)

        data['wp_published'] = datetime.now().isoformat()
        if selected_wp_category:
            data['wp_category'] = int(selected_wp_category)
        if parsed:
            if parsed.get('post_id'):
                data['wp_post_id'] = str(parsed.get('post_id'))
            if parsed.get('link'):
                data['wp_url'] = parsed.get('link')

        with open(filepath, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_activity(client_ip, username, "WP_PUBLISH_METADATA_FAILED", f"{filename}: {exc}")

    log_activity(client_ip, username, "WP_PUBLISH_SUCCESS", f"File: {filename}, Category: {selected_wp_category or 'default'}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'status': 'success',
            'message': 'Published to WordPress.',
            'result': parsed or {},
            'wp_category': selected_wp_category or None,
            'output': combined_output[-2000:],
        })

    return redirect(url_for('index'))

@app.route('/api/delete-multiple', methods=['POST'])
@login_required
def delete_multiple_articles():
    """Bulk delete multiple article JSON files"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')

    payload = request.get_json(silent=True) or {}
    filenames = payload.get('filenames', [])

    if not isinstance(filenames, list):
        return jsonify({'status': 'error', 'message': 'filenames must be a list'}), 400

    deleted = []
    errors = []

    for filename in filenames:
        # Security: prevent path traversal
        if not filename or '/' in filename or '\\' in filename or '..' in filename:
            errors.append({'filename': filename, 'error': 'Invalid filename'})
            continue
        if not filename.endswith('.json'):
            errors.append({'filename': filename, 'error': 'Not a JSON file'})
            continue

        filepath = os.path.join(JSON_DIR, os.path.basename(filename))
        if not os.path.exists(filepath):
            errors.append({'filename': filename, 'error': 'File not found'})
            continue

        try:
            os.remove(filepath)
            deleted.append(filename)
        except Exception as exc:
            errors.append({'filename': filename, 'error': str(exc)})

    log_activity(client_ip, username, 'BULK_DELETE',
                 f'Deleted: {len(deleted)}, Errors: {len(errors)}')

    return jsonify({
        'status': 'success',
        'deleted_count': len(deleted),
        'deleted': deleted,
        'errors': errors,
    })


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
    
    articles = get_articles(limit=None)
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
    
    articles = get_articles(limit=None)
    
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

@app.route('/facebook')
@login_required
def facebook_tools():
    """Facebook tools page (Apify scrape + pages management)"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    log_activity(client_ip, username, 'VIEWED_FACEBOOK_TOOLS')

    try:
        import socket
        try:
            server_ip = socket.gethostbyname(socket.gethostname())
            if server_ip.startswith('127.'):
                server_ip = request.host.split(':')[0]
        except Exception:
            server_ip = request.host.split(':')[0]

        return render_template(
            'facebook.html',
            server_ip=server_ip,
            port=8080,
            now=datetime.now(),
            username=username,
        )
    except Exception as exc:
        return render_template('error.html',
            error_type='error',
            title='Facebook Tools Error',
            message='An error occurred while loading the Facebook tools page.',
            error=str(exc)
        ), 500

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
        result = subprocess.run(
            ["/bin/bash", os.path.join(BASE_DIR, "rewrite_titles_deepseek.sh")],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=BASE_DIR,
        )
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
    # print(f"Server HTTP:  http://31.31.74.183:8080")
    print(f"Server HTTPS: https://31.31.74.183:8443")
    print(f"{'='*50}")
    print("🔐 Login with credentials from manage_users.sh")
    print(f"{'='*50}\n")
    
    # Create directories
    os.makedirs(JSON_DIR, exist_ok=True)
    
    # Check if SSL certificates exist
    cert_path = '/home/bihac-danas/web-scraper/certs/cert.pem'
    key_path = '/home/bihac-danas/web-scraper/certs/key.pem'
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        # Run with HTTPS only (HTTP port 8080 disabled - uncomment below to re-enable)
        print("🔒 Starting with HTTPS (8443) only...")
        # import threading
        from werkzeug.serving import run_simple
        
        # # Run HTTP in background thread (DISABLED - uncomment to re-enable)
        # def run_http():
        #     app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        # 
        # http_thread = threading.Thread(target=run_http, daemon=True)
        # http_thread.start()
        
        # Run HTTPS in main thread
        run_simple('0.0.0.0', 8443, app, ssl_context=(cert_path, key_path), use_reloader=False, use_debugger=False)
    else:
        # Fallback to HTTP only
        print("⚠️ SSL certificates not found, running HTTP only on port 8080")
        app.run(host='0.0.0.0', port=8080, debug=False)
    