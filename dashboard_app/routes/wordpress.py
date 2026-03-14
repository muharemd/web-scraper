import json
import os
import subprocess
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..utils import clean_text, extract_tagged_json

wp_bp = Blueprint("wordpress", __name__)


@wp_bp.route("/publish-wp/<filename>", methods=["POST"])
@login_required
def publish_wordpress_article(filename):
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    filename = os.path.basename(filename)
    filepath = os.path.join(config.JSON_DIR, filename)

    payload = request.get_json(silent=True) if request.is_json else {}
    selected_cat = clean_text(request.form.get("wp_category", ""))
    if not selected_cat and isinstance(payload, dict):
        selected_cat = clean_text(str(payload.get("wp_category", "")))

    def _is_ajax():
        return request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json

    if selected_cat and not selected_cat.isdigit():
        if _is_ajax():
            return jsonify({"status": "error", "message": "WordPress category must be numeric."}), 400
        return render_template(
            "error.html", error_type="error", title="Invalid WordPress Category",
            message="WordPress category must be numeric.",
            details={"File": filename, "Category": selected_cat},
        ), 400

    if selected_cat and selected_cat not in config.WP_CATEGORY_IDS:
        if _is_ajax():
            return jsonify({"status": "error",
                            "message": "Selected category is not in the dashboard list."}), 400
        return render_template(
            "error.html", error_type="error", title="Invalid WordPress Category",
            message="Selected category is not in the dashboard list.",
            details={"File": filename, "Category": selected_cat},
        ), 400

    if not os.path.exists(filepath):
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", f"File not found: {filename}")
        if _is_ajax():
            return jsonify({"status": "error", "message": "File not found"}), 404
        return render_template(
            "error.html", error_type="error", title="File Not Found",
            message="The requested article file could not be found.",
            details={"File": filename},
        ), 404

    if not os.path.exists(config.WORDPRESS_PUBLISH_SCRIPT):
        msg = f"WordPress script not found: {config.WORDPRESS_PUBLISH_SCRIPT}"
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", msg)
        if _is_ajax():
            return jsonify({"status": "error", "message": msg}), 500
        return render_template(
            "error.html", error_type="error", title="WordPress Script Missing",
            message="WordPress publish script was not found.", error=msg,
        ), 500

    log_activity(client_ip, username, "WP_PUBLISH_ATTEMPT",
                 f"File: {filename}, Category: {selected_cat or 'default'}")
    command = ["/bin/bash", config.WORDPRESS_PUBLISH_SCRIPT, filepath]
    if selected_cat:
        command.append(selected_cat)

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300, cwd=config.BASE_DIR
        )
    except Exception as exc:
        log_activity(client_ip, username, "WP_PUBLISH_FAILED", str(exc))
        if _is_ajax():
            return jsonify({"status": "error", "message": str(exc)}), 500
        return render_template(
            "error.html", error_type="error", title="WordPress Publish Error",
            message="An exception occurred while publishing to WordPress.",
            details={"File": filename}, error=str(exc),
        ), 500

    combined = (result.stdout or "")
    if result.stderr:
        combined = f"{combined}\n{result.stderr}"
    parsed = extract_tagged_json(config.WP_RESULT_PREFIX, result.stdout)

    if result.returncode != 0:
        log_activity(client_ip, username, "WP_PUBLISH_FAILED",
                     f"File: {filename}, Exit code: {result.returncode}")
        if _is_ajax():
            return jsonify({
                "status": "error",
                "message": "WordPress publish failed.",
                "output": combined[-5000:],
                "returncode": result.returncode,
            }), 500
        return render_template(
            "error.html", error_type="error", title="WordPress Publish Failed",
            message="An error occurred while publishing the article to WordPress.",
            details={"File": filename}, error=combined[-5000:],
        ), 500

    # Persist metadata back to the JSON file
    try:
        with open(filepath, "r", encoding="utf-8") as h:
            data = json.load(h)
        data["wp_published"] = datetime.now().isoformat()
        if selected_cat:
            data["wp_category"] = int(selected_cat)
        if parsed:
            if parsed.get("post_id"):
                data["wp_post_id"] = str(parsed["post_id"])
            if parsed.get("link"):
                data["wp_url"] = parsed["link"]
        with open(filepath, "w", encoding="utf-8") as h:
            json.dump(data, h, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_activity(client_ip, username, "WP_PUBLISH_METADATA_FAILED", f"{filename}: {exc}")

    log_activity(client_ip, username, "WP_PUBLISH_SUCCESS",
                 f"File: {filename}, Category: {selected_cat or 'default'}")
    if _is_ajax():
        return jsonify({
            "status": "success",
            "message": "Published to WordPress.",
            "result": parsed or {},
            "wp_category": selected_cat or None,
            "output": combined[-2000:],
        })
    return redirect(url_for("main.index"))
