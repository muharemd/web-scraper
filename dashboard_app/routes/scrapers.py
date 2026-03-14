import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, render_template, request, session

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..utils import (clean_text, content_hash, extract_tagged_json,
                     load_custom_state, normalize_text, save_custom_state)
from ..services.scraping import (extract_article_links, extract_title_content,
                                  is_low_quality_article, matches_filter,
                                  next_output_filename)

scrapers_bp = Blueprint("scrapers", __name__)


@scrapers_bp.route("/run-scrapers")
@login_required
def run_scrapers():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_activity(client_ip, username, "SCRAPERS_RUN_ATTEMPT")
    try:
        result = subprocess.run(
            [os.path.join(config.BASE_DIR, "run_all_scrapers.sh")],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            log_activity(client_ip, username, "SCRAPERS_RUN_SUCCESS",
                         f"Output length: {len(result.stdout)} chars")
        else:
            log_activity(client_ip, username, "SCRAPERS_RUN_FAILED",
                         f"Exit code: {result.returncode}")
        return render_template("scraper_output.html",
                               stdout=result.stdout,
                               stderr=result.stderr,
                               returncode=result.returncode)
    except Exception as e:
        log_activity(client_ip, username, "SCRAPERS_RUN_ERROR", f"Exception: {e}")
        return f"Error: {e}"


@scrapers_bp.route("/api/custom-scrape", methods=["POST"])
@login_required
def custom_scrape():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    payload = request.get_json(silent=True) or {}
    target_url = clean_text(payload.get("url", ""))
    filter_text = clean_text(payload.get("filter", ""))

    if not target_url:
        return jsonify({"status": "error", "message": "URL is required"}), 400
    if not target_url.startswith(("http://", "https://")):
        return jsonify({"status": "error",
                        "message": "URL must start with http:// or https://"}), 400

    filter_terms = [normalize_text(t) for t in re.split(r"[,\n]+", filter_text) if clean_text(t)]
    source_domain = urlparse(target_url).netloc.replace("www.", "")
    source_name = f"Custom {source_domain}" if source_domain else "Custom Source"
    source_hash = hashlib.md5(
        f"custom:{target_url}:{'|'.join(filter_terms)}".encode()
    ).hexdigest()[:12]
    state_key = hashlib.md5(f"{target_url}|{'|'.join(filter_terms)}".encode()).hexdigest()

    state = load_custom_state()
    entry = state.get(state_key, {"scraped_urls": [], "content_hashes": []})
    scraped_urls = set(entry.get("scraped_urls", []))
    content_hashes = set(entry.get("content_hashes", []))

    log_activity(client_ip, username, "CUSTOM_SCRAPE_ATTEMPT",
                 f"URL: {target_url} | Filter: {filter_text}")

    session_http = requests.Session()
    session_http.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })

    try:
        listing_resp = session_http.get(target_url, timeout=25)
        listing_resp.raise_for_status()
        links = extract_article_links(target_url, listing_resp.text) or [target_url]

        created_files = []
        for link in links[:20]:
            if link in scraped_urls:
                continue
            try:
                art_resp = session_http.get(link, timeout=25)
                art_resp.raise_for_status()
            except Exception:
                continue
            article = extract_title_content(link, art_resp.text)
            if is_low_quality_article(article) or not matches_filter(article, filter_terms):
                scraped_urls.add(link)
                continue
            body = (
                f"{article['content'][:900]}\n\n"
                f"📰 Izvor: {source_name}\n"
                f"🔗 Pročitaj više: {article['url']}"
            )
            c_hash = content_hash(body)
            if c_hash in content_hashes:
                scraped_urls.add(link)
                continue

            output = {
                "title": article["title"],
                "id": hashlib.md5(article["url"].encode()).hexdigest()[:8],
                "content": body,
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

            fname = next_output_filename(source_hash)
            with open(os.path.join(config.JSON_DIR, fname), "w", encoding="utf-8") as fh:
                json.dump(output, fh, ensure_ascii=False, indent=2)

            scraped_urls.add(link)
            content_hashes.add(c_hash)
            created_files.append(fname)

        state[state_key] = {
            "target_url": target_url,
            "filter": filter_text,
            "scraped_urls": list(scraped_urls),
            "content_hashes": list(content_hashes),
            "last_run": datetime.now().isoformat(),
        }
        save_custom_state(state)
        log_activity(client_ip, username, "CUSTOM_SCRAPE_SUCCESS",
                     f"Created: {len(created_files)}")
        return jsonify({
            "status": "success",
            "message": f"Custom scrape finished. Created {len(created_files)} JSON files.",
            "created_count": len(created_files),
            "created_files": created_files,
        })
    except Exception as exc:
        log_activity(client_ip, username, "CUSTOM_SCRAPE_FAILED", str(exc))
        return jsonify({"status": "error", "message": str(exc)}), 500


@scrapers_bp.route("/api/custom-scrape-reset", methods=["POST"])
@login_required
def custom_scrape_reset():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    try:
        if os.path.exists(config.CUSTOM_SCRAPE_STATE_FILE):
            os.remove(config.CUSTOM_SCRAPE_STATE_FILE)
        log_activity(client_ip, username, "CUSTOM_SCRAPE_STATE_RESET", "State file cleared")
        return jsonify({"status": "success",
                        "message": "Custom scrape state reset successfully."})
    except Exception as exc:
        log_activity(client_ip, username, "CUSTOM_SCRAPE_STATE_RESET_FAILED", str(exc))
        return jsonify({"status": "error", "message": str(exc)}), 500


@scrapers_bp.route("/api/run-apify-scrape", methods=["POST"])
@login_required
def run_apify_scrape():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_activity(client_ip, username, "APIFY_SCRAPE_ATTEMPT")

    if not os.path.exists(config.APIFY_SCRAPE_SCRIPT):
        msg = f"Apify scrape script not found: {config.APIFY_SCRAPE_SCRIPT}"
        log_activity(client_ip, username, "APIFY_SCRAPE_FAILED", msg)
        return jsonify({"status": "error", "message": msg}), 500

    try:
        result = subprocess.run(
            ["/bin/bash", config.APIFY_SCRAPE_SCRIPT],
            capture_output=True, text=True, timeout=900, cwd=config.BASE_DIR,
        )
    except Exception as exc:
        log_activity(client_ip, username, "APIFY_SCRAPE_FAILED", str(exc))
        return jsonify({"status": "error", "message": str(exc)}), 500

    parsed = extract_tagged_json(config.APIFY_RESULT_PREFIX, result.stdout)
    combined = (result.stdout or "").strip()
    if result.stderr:
        combined = f"{combined}\n{result.stderr}".strip()

    if result.returncode != 0:
        log_activity(client_ip, username, "APIFY_SCRAPE_FAILED",
                     f"Exit code: {result.returncode}")
        return jsonify({
            "status": "error",
            "message": "Apify scrape failed. Check output for details.",
            "output": combined[-5000:],
            "returncode": result.returncode,
        }), 500

    created_count = int((parsed or {}).get("created_count", 0))
    created_files = (parsed or {}).get("created_files", [])
    log_activity(client_ip, username, "APIFY_SCRAPE_SUCCESS", f"Created: {created_count}")
    return jsonify({
        "status": "success",
        "message": f"Apify scrape finished. Created {created_count} JSON files.",
        "created_count": created_count,
        "created_files": created_files,
        "output": combined[-5000:],
    })
