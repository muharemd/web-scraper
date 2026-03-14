import hashlib
import json
import os
import subprocess
from datetime import datetime

from .. import config
from ..utils import clean_text


def _normalize_page_url(url):
    return clean_text(url).rstrip("/").lower()


def _stable_page_id(name, url, source_file):
    seed = f"{source_file}|{clean_text(name)}|{_normalize_page_url(url)}"
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
            name = clean_text(page.get("name", ""))
            url = clean_text(page.get("url", ""))
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


def _merge_fb_pages(preconfigured, manual):
    merged = {}
    for page in preconfigured:
        key = _normalize_page_url(page.get("url", ""))
        if key:
            merged[key] = page
    for page in manual:
        key = _normalize_page_url(page.get("url", ""))
        if key:
            merged[key] = page
    return list(merged.values())


def load_fb_pages_config():
    manual = _load_pages_from_file(config.FB_PAGES_FILE, "manual")
    preconfigured = _load_pages_from_file(config.FB_PAGES_PRECONFIGURED_FILE, "preconfigured")
    return {
        "pages": _merge_fb_pages(preconfigured, manual),
        "manual_pages": manual,
        "preconfigured_pages": preconfigured,
        "updated_at": datetime.now().isoformat(),
    }


def save_fb_pages_config(payload):
    cleaned = []
    for page in payload.get("pages", []):
        if not isinstance(page, dict):
            continue
        name = clean_text(page.get("name", ""))
        url = clean_text(page.get("url", ""))
        if not name or not url:
            continue
        if page.get("source_file") == "preconfigured":
            continue
        cleaned.append({
            "id": page.get("id") or _stable_page_id(name, url, "manual"),
            "name": name,
            "url": url,
            "enabled": bool(page.get("enabled", True)),
            "created_at": page.get("created_at") or datetime.now().isoformat(),
        })
    data = {"pages": cleaned, "updated_at": datetime.now().isoformat()}
    with open(config.FB_PAGES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return data


def is_valid_http_url(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def get_fb_pages():
    return load_fb_pages_config().get("pages", [])


def get_webhook_for_target(target):
    if target == "bihac_danas":
        return config.WEBHOOK_URL
    if target == "konkursi":
        return config.WEBHOOK_URL_KONKURSI
    return None


def run_curl_command_for_target(json_file_path, target="bihac_danas"):
    webhook_url = get_webhook_for_target(target)
    if not webhook_url:
        return {"success": False, "error": f"Unknown or unconfigured target: {target}"}
    try:
        cmd = [
            "curl", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", f"@{json_file_path}",
            webhook_url,
            "--max-time", "30",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        return {"success": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_curl_command(json_file_path):
    return run_curl_command_for_target(json_file_path, "bihac_danas")
