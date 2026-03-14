import os
import warnings

from bs4 import XMLParsedAsHTMLWarning

# ===== PATHS =====
BASE_DIR = "/home/bihac-danas/web-scraper"
JSON_DIR = os.path.join(BASE_DIR, "facebook_ready_posts")
FB_PAGES_FILE = os.path.join(BASE_DIR, ".fb_pages.json")
FB_PAGES_PRECONFIGURED_FILE = os.path.join(BASE_DIR, ".fb_pages_preconfigured.json")
APIFY_SCRAPE_SCRIPT = os.path.join(BASE_DIR, "run_apify_facebook_scrape.sh")
WORDPRESS_PUBLISH_SCRIPT = os.path.join(BASE_DIR, "post_to_wp.sh")
USERS_FILE = os.path.join(BASE_DIR, "dashboard_users.json")
CUSTOM_SCRAPE_STATE_FILE = os.path.join(BASE_DIR, "custom_dashboard_scrape_state.json")
ACCESS_LOG = os.path.join(BASE_DIR, "dashboard_access.log")
ACTIVITY_LOG = os.path.join(BASE_DIR, "dashboard_activity.log")
FAILED_LOGIN_LOG = os.path.join(BASE_DIR, "failed_logins.log")

# ===== PREFIXES =====
APIFY_RESULT_PREFIX = "__APIFY_RESULT__"
WP_RESULT_PREFIX = "__WP_RESULT__"

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ===== WORDPRESS CATEGORIES =====
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
    {"id": 1,  "name": "Uncategorized", "parent": 0},
    {"id": 45, "name": "Vatrogasci", "parent": 31},
    {"id": 29, "name": "Vijesti BiH i Regija", "parent": 0},
    {"id": 26, "name": "Vijesti Bihać", "parent": 0},
    {"id": 27, "name": "Vijesti USK", "parent": 0},
    {"id": 39, "name": "Vodovod", "parent": 31},
    {"id": 4,  "name": "World", "parent": 0},
    {"id": 37, "name": "Zdravstvo", "parent": 31},
]

WP_CATEGORY_IDS = {str(cat["id"]) for cat in WP_CATEGORIES}
_WP_CATEGORY_NAME_BY_ID = {cat["id"]: cat["name"] for cat in WP_CATEGORIES}
WP_CATEGORY_OPTIONS = []
for _cat in WP_CATEGORIES:
    _parent_id = _cat.get("parent", 0)
    _parent_name = _WP_CATEGORY_NAME_BY_ID.get(_parent_id, "") if _parent_id else ""
    _label = f"{_parent_name} / {_cat['name']}" if _parent_name else _cat["name"]
    WP_CATEGORY_OPTIONS.append({
        "id": str(_cat["id"]),
        "name": _cat["name"],
        "parent": _parent_id,
        "label": _label,
    })


def load_make_webhooks():
    config_file = os.path.join(BASE_DIR, ".make_tokens")
    webhooks = {"webhook_url": None, "webhook_url_konkursi": None}
    try:
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "WEBHOOK_URL=" in line:
                    value = line.split("WEBHOOK_URL=", 1)[1].strip().strip('"').strip("'")
                    if "KONKURSI" in line:
                        webhooks["webhook_url_konkursi"] = value
                    else:
                        webhooks["webhook_url"] = value
    except Exception as e:
        print(f"ERROR loading Make webhooks: {e}")
    return webhooks


def load_wp_default_category():
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
    return "36"


_make_webhooks = load_make_webhooks()
WEBHOOK_URL = _make_webhooks.get("webhook_url")
WEBHOOK_URL_KONKURSI = _make_webhooks.get("webhook_url_konkursi")
