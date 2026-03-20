import json
import os
import hashlib
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..services.articles import get_articles
from ..services.facebook import run_curl_command, run_curl_command_for_target
from ..services.scraping import next_output_filename
from ..utils import clean_text, content_hash

articles_bp = Blueprint("articles", __name__)


def _paragraph_metrics(text):
    paragraphs = [line.strip() for line in text.split("\n") if line.strip()]
    if not paragraphs and text.strip():
        return 1, len(text.strip())
    return len(paragraphs), sum(len(line) for line in paragraphs)


@articles_bp.route("/manual-entry", methods=["GET", "POST"])
@login_required
def manual_entry():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")

    form_data = {
        "title": "",
        "url": "",
        "image_url": "",
        "content": "",
    }

    if request.method == "GET":
        log_activity(client_ip, username, "VIEW_MANUAL_ENTRY_PAGE")
        return render_template(
            "manual_entry.html",
            now=datetime.now(),
            form_data=form_data,
            error_message="",
            success_message="",
            created_filename="",
        )

    title = clean_text(request.form.get("title", ""))
    url = clean_text(request.form.get("url", ""))
    image_url = clean_text(request.form.get("image_url", ""))
    raw_content = (request.form.get("content", "") or "")
    normalized_content = raw_content.replace("\r\n", "\n").replace("\r", "\n").strip()

    form_data = {
        "title": title,
        "url": url,
        "image_url": image_url,
        "content": normalized_content,
    }

    if not title or not url or not normalized_content:
        return render_template(
            "manual_entry.html",
            now=datetime.now(),
            form_data=form_data,
            error_message="Title, URL and content are required.",
            success_message="",
            created_filename="",
        ), 400

    if not url.startswith(("http://", "https://")):
        return render_template(
            "manual_entry.html",
            now=datetime.now(),
            form_data=form_data,
            error_message="URL must start with http:// or https://",
            success_message="",
            created_filename="",
        ), 400

    if image_url and not image_url.startswith(("http://", "https://")):
        return render_template(
            "manual_entry.html",
            now=datetime.now(),
            form_data=form_data,
            error_message="Image URL must start with http:// or https://",
            success_message="",
            created_filename="",
        ), 400

    content_value = normalized_content
    if url not in content_value:
        content_value = f"{content_value}\n\n🔗 Pročitaj više: {url}"

    source_domain = urlparse(url).netloc.lower().replace("www.", "")
    source_name = f"Manual Entry ({source_domain})" if source_domain else "Manual Entry"
    source_hash = hashlib.md5(f"manual:{source_domain or 'unknown'}".encode("utf-8")).hexdigest()[:12]

    paragraph_count, paragraph_total_length = _paragraph_metrics(normalized_content)
    now_dt = datetime.now()
    article_payload = {
        "title": title,
        "id": hashlib.md5(url.encode("utf-8")).hexdigest()[:8],
        "content": content_value,
        "url": url,
        "scheduled_publish_time": None,
        "published": "",
        "source": source_hash,
        "source_name": source_name,
        "content_hash": content_hash(content_value),
        "content_full_length": len(content_value),
        "content_post_length": len(content_value),
        "content_truncated_for_facebook": False,
        "content_extraction_method": "manual_form",
        "content_coverage_label": "manual",
        "content_coverage_ratio": 1.0,
        "page_paragraph_count": paragraph_count,
        "page_paragraph_total_length": paragraph_total_length,
        "scraped_at": now_dt.isoformat(),
        "date": now_dt.strftime("%Y-%m-%d"),
        "image_url": image_url,
    }

    os.makedirs(config.JSON_DIR, exist_ok=True)
    created_filename = next_output_filename(source_hash)
    output_path = os.path.join(config.JSON_DIR, created_filename)

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(article_payload, handle, ensure_ascii=False, indent=2)

    log_activity(client_ip, username, "MANUAL_ENTRY_CREATED", f"File: {created_filename}")
    return render_template(
        "manual_entry.html",
        now=datetime.now(),
        form_data={"title": "", "url": "", "image_url": "", "content": ""},
        error_message="",
        success_message="Manual article JSON created successfully.",
        created_filename=created_filename,
    )


@articles_bp.route("/post/<filename>")
@login_required
def post_article(filename):
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    target = (request.args.get("target") or "bihac_danas").strip().lower()
    if target not in ("bihac_danas", "konkursi"):
        target = "bihac_danas"

    filename = os.path.basename(filename)
    filepath = os.path.join(config.JSON_DIR, filename)

    if not os.path.exists(filepath):
        log_activity(client_ip, username, "POST_FAILED", f"File not found: {filename}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": "File not found"}), 404
        return render_template(
            "error.html", error_type="error", title="File Not Found",
            message="The requested article file could not be found.",
            details={"File": filename},
        ), 404

    log_activity(client_ip, username, "POST_ATTEMPT", f"File: {filename}, Target: {target}")
    result = run_curl_command_for_target(filepath, target)

    if result.get("success"):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            data["published"] = datetime.now().isoformat()
            data["published_target"] = target
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"ERROR updating published status: {e}")
        log_activity(client_ip, username, "POST_SUCCESS", f"File: {filename}, Target: {target}")
        return redirect(url_for("main.index"))

    log_activity(client_ip, username, "POST_FAILED",
                 f"File: {filename}, Target: {target}, "
                 f"Error: {result.get('stderr', result.get('error', 'Unknown'))[:200]}")
    return render_template(
        "error.html", error_type="error", title="Failed to Post",
        message="An error occurred while posting the article.",
        details={"File": filename},
        error=result.get("stderr", result.get("error", "Unknown")),
    )


@articles_bp.route("/post-all-new")
@login_required
def post_all_new():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    articles = get_articles(limit=None)
    new_articles = [a for a in articles if a.get("is_new")]
    log_activity(client_ip, username, "BULK_POST_ATTEMPT",
                 f"Trying to post {len(new_articles)} articles")
    if not new_articles:
        log_activity(client_ip, username, "BULK_POST_FAILED", "No new articles found")
        return render_template("post_results.html", results=[], success_count=0)

    results = []
    for article in new_articles:
        filepath = os.path.join(config.JSON_DIR, article["filename"])
        result = run_curl_command(filepath)
        if result.get("success"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                data["published"] = datetime.now().isoformat()
                with open(filepath, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass
        results.append({
            "filename": article["filename"],
            "title": article["title"],
            "success": result.get("success", False),
            "error": result.get("stderr", "") if not result.get("success") else "",
        })

    success_count = sum(1 for r in results if r["success"])
    log_activity(client_ip, username, "BULK_POST_COMPLETE",
                 f"Success: {success_count}/{len(results)}")
    return render_template("post_results.html", results=results, success_count=success_count)


@articles_bp.route("/api/delete-multiple", methods=["POST"])
@login_required
def delete_multiple_articles():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    payload = request.get_json(silent=True) or {}
    filenames = payload.get("filenames", [])
    if not isinstance(filenames, list):
        return jsonify({"status": "error", "message": "filenames must be a list"}), 400

    deleted, errors = [], []
    for filename in filenames:
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            errors.append({"filename": filename, "error": "Invalid filename"})
            continue
        if not filename.endswith(".json"):
            errors.append({"filename": filename, "error": "Not a JSON file"})
            continue
        filepath = os.path.join(config.JSON_DIR, os.path.basename(filename))
        if not os.path.exists(filepath):
            errors.append({"filename": filename, "error": "File not found"})
            continue
        try:
            os.remove(filepath)
            deleted.append(filename)
        except Exception as exc:
            errors.append({"filename": filename, "error": str(exc)})

    log_activity(client_ip, username, "BULK_DELETE",
                 f"Deleted: {len(deleted)}, Errors: {len(errors)}")
    return jsonify({
        "status": "success",
        "deleted_count": len(deleted),
        "deleted": deleted,
        "errors": errors,
    })


@articles_bp.route("/delete/<filename>")
@login_required
def delete_article(filename):
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    filename = os.path.basename(filename)
    filepath = os.path.join(config.JSON_DIR, filename)

    if not os.path.exists(filepath):
        log_activity(client_ip, username, "DELETE_FAILED", f"File not found: {filename}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": "File not found"}), 404
        return render_template(
            "error.html", error_type="error", title="File Not Found",
            message="The requested article file could not be found.",
            details={"File": filename},
        ), 404

    try:
        os.remove(filepath)
        log_activity(client_ip, username, "DELETE_SUCCESS", f"File deleted: {filename}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "success", "message": "File deleted"})
        return redirect(url_for("main.index"))
    except Exception as e:
        log_activity(client_ip, username, "DELETE_FAILED",
                     f"File: {filename}, Error: {str(e)}")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"status": "error", "message": str(e)}), 500
        return render_template(
            "error.html", error_type="error", title="Delete Failed",
            message="An error occurred while deleting the article.",
            details={"File": filename}, error=str(e),
        )


@articles_bp.route("/get-article/<filename>")
@login_required
def get_article(filename):
    filename = os.path.basename(filename)
    filepath = os.path.join(config.JSON_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
