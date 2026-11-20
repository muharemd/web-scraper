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

    # SSL is handled by nginx reverse proxy on port 8443.
    # Dashboard runs on plain HTTP port 8080 (internal only).
    os.makedirs(config.JSON_DIR, exist_ok=True)
    print("🔒 SSL handled by nginx on port 8443. Starting HTTP on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=False)
