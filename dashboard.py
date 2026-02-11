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
# Set a fixed, secure secret key (generated once, keep private)
app.secret_key = 'b1e2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2'
# Set session cookie options for compatibility
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_DOMAIN'] = None

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
        
        return render_template('index.html',
                             articles=articles,
                             total=total,
                             new_count=new_count,
                             published_count=published_count,
                             server_ip=server_ip,
                             port=8080,
                             now=datetime.now(),
                             username=session.get('username', 'Unknown'),
                             client_ip=get_client_ip())
            
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
    
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        log_activity(client_ip, username, "POST_FAILED", f"File not found: {filename}")
        return render_template('error.html',
            error_type='error',
            title='File Not Found',
            message='The requested article file could not be found.',
            details={'File': filename}
        ), 404
    
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
        return render_template('error.html',
            error_type='error',
            title='File Not Found',
            message='The requested article file could not be found.',
            details={'File': filename}
        ), 404
    
    try:
        os.remove(filepath)
        log_activity(client_ip, username, "DELETE_SUCCESS", f"File deleted: {filename}")
        return redirect(url_for('index'))
    except Exception as e:
        log_activity(client_ip, username, "DELETE_FAILED", f"File: {filename}, Error: {str(e)}")
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
    