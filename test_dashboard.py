"""
Quick import + route sanity check for the modularised dashboard.
Run with: python test_dashboard.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1. App factory imports without errors
from dashboard_app import create_app
app = create_app()

# 2. All original URL rules still exist
EXPECTED_ROUTES = [
    "/",
    "/login",
    "/logout",
    "/health",
    "/list",
    "/refresh",
    "/view-logs",
    "/facebook",
    "/manual-entry",
    "/post/<filename>",
    "/post-all-new",
    "/delete/<filename>",
    "/get-article/<filename>",
    "/api/delete-multiple",
    "/publish-wp/<filename>",
    "/run-scrapers",
    "/api/custom-scrape",
    "/api/custom-scrape-reset",
    "/api/run-apify-scrape",
    "/api/facebook-pages",
    "/api/facebook-pages/<page_id>/toggle",
    "/api/facebook-pages/<page_id>",
    "/rewrite-title/<filename>",
    "/run-rewrite-titles",
]

registered = {rule.rule for rule in app.url_map.iter_rules()}
missing = [r for r in EXPECTED_ROUTES if r not in registered]

if missing:
    print(f"FAIL — missing routes:\n  " + "\n  ".join(missing))
    sys.exit(1)

print(f"OK — all {len(EXPECTED_ROUTES)} expected routes are registered.")

# 3. Config values are sensible
from dashboard_app.config import BASE_DIR, JSON_DIR, WP_CATEGORIES, WP_CATEGORY_OPTIONS
assert os.path.isdir(BASE_DIR), f"BASE_DIR does not exist: {BASE_DIR}"
assert len(WP_CATEGORIES) > 0, "WP_CATEGORIES is empty"
assert len(WP_CATEGORY_OPTIONS) == len(WP_CATEGORIES), "WP_CATEGORY_OPTIONS length mismatch"
print(f"OK — config: BASE_DIR={BASE_DIR}, {len(WP_CATEGORIES)} WP categories")

# 4. Auth helpers
from dashboard_app.auth import load_users, verify_password
users = load_users()
assert isinstance(users, dict), "load_users() should return a dict"
print(f"OK — auth: {len(users)} user(s) loaded")

# 5. Utility functions
from dashboard_app.utils import clean_text, content_hash, normalize_text, extract_tagged_json
assert clean_text("  hello\nworld  ") == "hello world"
assert len(content_hash("test")) == 12
assert normalize_text("Šarić") == "saric"
assert extract_tagged_json("__TAG__", "__TAG__{}") == {}
assert extract_tagged_json("__TAG__", "no tag here") is None
print("OK — utils functions work correctly")

# 6. Health endpoint via test client
with app.test_client() as client:
    resp = client.get("/health")
    assert resp.status_code == 200, f"/health returned {resp.status_code}"
    data = resp.get_json()
    assert data.get("status") == "ok", f"Unexpected health payload: {data}"
    print(f"OK — /health returned status=ok, article_count={data.get('article_count')}")

# 7. Login page renders
with app.test_client() as client:
    resp = client.get("/login")
    assert resp.status_code == 200, f"/login returned {resp.status_code}"
    assert b"login" in resp.data.lower(), "/login response doesn't look like a login page"
    print("OK — /login page renders (200)")

# 8. Protected routes redirect to login
with app.test_client() as client:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 301), f"Expected redirect from /, got {resp.status_code}"
    assert "login" in (resp.headers.get("Location") or "").lower()
    print("OK — / redirects unauthenticated requests to /login")

print("\n✅ All checks passed — dashboard_app is working correctly.")
