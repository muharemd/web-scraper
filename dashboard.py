#!/usr/bin/env python3
"""
Facebook Posting Dashboard - SIMPLIFIED WORKING VERSION
No ipaddress module dependency
"""

import os
import sys
import json
import subprocess
import traceback
import hashlib
import secrets
import bcrypt
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, jsonify, redirect, url_for, request, session

print(f"DEBUG: Starting dashboard.py with Python: {sys.executable}")

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ===== CONFIGURATION =====
JSON_DIR = "/home/bihac-danas/web-scraper/facebook_ready_posts"
WEBHOOK_URL = "https://hook.eu1.make.com/p1kanqk3w243rnyaio8gbeeiosvhddgb"
USERS_FILE = "/home/bihac-danas/web-scraper/dashboard_users.json"

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
            return render_login_form(error="Please enter both username and password")
        
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
            
            return render_login_form(error="Invalid username or password")
    
    log_access(client_ip, "ANONYMOUS", "LOGIN_PAGE_VIEW")
    return render_login_form()

def render_login_form(error=None):
    """Render login form"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard Login</title>
        <style>
            body {{ font-family: Arial; background: #667eea; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .login-box {{ background: white; padding: 2rem; border-radius: 10px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }}
            h1 {{ color: #333; text-align: center; margin-bottom: 1.5rem; }}
            .form-group {{ margin-bottom: 1rem; }}
            label {{ display: block; margin-bottom: 0.5rem; color: #555; }}
            input {{ width: 100%; padding: 0.75rem; border: 2px solid #ddd; border-radius: 5px; font-size: 1rem; }}
            button {{ width: 100%; padding: 0.75rem; background: #667eea; color: white; border: none; border-radius: 5px; font-size: 1rem; cursor: pointer; margin-top: 1rem; }}
            .error {{ background: #fee; color: #c33; padding: 0.75rem; border-radius: 5px; margin-bottom: 1rem; border-left: 4px solid #c33; }}
        </style>
    </head>
    <body>
        <div class="login-box">
            <h1>🔐 Dashboard Login</h1>
            {f'<div class="error">{error}</div>' if error else ''}
            <form method="POST">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required autofocus>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit">Sign In</button>
            </form>
        </div>
    </body>
    </html>
    '''

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
                
                # Determine source from filename
                source_name = "Unknown"
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
                content_preview = content[:200] + '...' if len(content) > 200 else content
                
                articles.append({
                    'filename': filename,
                    'title': data.get('title', 'Nema naslova'),
                    'content': content,
                    'content_preview': content_preview,
                    'date': data.get('date', 'Unknown'),
                    'published': data.get('published', ''),
                    'source_name': source_name,
                    'url': data.get('url', '#'),
                    'is_new': not bool(data.get('published'))
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
    try:
        cmd = [
            'curl', '-X', 'POST',
            '-H', 'Content-Type: application/json',
            '-d', f'@{json_file_path}',
            WEBHOOK_URL,
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
        total = len([f for f in os.listdir(JSON_DIR) if f.endswith('.json')]) if os.path.exists(JSON_DIR) else 0
        new_count = sum(1 for a in articles if a.get('is_new'))
        published_count = total - new_count
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Facebook Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                .header {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 10px; flex: 1; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .new {{ border-top: 4px solid #4CAF50; }}
                .published {{ border-top: 4px solid #2196F3; }}
                .total {{ border-top: 4px solid #9C27B0; }}
                .article-card {{ 
                    background: white; 
                    padding: 20px; 
                    margin-bottom: 15px; 
                    border-radius: 8px; 
                    border-left: 4px solid #FF9800;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                }}
                .article-card.published {{ border-left-color: #4CAF50; }}
                .article-title {{ 
                    font-size: 18px; 
                    font-weight: bold; 
                    margin-bottom: 10px; 
                    color: #333;
                }}
                .article-meta {{ 
                    color: #666; 
                    font-size: 14px; 
                    margin-bottom: 10px;
                    display: flex;
                    gap: 15px;
                }}
                .article-content {{ 
                    background: #f9f9f9; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 15px 0;
                    border-left: 3px solid #ddd;
                    font-size: 15px;
                    line-height: 1.5;
                    max-height: 300px;
                    overflow-y: auto;
                }}
                .actions {{ margin-top: 15px; }}
                .btn {{ 
                    padding: 8px 16px; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer; 
                    text-decoration: none; 
                    display: inline-block;
                    margin-right: 10px;
                    font-size: 14px;
                }}
                .btn-post {{ background: #4CAF50; color: white; }}
                .btn-post-all {{ background: #2196F3; color: white; }}
                .btn-run {{ background: #9C27B0; color: white; }}
                .btn-logout {{ background: #f44336; color: white; }}
                .nav {{ margin: 20px 0; }}
                .user-info {{ float: right; color: #666; }}
                .status-new {{ color: #4CAF50; font-weight: bold; }}
                .status-published {{ color: #2196F3; }}
                .content-toggle {{ 
                    background: none;
                    border: none;
                    color: #667eea;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 0;
                    margin-left: 10px;
                }}
            </style>
            <script>
                function toggleContent(id) {{
                    var content = document.getElementById('content-' + id);
                    var btn = document.getElementById('toggle-' + id);
                    if (content.style.display === 'none') {{
                        content.style.display = 'block';
                        btn.textContent = '↑ Collapse';
                    }} else {{
                        content.style.display = 'none';
                        btn.textContent = '↓ Expand';
                    }}
                }}
                
                function confirmPostAll() {{
                    return confirm('Post ALL {new_count} new articles?');
                }}
            </script>
        </head>
        <body>
            <div class="header">
                <h1>🚀 Facebook Posting Dashboard</h1>
                <div class="user-info">
                    User: {session.get('username', 'Unknown')}<br>
                    IP: {get_client_ip()}
                </div>
                <div class="nav">
                    <a href="/refresh" class="btn">🔄 Refresh</a>
                    <a href="/post-all-new" class="btn btn-post-all" onclick="return confirmPostAll()">📤 Post All New ({new_count})</a>
                    <a href="/run-scrapers" class="btn btn-run">🤖 Run Scrapers</a>
                    <a href="/list" class="btn">📋 List View</a>
                    <a href="/view-logs" class="btn">📊 View Logs</a>
                    <a href="/logout" class="btn btn-logout">🚪 Logout</a>
                </div>
            </div>
            
            <div class="stats">
                <div class="stat-card total">
                    <h3>📁 Total</h3>
                    <h1>{total}</h1>
                </div>
                <div class="stat-card new">
                    <h3>🆕 New</h3>
                    <h1>{new_count}</h1>
                </div>
                <div class="stat-card published">
                    <h3>✅ Published</h3>
                    <h1>{published_count}</h1>
                </div>
            </div>
            
            <h2>Latest Articles</h2>
        '''
        
        if not articles:
            html += '<p>No articles found. Run scrapers first.</p>'
        else:
            for i, article in enumerate(articles[:20]):
                is_new = article['is_new']
                status_class = "status-new" if is_new else "status-published"
                status_text = "🆕 NEW" if is_new else f"✅ Published: {article['published'][:19] if article['published'] else ''}"
                
                html += f'''
                <div class="article-card {'published' if not is_new else ''}">
                    <div class="article-title">{article['title']}</div>
                    <div class="article-meta">
                        <span><strong>Source:</strong> {article['source_name']}</span>
                        <span><strong>Date:</strong> {article['date']}</span>
                        <span class="{status_class}">{status_text}</span>
                        <button class="content-toggle" id="toggle-{i}" onclick="toggleContent({i})">↓ Expand</button>
                    </div>
                    
                    <div class="article-content" id="content-{i}" style="display: none;">
                        {article['content'].replace('<', '&lt;').replace('>', '&gt;').replace('\\n', '<br>')}
                    </div>
                    
                    <div class="actions">
                '''
                
                if is_new:
                    html += f'''
                        <a href="/post/{article['filename']}" class="btn btn-post">📤 Post to Facebook</a>
                    '''
                
                html += f'''
                        <small>File: {article['filename']}</small>
                    </div>
                </div>
                '''
        
        html += '''
        </body>
        </html>
        '''
        
        return html
            
    except Exception as e:
        print(f"ERROR in index route: {e}")
        traceback.print_exc()
        return f'''
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1>Dashboard Error</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/">Refresh</a> | <a href="/logout">Logout</a></p>
        </body>
        </html>
        ''', 500

@app.route('/post/<filename>')
@login_required
def post_article(filename):
    """Post a single article to Facebook with logging"""
    client_ip = get_client_ip()
    username = session.get('username', 'UNKNOWN')
    
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        log_activity(client_ip, username, "POST_FAILED", f"File not found: {filename}")
        return f"File not found: {filename}", 404
    
    log_activity(client_ip, username, "POST_ATTEMPT", f"File: {filename}")
    
    result = run_curl_command(filepath)
    
    if result.get('success'):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            data['published'] = datetime.now().isoformat()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"ERROR updating published status: {e}")
        
        log_activity(client_ip, username, "POST_SUCCESS", 
                    f"File: {filename}")
        
        return redirect(url_for('index'))
    else:
        log_activity(client_ip, username, "POST_FAILED", 
                    f"File: {filename}, Error: {result.get('stderr', result.get('error', 'Unknown'))[:200]}")
        
        return f'''
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: red;">❌ Failed to Post</h1>
            <p>File: {filename}</p>
            <p>Error: {result.get('stderr', result.get('error', 'Unknown'))}</p>
            <p><a href="/">← Back</a></p>
        </body>
        </html>
        '''

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
        return '''
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1>No New Articles</h1>
            <p>No new articles found to post.</p>
            <p><a href="/">← Back</a></p>
        </body>
        </html>
        '''
    
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
    
    html = f'''
    <html>
    <head>
        <title>Posting Results</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .success {{ background: #f0fff0; padding: 10px; margin: 5px; border-left: 4px solid #4CAF50; }}
            .error {{ background: #fff0f0; padding: 10px; margin: 5px; border-left: 4px solid #f44336; }}
        </style>
    </head>
    <body>
        <h1>📤 Posting Results</h1>
        <p>Success: <strong>{success_count}</strong> / {len(results)}</p>
        <p><a href="/">← Back to Dashboard</a></p>
        <hr>
    '''
    
    for r in results:
        if r['success']:
            html += f'''
            <div class="success">
                ✅ <strong>{r['title']}</strong><br>
                <small>File: {r['filename']}</small>
            </div>
            '''
        else:
            html += f'''
            <div class="error">
                ❌ <strong>{r['title']}</strong><br>
                <small>Error: {r['error'][:100]}</small>
            </div>
            '''
    
    html += '</body></html>'
    return html

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
        
        html = f'''
        <html>
        <head>
            <title>Scrapers Output</title>
            <style>
                body {{ font-family: monospace; padding: 20px; }}
                pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; max-height: 600px; overflow: auto; }}
                .error {{ background: #fff0f0; color: #c00; }}
            </style>
        </head>
        <body>
            <h1>🤖 Scrapers Output</h1>
            <pre>{result.stdout}</pre>
            <pre class="error">{result.stderr}</pre>
            <p><a href="/">← Back</a></p>
        </body>
        </html>
        '''
        return html
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
    
    html = f'''
    <html>
    <head>
        <title>Article List</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .article {{ 
                border: 1px solid #ddd; 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 5px;
                background: white;
            }}
            .new {{ border-left: 4px solid #4CAF50; }}
            .published {{ border-left: 4px solid #2196F3; }}
            .article-content {{
                background: #f9f9f9;
                padding: 10px;
                margin: 10px 0;
                border-radius: 3px;
                font-size: 14px;
                max-height: 200px;
                overflow-y: auto;
            }}
            .btn {{ 
                padding: 5px 10px; 
                background: #4CAF50; 
                color: white; 
                text-decoration: none;
                border-radius: 3px;
                display: inline-block;
                margin-right: 5px;
            }}
        </style>
    </head>
    <body>
        <h1>📋 All Articles ({len(articles)})</h1>
        <p><a href="/">← Dashboard</a> | <a href="/logout">Logout</a></p>
        <hr>
    '''
    
    for article in articles:
        status_class = "new" if article['is_new'] else "published"
        status_text = "🆕 NEW" if article['is_new'] else f"✅ Published: {article['published'][:19] if article['published'] else ''}"
        btn = f'<a href="/post/{article["filename"]}" class="btn">📤 Post</a>' if article['is_new'] else ''
        
        html += f'''
        <div class="article {status_class}">
            <h3>{article['title']}</h3>
            <p><strong>{article['source_name']}</strong> | {article['date']} | {status_text}</p>
            <div class="article-content">
                {article['content'].replace('<', '&lt;').replace('>', '&gt;').replace('\\n', '<br>')}
            </div>
            <p>
                {btn}
                <small>File: {article['filename']}</small>
            </p>
        </div>
        '''
    
    html += '</body></html>'
    return html

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
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Security Logs</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .header {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .log-section {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 10px; }}
            pre {{ 
                background: #f9f9f9; 
                padding: 15px; 
                border-radius: 5px; 
                overflow: auto; 
                max-height: 400px;
                font-family: monospace;
                font-size: 12px;
                border: 1px solid #ddd;
            }}
            .btn {{ 
                padding: 8px 16px; 
                border: none; 
                border-radius: 4px; 
                cursor: pointer; 
                text-decoration: none; 
                display: inline-block;
                margin-right: 10px;
                font-size: 14px;
                background: #607d8b; 
                color: white; 
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Security Logs</h1>
            <p><a href="/" class="btn">← Back to Dashboard</a></p>
        </div>
        
        <div class="log-section">
            <h2>🛡️ Failed Login Attempts</h2>
            <pre>{failed_logins}</pre>
        </div>
        
        <div class="log-section">
            <h2>👤 Access Log</h2>
            <pre>{access_log}</pre>
        </div>
        
        <div class="log-section">
            <h2>📝 Activity Log</h2>
            <pre>{activity_log}</pre>
        </div>
    </body>
    </html>
    '''
    
    return html

@app.route('/refresh')
@login_required
def refresh():
    """Refresh page"""
    return redirect(url_for('index'))

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
    