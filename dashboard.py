import os
import sys

# Ensure the project root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"DEBUG: Starting dashboard.py with Python: {sys.executable}")

from dashboard_app import create_app

app = create_app()

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print("🚀 Facebook Dashboard Starting")
    print(f"{'='*50}")
    from dashboard_app import config
    print(f"JSON Directory: {config.JSON_DIR}")
    print(f"Users File: {config.USERS_FILE}")
    print(f"Webhook Path: {config.INOREADER_WEBHOOK_PATH}")
    print(f"Webhook Token Configured: {'yes' if config.INOREADER_WEBHOOK_TOKEN else 'no'}")
    print(f"Server HTTPS: https://31.31.74.183:8443")
    print(f"{'='*50}")
    print("🔐 Login with credentials from manage_users.sh")
    print(f"{'='*50}\n")

    # Keep previous runtime behavior for systemd: HTTPS on 8443 when certs exist,
    # otherwise fallback to HTTP on 8080.
    os.makedirs(config.JSON_DIR, exist_ok=True)

    cert_path = '/home/bihac-danas/web-scraper/certs/cert.pem'
    key_path = '/home/bihac-danas/web-scraper/certs/key.pem'

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print("🔒 Starting with HTTPS (8443)...")
        print(f"SSL cert: {cert_path}")
        print(f"SSL key:  {key_path}")
        from werkzeug.serving import run_simple

        run_simple(
            '0.0.0.0',
            8443,
            app,
            ssl_context=(cert_path, key_path),
            use_reloader=False,
            use_debugger=False,
        )
    else:
        print("⚠️ SSL certificates not found, running HTTP only on port 8080")
        app.run(host='0.0.0.0', port=8080, debug=False)
