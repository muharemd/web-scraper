import os
import subprocess
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, session

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..services.ai import rewrite_single_title

ai_bp = Blueprint("ai_routes", __name__)


@ai_bp.route("/rewrite-title/<filename>", methods=["POST"])
@login_required
def rewrite_title_single(filename):
    client_ip = get_client_ip()
    username = session.get("username", "Unknown")
    log_activity(client_ip, username, "REWRITE_SINGLE_TITLE", f"File: {filename}")
    result = rewrite_single_title(filename)
    if result["success"]:
        return jsonify({
            "status": "success",
            "message": "Title rewritten successfully",
            "original": result["original"],
            "rewritten": result["rewritten"],
        })
    return jsonify({"status": "error", "message": result["error"]}), 400


@ai_bp.route("/run-rewrite-titles", methods=["POST"])
@login_required
def run_rewrite_titles():
    try:
        result = subprocess.run(
            ["/bin/bash", os.path.join(config.BASE_DIR, "rewrite_titles_deepseek.sh")],
            capture_output=True, text=True, timeout=120, cwd=config.BASE_DIR,
        )
        output = result.stdout + "\n" + result.stderr
        status = "success" if result.returncode == 0 else "error"
    except Exception as e:
        output = str(e)
        status = "error"
    return render_template(
        "scraper_output.html",
        output=output,
        status=status,
        now=datetime.now(),
        username=session.get("username", "Unknown"),
        client_ip=get_client_ip(),
    )
