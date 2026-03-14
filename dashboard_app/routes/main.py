import json
import os
import socket
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..services.articles import get_articles

main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    count = (
        len([f for f in os.listdir(config.JSON_DIR) if f.endswith(".json")])
        if os.path.exists(config.JSON_DIR)
        else 0
    )
    return jsonify({
        "status": "ok",
        "service": "facebook-posting-dashboard",
        "time": datetime.now().isoformat(),
        "article_count": count,
        "authenticated": session.get("logged_in", False),
    })


@main_bp.route("/")
@login_required
def index():
    try:
        per_page = 50
        try:
            page = max(1, int(request.args.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        offset = (page - 1) * per_page
        articles = get_articles(offset=offset, limit=per_page)

        total = new_count = published_count = 0
        if os.path.exists(config.JSON_DIR):
            for fname in os.listdir(config.JSON_DIR):
                if not fname.endswith(".json"):
                    continue
                total += 1
                try:
                    with open(os.path.join(config.JSON_DIR, fname), "r", encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("published"):
                        published_count += 1
                    else:
                        new_count += 1
                except Exception:
                    pass

        try:
            server_ip = socket.gethostbyname(socket.gethostname())
            if server_ip.startswith("127."):
                server_ip = request.host.split(":")[0]
        except Exception:
            server_ip = request.host.split(":")[0]

        posts = []
        for a in articles:
            preview = a.get("content_preview", "")
            posts.append({
                "filename": a.get("filename", ""),
                "title": a.get("title", "Nema naslova"),
                "title_rewritten": a.get("title_rewritten", ""),
                "summary": (preview[:120] + "...") if len(preview) > 120 else preview,
                "image_url": a.get("image_url", ""),
                "source": a.get("source_name", "Unknown"),
                "time": a.get("date", "Unknown"),
                "url": a.get("url", "#"),
                "published": a.get("published", ""),
                "published_target": a.get("published_target", ""),
                "wp_published": a.get("wp_published", ""),
                "wp_url": a.get("wp_url", ""),
                "wp_post_id": a.get("wp_post_id", ""),
                "wp_category": a.get("wp_category", ""),
            })

        from ..config import WP_CATEGORY_OPTIONS, load_wp_default_category
        total_pages = max(1, (total + per_page - 1) // per_page)
        return render_template(
            "dashboard.html",
            posts=posts,
            total=total,
            new_count=new_count,
            published_count=published_count,
            server_ip=server_ip,
            port=8080,
            now=datetime.now(),
            wp_categories=WP_CATEGORY_OPTIONS,
            wp_default_category=load_wp_default_category(),
            page=page,
            total_pages=total_pages,
            per_page=per_page,
        )
    except Exception as e:
        print(f"ERROR in index: {e}")
        traceback.print_exc()
        return render_template(
            "error.html",
            error_type="error",
            title="Dashboard Error",
            message="An error occurred while loading the dashboard.",
            error=str(e),
        ), 500


@main_bp.route("/list")
@login_required
def list_articles():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_activity(client_ip, username, "VIEWED_LIST")
    return render_template("list.html", articles=get_articles(limit=None))


@main_bp.route("/view-logs")
@login_required
def view_logs():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_activity(client_ip, username, "VIEWED_LOGS")

    def _read(path, fallback):
        try:
            with open(path, "r") as f:
                return f.read()[-10000:]
        except Exception:
            return fallback

    return render_template(
        "logs.html",
        access_log=_read(config.ACCESS_LOG, "No access log found"),
        activity_log=_read(config.ACTIVITY_LOG, "No activity log found"),
        failed_logins=_read(config.FAILED_LOGIN_LOG, "No failed login log found"),
    )


@main_bp.route("/refresh")
@login_required
def refresh():
    return redirect(url_for("main.index"))


@main_bp.route("/facebook")
@login_required
def facebook_tools():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")
    log_activity(client_ip, username, "VIEWED_FACEBOOK_TOOLS")
    try:
        try:
            server_ip = socket.gethostbyname(socket.gethostname())
            if server_ip.startswith("127."):
                server_ip = request.host.split(":")[0]
        except Exception:
            server_ip = request.host.split(":")[0]
        return render_template(
            "facebook.html",
            server_ip=server_ip,
            port=8080,
            now=datetime.now(),
            username=username,
        )
    except Exception as exc:
        return render_template(
            "error.html",
            error_type="error",
            title="Facebook Tools Error",
            message="An error occurred while loading the Facebook tools page.",
            error=str(exc),
        ), 500
