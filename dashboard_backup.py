#!/usr/bin/env python3
"""
Facebook Posting Dashboard - Fixed with proper error handling
"""

import os
import sys
import json
import subprocess
import traceback
from datetime import datetime
from flask import Flask, render_template, jsonify, redirect, url_for

print(f"DEBUG: Starting dashboard.py with Python: {sys.executable}")

app = Flask(__name__, template_folder='templates')

# ===== CONFIGURATION =====
JSON_DIR = "/home/bihac-danas/web-scraper/facebook_ready_posts"
WEBHOOK_URL = "https://hook.eu1.make.com/p1kanqk3w243rnyaio8gbeeiosvhddgb"
# =========================

def get_articles_safe(limit=30):
    """Safe version that won't hang"""
    articles = []
    
    if not os.path.exists(JSON_DIR):
        print(f"DEBUG: JSON_DIR {JSON_DIR} doesn't exist")
        return articles
    
    try:
        files = [f for f in os.listdir(JSON_DIR) if f.endswith('.json')]
        print(f"DEBUG: Found {len(files)} JSON files")
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: os.path.getmtime(os.path.join(JSON_DIR, x)), reverse=True)
        
        # Process only limited number
        for filename in files[:limit]:
            filepath = os.path.join(JSON_DIR, filename)
            
            try:
                # Quick read - minimal data
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Get source from filename
                source_hash = filename.split('-')[0] if '-' in filename else filename[:12]
                source_name = "Unknown"
                
                # Simple source detection
                if 'dz' in source_hash.lower():
                    source_name = 'Dom zdravlja'
                elif 'vod' in source_hash.lower():
                    source_name = 'Vodovod'
                elif 'bihac' in source_hash.lower():
                    source_name = 'Grad Bihać'
                elif 'usk' in source_hash.lower():
                    source_name = 'USK'
                elif 'krajina' in source_hash.lower():
                    source_name = 'USN Krajina'
                elif 'komrad' in source_hash.lower():
                    source_name = 'Komrad'
                elif 'radio' in source_hash.lower():
                    source_name = 'Radio'
                elif 'rtv' in source_hash.lower():
                    source_name = 'RTV'
                
                articles.append({
                    'filename': filename,
                    'title': data.get('title', 'Nema naslova')[:80],
                    'content_preview': (data.get('content', '')[:100] + '...') if data.get('content') else '',
                    'date': data.get('date', 'Unknown'),
                    'published': data.get('published', ''),
                    'source_name': source_name,
                    'url': data.get('url', '#'),
                    'is_new': not bool(data.get('published'))
                })
                
            except Exception as e:
                print(f"DEBUG: Error reading {filename}: {e}")
                continue
                
    except Exception as e:
        print(f"DEBUG: Error in get_articles_safe: {e}")
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
        'python': sys.executable.split('/')[-1]
    })

@app.route('/')
def index():
    """Main dashboard page - SIMPLIFIED"""
    try:
        articles = get_articles_safe(limit=20)
        total = len([f for f in os.listdir(JSON_DIR) if f.endswith('.json')]) if os.path.exists(JSON_DIR) else 0
        new_count = sum(1 for a in articles if a.get('is_new'))
        published_count = len(articles) - new_count
        
        # Get server IP
        server_ip = '31.31.74.183'
        
        print(f"DEBUG: Rendering index with {len(articles)} articles")
        
        # Try to render template, if fails use simple HTML
        try:
            return render_template('index.html',
                                 articles=articles,
                                 total=total,
                                 new_count=new_count,
                                 published_count=published_count,
                                 server_ip=server_ip,
                                 port=8080,
                                 now=datetime.now())
        except Exception as e:
            print(f"DEBUG: Template error: {e}")
            # Fallback to simple HTML
            return f"""
            <html>
            <head><title>Facebook Dashboard</title></head>
            <body>
                <h1>Facebook Posting Dashboard</h1>
                <p>Total: {total} | New: {new_count} | Published: {published_count}</p>
                <p>Server: {server_ip}:8080</p>
                <p><a href="/health">Health Check</a> | <a href="/list">List View</a></p>
                <hr>
                {"".join(f'<div><h3>{a["title"]}</h3><p>{a["source_name"]} - {a["date"]}</p><a href="/post/{a["filename"]}">Post</a></div>' for a in articles[:10])}
            </body>
            </html>
            """
            
    except Exception as e:
        print(f"DEBUG: Error in index route: {e}")
        traceback.print_exc()
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1>Error Loading Dashboard</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/health">Health Check</a> | <a href="/list">Simple List</a></p>
        </body>
        </html>
        """, 500

@app.route('/post/<filename>')
def post_article(filename):
    """Post a single article to Facebook"""
    filepath = os.path.join(JSON_DIR, filename)
    
    if not os.path.exists(filepath):
        return f"File not found: {filename}", 404
    
    result = run_curl_command(filepath)
    
    if result.get('success'):
        # Mark as published
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            data['published'] = datetime.now().isoformat()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass
        
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: green;">✅ Posted Successfully!</h1>
            <p>File: {filename}</p>
            <p>Time: {datetime.now().strftime('%H:%M:%S')}</p>
            <p><a href="/">← Back to Dashboard</a></p>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: red;">❌ Failed to Post</h1>
            <p>File: {filename}</p>
            <p>Error: {result.get('stderr', result.get('error', 'Unknown'))}</p>
            <p><a href="/">← Back to Dashboard</a></p>
        </body>
        </html>
        """

@app.route('/post-all-new')
def post_all_new():
    """Post all new articles"""
    articles = get_articles_safe(limit=50)
    new_articles = [a for a in articles if a.get('is_new')]
    
    if not new_articles:
        return "No new articles found", 404
    
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
            'success': result.get('success', False)
        })
    
    success_count = sum(1 for r in results if r['success'])
    
    # Simple HTML instead of template
    html = f"""
    <html>
    <body style="font-family: Arial; padding: 20px;">
        <h1>Posting Results</h1>
        <p>Success: {success_count} / {len(results)}</p>
        {"".join(f'<div>{"✅" if r["success"] else "❌"} {r["title"]}</div>' for r in results)}
        <p><a href="/">← Back</a></p>
    </body>
    </html>
    """
    return html

@app.route('/run-scrapers')
def run_scrapers():
    """Run all scrapers"""
    try:
        result = subprocess.run(
            ['/home/bihac-danas/web-scraper/run_all_scrapers.sh'],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return f"""
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h1>Scrapers Output</h1>
            <pre>{result.stdout[:5000]}</pre>
            <pre style="color: red">{result.stderr[:5000]}</pre>
            <p><a href="/">← Back</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/list')
def list_articles():
    """Simple list view"""
    articles = get_articles_safe(limit=100)
    
    html = "<html><head><title>Article List</title></head><body>"
    html += f"<h1>Articles ({len(articles)})</h1>"
    html += "<p><a href='/'>← Dashboard</a></p>"
    
    for article in articles:
        html += f"""
        <div style="border:1px solid #ddd; padding:10px; margin:5px;">
            <h3>{article['title']}</h3>
            <p>File: {article['filename']} | Source: {article['source_name']}</p>
            <p>Date: {article['date']} | Status: {'Published' if article['published'] else 'New'}</p>
            <a href="/post/{article['filename']}">📤 Post</a>
        </div>
        """
    
    html += "</body></html>"
    return html

@app.route('/refresh')
def refresh():
    return redirect(url_for('index'))

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print("🚀 Facebook Dashboard Starting")
    print(f"{'='*50}")
    print(f"Python: {sys.executable}")
    print(f"Port: 8080")
    print(f"JSON Dir: {JSON_DIR}")
    print(f"Templates: {os.path.join(os.getcwd(), 'templates')}")
    print(f"{'='*50}\n")
    
    app.run(host='0.0.0.0', port=8080, debug=False)
