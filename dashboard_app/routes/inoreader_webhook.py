import hashlib
import hmac
import ipaddress
import json
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from flask import Blueprint, abort, jsonify, request

from .. import config
from ..logging_utils import get_client_ip, log_activity
from ..services.scraping import next_output_filename
from ..utils import clean_text, content_hash

webhook_bp = Blueprint("inoreader_webhook", __name__)


def _clean_multiline_text(value):
    if value is None:
        return ""

    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    collapsed = []
    previous_blank = False
    for line in lines:
        if not line:
            if collapsed and not previous_blank:
                collapsed.append("")
            previous_blank = True
            continue
        collapsed.append(line)
        previous_blank = False

    while collapsed and not collapsed[0]:
        collapsed.pop(0)
    while collapsed and not collapsed[-1]:
        collapsed.pop()

    return "\n".join(collapsed)


def _first_non_empty(payload, keys):
    if not isinstance(payload, dict):
        return ""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            cleaned = clean_text(value)
            if cleaned:
                return cleaned
    return ""


def _first_non_empty_multiline(payload, keys):
    if not isinstance(payload, dict):
        return ""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            cleaned = _clean_multiline_text(value)
            if cleaned:
                return cleaned
        elif isinstance(value, dict):
            nested = _first_non_empty_multiline(value, ["text", "value", "content", "html"])
            if nested:
                return nested
    return ""


def _normalize_http_url(value):
    url = clean_text(value)
    if url.startswith(("http://", "https://")):
        return url
    return ""


def _extract_article_url(payload):
    if not isinstance(payload, dict):
        return ""

    direct = _first_non_empty(payload, ["url", "link", "canonical_url", "article_url", "source_url"])
    url = _normalize_http_url(direct)
    if url:
        return url

    links = payload.get("links")
    if isinstance(links, list):
        for entry in links:
            if isinstance(entry, str):
                url = _normalize_http_url(entry)
                if url:
                    return url
            elif isinstance(entry, dict):
                url = _normalize_http_url(entry.get("href") or entry.get("url") or "")
                if url:
                    return url

    return ""


def _extract_image_url(payload):
    if not isinstance(payload, dict):
        return ""

    for key in ["image_url", "imageUrl", "thumbnail", "thumbnail_url", "image", "cover"]:
        value = payload.get(key)
        if isinstance(value, str):
            url = _normalize_http_url(value)
            if url:
                return url
        elif isinstance(value, dict):
            url = _normalize_http_url(
                value.get("url")
                or value.get("src")
                or value.get("href")
                or value.get("uri")
                or ""
            )
            if url:
                return url

    enclosures = payload.get("enclosures")
    if isinstance(enclosures, list):
        for entry in enclosures:
            if isinstance(entry, str):
                url = _normalize_http_url(entry)
                if url:
                    return url
            elif isinstance(entry, dict):
                url = _normalize_http_url(entry.get("url") or entry.get("href") or "")
                if url:
                    return url

    media = payload.get("media")
    if isinstance(media, list):
        for entry in media:
            if isinstance(entry, dict):
                url = _normalize_http_url(entry.get("url") or entry.get("src") or "")
                if url:
                    return url

    return ""


def _extract_source_name(item, envelope, article_url):
    for payload in (item, envelope):
        if not isinstance(payload, dict):
            continue

        source_name = _first_non_empty(
            payload,
            ["source_name", "source", "feed_title", "feedName", "publisher", "site_name"],
        )
        if source_name:
            return source_name

        feed = payload.get("feed")
        if isinstance(feed, dict):
            feed_name = _first_non_empty(feed, ["title", "name"])
            if feed_name:
                return feed_name

    domain = urlparse(article_url).netloc.lower().replace("www.", "")
    if domain:
        return domain
    return config.INOREADER_WEBHOOK_SOURCE_NAME


def _extract_article_date(item, envelope):
    candidates = []
    for payload in (item, envelope):
        if not isinstance(payload, dict):
            continue
        for key in ["date", "published", "published_at", "pubDate", "time", "timestamp", "updated"]:
            if key in payload:
                candidates.append(payload.get(key))

    for value in candidates:
        dt = _parse_datetime(value)
        if dt:
            return dt.strftime("%Y-%m-%d")

    return datetime.now().strftime("%Y-%m-%d")


def _parse_datetime(value):
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 10_000_000_000:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts)
        except Exception:
            return None

    if not isinstance(value, str):
        return None

    text = clean_text(value)
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%Y-%m-%d")
        except ValueError:
            pass

    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%d.%m.%Y")
        except ValueError:
            pass

    try:
        return parsedate_to_datetime(text)
    except Exception:
        return None


def _paragraph_metrics(text):
    paragraphs = [line.strip() for line in text.split("\n") if line.strip()]
    if not paragraphs and text.strip():
        return 1, len(text.strip())
    return len(paragraphs), sum(len(line) for line in paragraphs)


def _extract_items(payload):
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "articles", "entries", "data", "item", "article", "entry", "payload", "event"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested_items = _extract_items(value)
                if nested_items:
                    return nested_items
        return [payload]

    return []


def _load_payload(raw_body):
    payload = request.get_json(silent=True)
    if payload is not None:
        return payload, "request_json"

    if raw_body:
        body_text = raw_body.decode("utf-8", errors="replace").strip()
        if body_text:
            try:
                return json.loads(body_text), "raw_body_json"
            except Exception:
                pass

    if request.form:
        for key in ("payload", "data", "body", "json", "event", "item", "items"):
            value = request.form.get(key, "")
            if not value:
                continue
            try:
                return json.loads(value), f"form_field:{key}"
            except Exception:
                continue

    return None, "none"


def _payload_shape(payload):
    if isinstance(payload, dict):
        keys = list(payload.keys())[:10]
        return f"type=dict keys={keys}"
    if isinstance(payload, list):
        return f"type=list len={len(payload)}"
    return f"type={type(payload).__name__}"


def _source_hash(source_name, article_url):
    domain = urlparse(article_url).netloc.lower().replace("www.", "")
    seed = f"inoreader:{source_name}:{domain}"
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]


def _find_existing_article(article_url, article_content_hash):
    if not os.path.exists(config.JSON_DIR):
        return ""

    try:
        entries = list(os.scandir(config.JSON_DIR))
    except Exception:
        return ""

    for entry in entries:
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        try:
            with open(entry.path, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
        except Exception:
            continue

        existing_url = clean_text(existing.get("url", ""))
        if article_url and existing_url and article_url == existing_url:
            return entry.name

        existing_hash = clean_text(existing.get("content_hash", ""))
        if article_content_hash and existing_hash and article_content_hash == existing_hash:
            return entry.name

    return ""


def _build_article_payload(item, envelope):
    article_url = _extract_article_url(item)
    if not article_url:
        article_url = _extract_article_url(envelope)
    if not article_url:
        return None

    title = _first_non_empty(item, ["title", "headline", "name"])
    content_main = _first_non_empty_multiline(
        item,
        ["content", "content_text", "summary", "description", "body", "text", "excerpt"],
    )
    if not content_main:
        content_main = title
    if not content_main:
        return None

    if not title:
        title = clean_text(content_main.split("\n", 1)[0])
    if not title:
        title = "Inoreader Article"

    source_name = _extract_source_name(item, envelope, article_url)

    body = content_main
    source_line = f"Izvor: {source_name}"
    if source_line not in body:
        body = f"{body}\n\n{source_line}" if body else source_line

    if article_url not in body:
        link_line = f"Procitaj vise: {article_url}"
        body = f"{body}\n{link_line}" if body else link_line

    paragraph_count, paragraph_total_length = _paragraph_metrics(content_main)
    now_dt = datetime.now()
    payload = {
        "title": title,
        "title_rewritten": "",
        "id": hashlib.md5(article_url.encode("utf-8")).hexdigest()[:8],
        "content": body,
        "url": article_url,
        "scheduled_publish_time": None,
        "published": "",
        "published_target": "",
        "source": _source_hash(source_name, article_url),
        "source_name": source_name,
        "content_hash": content_hash(body),
        "content_full_length": len(body),
        "content_post_length": len(body),
        "content_truncated_for_facebook": False,
        "content_extraction_method": "inoreader_webhook",
        "content_coverage_label": "inoreader",
        "content_coverage_ratio": 1.0,
        "page_paragraph_count": paragraph_count,
        "page_paragraph_total_length": paragraph_total_length,
        "scraped_at": now_dt.isoformat(),
        "date": _extract_article_date(item, envelope),
        "wp_published": "",
        "wp_url": "",
        "wp_post_id": "",
        "wp_category": "",
    }

    image_url = _extract_image_url(item)
    if image_url:
        payload["image_url"] = image_url

    return payload


def _parse_allowed_ip_rules(raw_values):
    rules = []
    for value in raw_values:
        try:
            if "/" in value:
                rules.append(ipaddress.ip_network(value, strict=False))
            else:
                rules.append(ipaddress.ip_address(value))
        except ValueError:
            print(f"WARNING: Ignoring invalid INOREADER_WEBHOOK_ALLOWED_IPS entry: {value}")
    return rules


ALLOWED_IP_RULES = _parse_allowed_ip_rules(config.INOREADER_WEBHOOK_ALLOWED_IPS)


def _is_ip_allowed(client_ip):
    if not ALLOWED_IP_RULES:
        return True

    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for rule in ALLOWED_IP_RULES:
        if isinstance(rule, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if ip_obj in rule:
                return True
        elif ip_obj == rule:
            return True
    return False


@webhook_bp.route("/inoreader-webhook", methods=["GET", "HEAD", "POST"])
def handle_inoreader_webhook():
    client_ip = get_client_ip()

    if request.method in {"GET", "HEAD"}:
        if not config.INOREADER_WEBHOOK_TOKEN:
            log_activity(
                client_ip,
                "inoreader-webhook",
                "INOREADER_WEBHOOK_REJECTED",
                "INOREADER_WEBHOOK_TOKEN is not configured",
            )
            return jsonify({"status": "error", "message": "Webhook token is not configured."}), 503

        token = clean_text(request.args.get("token", ""))
        if not token or not hmac.compare_digest(token, config.INOREADER_WEBHOOK_TOKEN):
            log_activity(client_ip, "inoreader-webhook", "INOREADER_WEBHOOK_FORBIDDEN", "Invalid token")
            abort(403)

        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_PROBE_OK",
            f"Method={request.method}",
        )
        return jsonify({"status": "ok", "message": "Webhook endpoint reachable."}), 200

    if not config.INOREADER_WEBHOOK_TOKEN:
        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_REJECTED",
            "INOREADER_WEBHOOK_TOKEN is not configured",
        )
        return jsonify({"status": "error", "message": "Webhook token is not configured."}), 503

    token = clean_text(request.args.get("token", ""))
    if not token or not hmac.compare_digest(token, config.INOREADER_WEBHOOK_TOKEN):
        log_activity(client_ip, "inoreader-webhook", "INOREADER_WEBHOOK_FORBIDDEN", "Invalid token")
        abort(403)

    content_length = request.content_length or 0
    if content_length > config.INOREADER_WEBHOOK_MAX_BYTES:
        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_REJECTED",
            f"Payload too large: {content_length} bytes",
        )
        abort(413)

    raw_body = request.get_data(cache=True)
    if len(raw_body) > config.INOREADER_WEBHOOK_MAX_BYTES:
        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_REJECTED",
            f"Payload too large after read: {len(raw_body)} bytes",
        )
        abort(413)

    payload, payload_source = _load_payload(raw_body)
    if payload is None:
        content_type = clean_text(request.content_type or "") or "unknown"
        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_REJECTED",
            f"Request body must be valid JSON (content_type={content_type}, bytes={len(raw_body)})",
        )
        return jsonify({"status": "error", "message": "Request body must be valid JSON."}), 400

    items = _extract_items(payload)
    if not items:
        log_activity(
            client_ip,
            "inoreader-webhook",
            "INOREADER_WEBHOOK_REJECTED",
            f"No article items found in payload ({_payload_shape(payload)})",
        )
        return jsonify({"status": "error", "message": "No article items found in payload."}), 400

    os.makedirs(config.JSON_DIR, exist_ok=True)

    created_files = []
    skipped_count = 0
    skipped_missing_required = 0
    skipped_duplicates = 0

    envelope = payload if isinstance(payload, dict) else {}

    for item in items:
        article_payload = _build_article_payload(item, envelope)
        if not article_payload:
            skipped_count += 1
            skipped_missing_required += 1
            continue

        existing_name = _find_existing_article(
            article_payload.get("url", ""),
            article_payload.get("content_hash", ""),
        )
        if existing_name:
            skipped_count += 1
            skipped_duplicates += 1
            continue

        filename = next_output_filename(article_payload["source"])
        output_path = os.path.join(config.JSON_DIR, filename)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(article_payload, handle, ensure_ascii=False, indent=2)
        created_files.append(filename)

    log_activity(
        client_ip,
        "inoreader-webhook",
        "INOREADER_WEBHOOK_IMPORTED",
        (
            f"Processed={len(items)} Created={len(created_files)} Skipped={skipped_count} "
            f"MissingRequired={skipped_missing_required} Duplicates={skipped_duplicates} "
            f"PayloadSource={payload_source}"
        ),
    )

    return jsonify(
        {
            "status": "success",
            "processed_count": len(items),
            "created_count": len(created_files),
            "created_files": created_files,
            "skipped_count": skipped_count,
        }
    )


if config.INOREADER_WEBHOOK_PATH != "/inoreader-webhook":
    webhook_bp.add_url_rule(
        config.INOREADER_WEBHOOK_PATH,
        view_func=handle_inoreader_webhook,
        methods=["GET", "HEAD", "POST"],
    )