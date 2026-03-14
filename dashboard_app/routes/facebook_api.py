import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from ..auth import login_required
from ..logging_utils import get_client_ip, log_activity
from ..services.facebook import (get_fb_pages, is_valid_http_url,
                                  load_fb_pages_config, save_fb_pages_config)
from ..utils import clean_text

fb_api_bp = Blueprint("facebook_api", __name__)


@fb_api_bp.route("/api/facebook-pages", methods=["GET"])
@login_required
def get_facebook_pages():
    return jsonify({"status": "success", "pages": get_fb_pages()})


@fb_api_bp.route("/api/facebook-pages", methods=["POST"])
@login_required
def add_facebook_page():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    payload = request.get_json(silent=True) or {}
    name = clean_text(payload.get("name", ""))
    url = clean_text(payload.get("url", ""))
    enabled = bool(payload.get("enabled", True))

    if not name:
        return jsonify({"status": "error", "message": "Page name is required"}), 400
    if not is_valid_http_url(url):
        return jsonify({"status": "error",
                        "message": "URL must start with http:// or https://"}), 400

    cfg = load_fb_pages_config()
    pages = cfg.get("pages", [])
    manual_pages = cfg.get("manual_pages", [])
    existing_urls = {clean_text(p.get("url", "")).rstrip("/").lower() for p in pages}
    if url.rstrip("/").lower() in existing_urls:
        return jsonify({"status": "error",
                        "message": "This page URL is already in the list"}), 409

    new_page = {
        "id": secrets.token_hex(8),
        "name": name,
        "url": url,
        "enabled": enabled,
        "created_at": datetime.now().isoformat(),
        "source_file": "manual",
    }
    manual_pages.append(new_page)
    save_fb_pages_config({"pages": manual_pages})
    log_activity(client_ip, username, "FB_PAGE_ADDED", f"{name} | {url}")
    return jsonify({"status": "success", "message": "Facebook page source added.",
                    "page": new_page})


@fb_api_bp.route("/api/facebook-pages/<page_id>/toggle", methods=["POST"])
@login_required
def toggle_facebook_page(page_id):
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    payload = request.get_json(silent=True) or {}
    cfg = load_fb_pages_config()
    target = next((p for p in cfg.get("pages", []) if p.get("id") == page_id), None)
    if not target:
        return jsonify({"status": "error", "message": "Page not found"}), 404
    if target.get("source_file") == "preconfigured":
        return jsonify({
            "status": "error",
            "message": "This is a preconfigured page. "
                       "Edit .fb_pages_preconfigured.json to change it.",
        }), 400

    manual_pages = cfg.get("manual_pages", [])
    manual_target = next((p for p in manual_pages if p.get("id") == page_id), None)
    if not manual_target:
        return jsonify({"status": "error", "message": "Manual page not found"}), 404

    manual_target["enabled"] = (
        bool(payload["enabled"]) if "enabled" in payload
        else not bool(manual_target.get("enabled", True))
    )
    save_fb_pages_config({"pages": manual_pages})
    log_activity(client_ip, username, "FB_PAGE_TOGGLED",
                 f"{manual_target.get('name', '')} -> {manual_target.get('enabled')}")
    return jsonify({"status": "success", "message": "Facebook page updated.",
                    "page": manual_target})


@fb_api_bp.route("/api/facebook-pages/<page_id>", methods=["DELETE"])
@login_required
def delete_facebook_page(page_id):
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    cfg = load_fb_pages_config()
    target = next((p for p in cfg.get("pages", []) if p.get("id") == page_id), None)
    if not target:
        return jsonify({"status": "error", "message": "Page not found"}), 404
    if target.get("source_file") == "preconfigured":
        return jsonify({
            "status": "error",
            "message": "This is a preconfigured page. "
                       "Edit .fb_pages_preconfigured.json to remove it.",
        }), 400

    manual_pages = [p for p in cfg.get("manual_pages", []) if p.get("id") != page_id]
    save_fb_pages_config({"pages": manual_pages})
    log_activity(client_ip, username, "FB_PAGE_DELETED", f"{target.get('name', '')}")
    return jsonify({"status": "success", "message": "Facebook page removed."})
