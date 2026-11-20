import hashlib
import json
import os
import subprocess
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, session

from ..auth import login_required
from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..services.ai import rewrite_single_title, rewrite_title_and_content_custom
from ..services.scraping import next_output_filename
from ..utils import clean_text, content_hash

ai_bp = Blueprint("ai_routes", __name__)


DEFAULT_AI_COMPOSE_PROMPT = (
    "Rewrite title and content in Bosnian/Croatian language. "
    "Keep all facts accurate. Make title concise and engaging. "
    "Make content clear, readable, and structured in short paragraphs."
)


def _normalize_multiline(value):
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _paragraph_metrics(text):
    paragraphs = [line.strip() for line in text.split("\n") if line.strip()]
    if not paragraphs and text.strip():
        return 1, len(text.strip())
    return len(paragraphs), sum(len(line) for line in paragraphs)


def _build_ai_compose_payload(title, content):
    title_text = clean_text(title)
    content_text = _normalize_multiline(content)
    fingerprint = hashlib.md5(f"{title_text}|{content_text}".encode("utf-8")).hexdigest()
    source_hash = hashlib.md5("manual:ai_compose".encode("utf-8")).hexdigest()[:12]

    paragraph_count, paragraph_total_length = _paragraph_metrics(content_text)
    now_dt = datetime.now()

    return {
        "title": title_text,
        "title_rewritten": title_text,
        "id": fingerprint[:8],
        "content": content_text,
        "url": "",
        "scheduled_publish_time": None,
        "published": "",
        "published_target": "",
        "source": source_hash,
        "source_name": "AI Compose",
        "content_hash": content_hash(content_text),
        "content_full_length": len(content_text),
        "content_post_length": len(content_text),
        "content_truncated_for_facebook": False,
        "content_extraction_method": "manual_ai_compose",
        "content_coverage_label": "manual_ai",
        "content_coverage_ratio": 1.0,
        "page_paragraph_count": paragraph_count,
        "page_paragraph_total_length": paragraph_total_length,
        "scraped_at": now_dt.isoformat(),
        "date": now_dt.strftime("%Y-%m-%d"),
        "image_url": "",
        "wp_published": "",
        "wp_url": "",
        "wp_post_id": "",
        "wp_category": "",
    }


@ai_bp.route("/ai-compose", methods=["GET", "POST"])
@login_required
def ai_compose_page():
    client_ip = get_client_ip()
    username = session.get("username", "UNKNOWN")

    form_data = {
        "title": "",
        "content": "",
        "prompt": DEFAULT_AI_COMPOSE_PROMPT,
    }

    error_message = ""
    success_message = ""
    created_filename = ""
    status_code = 200

    if request.method == "GET":
        log_activity(client_ip, username, "VIEW_AI_COMPOSE_PAGE")
        return render_template(
            "ai_compose.html",
            now=datetime.now(),
            form_data=form_data,
            error_message=error_message,
            success_message=success_message,
            created_filename=created_filename,
        )

    action = clean_text(request.form.get("action", "rewrite")).lower()
    title = clean_text(request.form.get("title", ""))
    content = _normalize_multiline(request.form.get("content", ""))
    prompt = _normalize_multiline(request.form.get("prompt", "")) or DEFAULT_AI_COMPOSE_PROMPT

    form_data = {
        "title": title,
        "content": content,
        "prompt": prompt,
    }

    if action == "rewrite":
        if not title or not content or not prompt:
            error_message = "Title, content and prompt are required for rewrite."
            status_code = 400
        else:
            log_activity(
                client_ip,
                username,
                "AI_COMPOSE_REWRITE_ATTEMPT",
                f"TitleLen={len(title)} ContentLen={len(content)} PromptLen={len(prompt)}",
            )
            result = rewrite_title_and_content_custom(title, content, prompt)
            if result.get("success"):
                form_data["title"] = result.get("rewritten_title", "")
                form_data["content"] = result.get("rewritten_content", "")
                changed_title = bool(result.get("changed_title"))
                changed_content = bool(result.get("changed_content"))
                if changed_title and changed_content:
                    success_message = "Title and content rewritten. Review, then click Save."
                elif changed_title:
                    success_message = "Title rewritten. Content stayed the same. Review, then click Save."
                elif changed_content:
                    success_message = "Content rewritten. Title stayed the same. Review, then click Save."
                else:
                    success_message = "Rewrite completed. Review and click Save if satisfied."
                log_activity(
                    client_ip,
                    username,
                    "AI_COMPOSE_REWRITE_SUCCESS",
                    (
                        f"TitleLen={len(form_data['title'])} ContentLen={len(form_data['content'])} "
                        f"ChangedTitle={changed_title} ChangedContent={changed_content}"
                    ),
                )
            else:
                error_message = result.get("error", "Rewrite failed")
                status_code = 400
                log_activity(
                    client_ip,
                    username,
                    "AI_COMPOSE_REWRITE_FAILED",
                    error_message[:240],
                )

    elif action == "save":
        if not title or not content:
            error_message = "Title and content are required to save the article."
            status_code = 400
        else:
            article_payload = _build_ai_compose_payload(title, content)
            os.makedirs(config.JSON_DIR, exist_ok=True)
            created_filename = next_output_filename(article_payload["source"])
            output_path = os.path.join(config.JSON_DIR, created_filename)
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(article_payload, handle, ensure_ascii=False, indent=2)

            success_message = "AI article saved to facebook_ready_posts successfully."
            log_activity(client_ip, username, "AI_COMPOSE_SAVED", f"File: {created_filename}")

            form_data = {
                "title": "",
                "content": "",
                "prompt": prompt,
            }

    else:
        error_message = "Unknown action."
        status_code = 400

    return render_template(
        "ai_compose.html",
        now=datetime.now(),
        form_data=form_data,
        error_message=error_message,
        success_message=success_message,
        created_filename=created_filename,
    ), status_code


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
