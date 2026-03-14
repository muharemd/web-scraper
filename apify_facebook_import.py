#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

BASE_DIR = "/home/bihac-danas/web-scraper"
OUTPUT_DIR = os.path.join(BASE_DIR, "facebook_ready_posts")
STATE_FILE = os.path.join(BASE_DIR, "apify_facebook_state.json")
PAGES_FILE = os.path.join(BASE_DIR, ".fb_pages.json")
PAGES_PRECONFIGURED_FILE = os.path.join(BASE_DIR, ".fb_pages_preconfigured.json")
RESULT_PREFIX = "__APIFY_RESULT__"
DEFAULT_ACTOR_ID = "apify~facebook-posts-scraper"
ATTACHMENTS_DIR = os.path.join(OUTPUT_DIR, "attachments")
MEDIA_REQUEST_TIMEOUT = (10, 60)
MEDIA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def _clean_text(value):
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


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


def _content_hash(text):
    normalized = " ".join(_clean_text(text).lower().split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]


def _trim_title(text, max_length=160):
    cleaned = _clean_text(text)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _normalize_page_url(url):
    return _clean_text(url).rstrip("/").lower()


def _load_pages_file(path):
    payload = _load_json(path, {"pages": []})
    pages = payload.get("pages", []) if isinstance(payload, dict) else []
    return pages if isinstance(pages, list) else []


def _load_combined_pages():
    preconfigured_pages = _load_pages_file(PAGES_PRECONFIGURED_FILE)
    manual_pages = _load_pages_file(PAGES_FILE)

    merged_by_url = {}

    for page in preconfigured_pages:
        if not isinstance(page, dict):
            continue
        key = _normalize_page_url(page.get("url", ""))
        if key:
            merged_by_url[key] = page

    # Manual pages override same URLs from preconfigured file.
    for page in manual_pages:
        if not isinstance(page, dict):
            continue
        key = _normalize_page_url(page.get("url", ""))
        if key:
            merged_by_url[key] = page

    return {
        "pages": list(merged_by_url.values()),
        "manual_count": len([p for p in manual_pages if isinstance(p, dict)]),
        "preconfigured_count": len([p for p in preconfigured_pages if isinstance(p, dict)]),
    }


def _bool_from_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_positive_int(name, value):
    try:
        parsed = int(str(value).strip())
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than 0")
    return parsed


def _positive_int_from_env(name, default_value):
    value = os.environ.get(name, str(default_value)).strip() or str(default_value)
    return _parse_positive_int(name, value)


def _dataset_fetch_limit(input_payload, per_page_limit):
    fetch_limit = os.environ.get("APIFY_FETCH_LIMIT", "").strip()
    if fetch_limit:
        return _parse_positive_int("APIFY_FETCH_LIMIT", fetch_limit)

    url_field = os.environ.get("APIFY_URL_FIELD", "startUrls").strip() or "startUrls"
    source_values = input_payload.get(url_field, [])
    source_count = len(source_values) if isinstance(source_values, list) else 0
    if source_count <= 0:
        return per_page_limit
    return source_count * per_page_limit


def _first_non_empty(payload, keys):
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and _clean_text(value):
            return _clean_text(value)
    return ""


def _first_non_empty_multiline(payload, keys):
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            cleaned = _clean_multiline_text(value)
            if cleaned:
                return cleaned
    return ""


def _extract_date(item):
    candidates = [
        item.get("date"),
        item.get("createdAt"),
        item.get("timestamp"),
        item.get("publishedAt"),
        item.get("time"),
    ]

    for value in candidates:
        text = _clean_text(value)
        if not text:
            continue

        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if match:
            return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    return datetime.now().strftime("%Y-%m-%d")


def _looks_like_image_url(url):
    value = _clean_text(url).lower()
    if not value:
        return False
    if any(ext in value for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]):
        return True
    if "fbcdn.net" in value or "scontent." in value:
        return True
    return False


def _dedupe_preserve_order(values):
    seen = set()
    deduped = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _image_candidates_from_payload(payload):
    if not isinstance(payload, dict):
        return []

    candidates = []

    for nested_key in ["photo_image", "image"]:
        nested_value = payload.get(nested_key)
        if isinstance(nested_value, dict):
            for nested_field in ["uri", "url", "src"]:
                candidate = _clean_text(nested_value.get(nested_field, ""))
                if _looks_like_image_url(candidate):
                    candidates.append(candidate)

    for key in ["imageUrl", "displayUrl", "photo", "image", "src", "url"]:
        value = payload.get(key)
        if isinstance(value, str) and _looks_like_image_url(value):
            candidates.append(_clean_text(value))

    if candidates:
        return _dedupe_preserve_order(candidates)

    for key in ["thumbnailUrl", "thumbnail"]:
        value = payload.get(key)
        if isinstance(value, str) and _looks_like_image_url(value):
            candidates.append(_clean_text(value))

    return _dedupe_preserve_order(candidates)


def _extract_image_urls(item):
    candidates = []
    candidates.extend(_image_candidates_from_payload(item))

    for key in ["images", "attachments", "media", "photos"]:
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    candidates.extend(_image_candidates_from_payload(entry))
                elif isinstance(entry, str) and _looks_like_image_url(entry):
                    candidates.append(_clean_text(entry))
        elif isinstance(value, dict):
            candidates.extend(_image_candidates_from_payload(value))

    return _dedupe_preserve_order(candidates)


def _extract_image_url(item):
    image_urls = _extract_image_urls(item)
    if image_urls:
        return image_urls[0]

    if isinstance(item.get("user"), dict):
        profile_pic = _clean_text(item.get("user", {}).get("profilePic", ""))
        if _looks_like_image_url(profile_pic):
            return profile_pic

    return ""


def _safe_path_component(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", _clean_text(value))
    cleaned = cleaned.strip("._")
    return cleaned[:120] if cleaned else fallback


def _image_extension_from_response(url, response):
    path = urlparse(url).path or ""
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return ext

    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    by_type = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    return by_type.get(content_type, ".jpg")


MEDIA_MAX_BYTES = 20 * 1024 * 1024  # 20 MB per image

def _download_image_attachments(source_hash, item_id, image_urls, session):
    if not image_urls:
        return "", [], []

    safe_item_id = _safe_path_component(item_id, "facebook-post")
    target_dir = os.path.join(ATTACHMENTS_DIR, source_hash, safe_item_id)
    os.makedirs(target_dir, exist_ok=True)

    for existing_name in os.listdir(target_dir):
        existing_path = os.path.join(target_dir, existing_name)
        if os.path.isfile(existing_path):
            os.remove(existing_path)

    saved_files = []
    errors = []
    for index, image_url in enumerate(image_urls, start=1):
        file_path = ""
        try:
            with session.get(image_url, timeout=MEDIA_REQUEST_TIMEOUT, stream=True) as response:
                response.raise_for_status()
                extension = _image_extension_from_response(image_url, response)
                filename = f"{index:02d}{extension}"
                file_path = os.path.join(target_dir, filename)
                bytes_written = 0
                with open(file_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            bytes_written += len(chunk)
                            if bytes_written > MEDIA_MAX_BYTES:
                                raise ValueError(f"Image exceeds {MEDIA_MAX_BYTES // (1024 * 1024)} MB limit")
                            handle.write(chunk)
                saved_files.append(filename)
        except Exception as exc:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            errors.append(f"{image_url} | {exc}")

    if not saved_files:
        try:
            os.rmdir(target_dir)
        except OSError:
            pass
        return "", [], errors

    return target_dir, saved_files, errors


def _extract_url(item):
    return _first_non_empty(
        item,
        [
            "url",
            "postUrl",
            "post_url",
            "facebookUrl",
            "link",
            "permalink",
        ],
    )


def _extract_source_name(item, url, page_lookup):
    source_name = _first_non_empty(
        item,
        [
            "pageName",
            "ownerName",
            "profileName",
            "authorName",
            "sourceName",
        ],
    )

    if source_name and source_name.lower() not in {"people", "facebook"}:
        return source_name

    candidate_urls = [
        _first_non_empty(item, ["inputUrl", "facebookUrl", "pageUrl", "page_url"]),
        url,
    ]

    for candidate_url in candidate_urls:
        normalized_url = (candidate_url or "").rstrip("/").lower()
        if not normalized_url:
            continue

        if normalized_url in page_lookup:
            return page_lookup[normalized_url]["name"]

        for page_url, page_data in page_lookup.items():
            if normalized_url.startswith(page_url):
                return page_data["name"]

    normalized_url = (url or "").rstrip("/").lower()
    if normalized_url and normalized_url in page_lookup:
        return page_lookup[normalized_url]["name"]

    for page_url, page_data in page_lookup.items():
        if normalized_url.startswith(page_url):
            return page_data["name"]

    parsed = urlparse(url or "")
    if parsed.path.strip("/"):
        return parsed.path.strip("/").split("/")[0]
    if parsed.netloc:
        return parsed.netloc.replace("www.", "")
    return "Facebook"


def _next_output_filename(source_hash):
    date_part = datetime.now().strftime("%Y%m%d")
    prefix = f"{source_hash}-{date_part}-"
    next_num = 1

    for name in os.listdir(OUTPUT_DIR):
        if not (name.startswith(prefix) and name.endswith(".json")):
            continue
        parts = name.split("-")
        if not parts:
            continue
        try:
            existing_num = int(parts[-1].split(".")[0])
            if existing_num >= next_num:
                next_num = existing_num + 1
        except Exception:
            continue

    return f"{source_hash}-{date_part}-{next_num:03d}.json"


def _build_apify_input(enabled_pages):
    static_input = {}
    static_input_file = os.environ.get("APIFY_STATIC_INPUT_FILE", "").strip()
    if static_input_file:
        static_input = _load_json(static_input_file, {})
        if not isinstance(static_input, dict):
            raise RuntimeError("APIFY_STATIC_INPUT_FILE must contain a JSON object")

    url_field = os.environ.get("APIFY_URL_FIELD", "startUrls").strip() or "startUrls"
    urls_as_objects = _bool_from_env("APIFY_URL_OBJECTS", default=True)
    page_urls = [page["url"] for page in enabled_pages]

    if urls_as_objects:
        static_input[url_field] = [{"url": url} for url in page_urls]
    else:
        static_input[url_field] = page_urls

    if "includePosts" not in static_input:
        static_input["includePosts"] = _bool_from_env("APIFY_INCLUDE_POSTS", default=True)
    if "includeImages" not in static_input:
        static_input["includeImages"] = _bool_from_env("APIFY_INCLUDE_IMAGES", default=True)

    max_items = _positive_int_from_env("APIFY_MAX_ITEMS", 2)
    max_items_field = os.environ.get("APIFY_MAX_ITEMS_FIELD", "maxPosts").strip() or "maxPosts"
    if max_items_field:
        # Always enforce the configured limit to avoid expensive unrestricted runs.
        static_input[max_items_field] = max_items

    return static_input


def _run_apify(input_payload, per_page_limit):
    token = os.environ.get("APIFY_TOKEN", "").strip()
    actor_id = os.environ.get("APIFY_ACTOR_ID", "").strip() or DEFAULT_ACTOR_ID
    task_id = os.environ.get("APIFY_TASK_ID", "").strip()
    base_url = os.environ.get("APIFY_API_BASE", "https://api.apify.com/v2").strip().rstrip("/")
    wait_for_finish = int(os.environ.get("APIFY_WAIT_FOR_FINISH", "240"))
    poll_interval = int(os.environ.get("APIFY_POLL_INTERVAL", "5"))

    if not token:
        raise RuntimeError("APIFY_TOKEN is missing")

    if task_id:
        run_url = f"{base_url}/actor-tasks/{task_id}/runs"
    else:
        run_url = f"{base_url}/acts/{actor_id}/runs"

    apify_session = requests.Session()
    apify_session.headers.update({"Authorization": f"Bearer {token}"})

    run_response = apify_session.post(
        run_url,
        json=input_payload,
        timeout=120,
    )
    run_response.raise_for_status()

    run_payload = run_response.json().get("data") or {}
    run_id = run_payload.get("id")
    if not run_id:
        raise RuntimeError("Apify run did not return run ID")

    status = run_payload.get("status", "RUNNING")
    deadline = time.time() + max(wait_for_finish, 30)
    while status in {"RUNNING", "READY"}:
        if time.time() > deadline:
            raise RuntimeError(f"Apify run timed out after {wait_for_finish}s")
        time.sleep(max(poll_interval, 1))
        status_response = apify_session.get(
            f"{base_url}/actor-runs/{run_id}",
            timeout=60,
        )
        status_response.raise_for_status()
        run_payload = status_response.json().get("data") or {}
        status = run_payload.get("status", "UNKNOWN")

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify run failed with status: {status}")

    dataset_id = run_payload.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError("Apify run has no defaultDatasetId")

    item_params = {
        "clean": "true",
        "format": "json",
        "desc": "true",
    }

    item_params["limit"] = _dataset_fetch_limit(input_payload, per_page_limit)

    dataset_url = f"{base_url}/datasets/{dataset_id}/items"
    items_response = apify_session.get(dataset_url, params=item_params, timeout=180)
    items_response.raise_for_status()
    items = items_response.json()

    if not isinstance(items, list):
        raise RuntimeError("Unexpected Apify dataset response format")

    return {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "actor_id": actor_id,
        "items": items,
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pages_bundle = _load_combined_pages()
    pages = pages_bundle["pages"]
    enabled_pages = [
        {
            "id": page.get("id", ""),
            "name": _clean_text(page.get("name", "")),
            "url": _clean_text(page.get("url", "")).rstrip("/"),
        }
        for page in pages
        if isinstance(page, dict)
        and page.get("enabled", True)
        and _clean_text(page.get("name", ""))
        and _clean_text(page.get("url", "")).startswith(("http://", "https://"))
    ]

    if not enabled_pages:
        raise RuntimeError("No enabled Facebook pages in .fb_pages.json or .fb_pages_preconfigured.json")

    page_lookup = {page["url"].lower(): page for page in enabled_pages}
    per_page_limit = _positive_int_from_env("APIFY_MAX_ITEMS", 2)
    apify_input = _build_apify_input(enabled_pages)

    run_data = _run_apify(apify_input, per_page_limit)
    items = run_data["items"]

    state = _load_json(STATE_FILE, {"seen_urls": [], "seen_hashes": []})
    seen_urls = set(state.get("seen_urls", []))
    seen_hashes = set(state.get("seen_hashes", []))

    created_files = []
    skipped_count = 0
    download_session = requests.Session()
    download_session.headers.update(MEDIA_HEADERS)

    try:
        for item in items:
            if not isinstance(item, dict):
                skipped_count += 1
                continue

            url = _extract_url(item)
            title = _first_non_empty(item, ["title", "caption", "name"])
            content = _first_non_empty_multiline(item, ["message", "text", "content", "description", "title"])
            if not content and title:
                content = title

            if not title:
                first_line = ""
                for line in (content or "").splitlines():
                    if _clean_text(line):
                        first_line = line
                        break
                title = _trim_title(first_line or content or "Facebook objava")
            if not content:
                skipped_count += 1
                continue

            source_name = _extract_source_name(item, url, page_lookup)
            source_hash = hashlib.md5(f"apify:{source_name}".encode("utf-8")).hexdigest()[:12]

            publish_text = content
            if source_name:
                publish_text = f"{publish_text}\n\n📰 Izvor: {source_name}"
            if url:
                publish_text = f"{publish_text}\n🔗 Pročitaj više: {url}"

            c_hash = _content_hash(publish_text)
            if (url and url in seen_urls) or c_hash in seen_hashes:
                skipped_count += 1
                continue

            item_id = _first_non_empty(item, ["id", "postId", "post_id"])
            if not item_id:
                item_id = hashlib.md5((url or publish_text).encode("utf-8")).hexdigest()[:8]

            output = {
                "title": title,
                "id": item_id,
                "content": publish_text,
                "url": url,
                "scheduled_publish_time": None,
                "published": "",
                "source": source_hash,
                "source_name": source_name,
                "content_hash": c_hash,
                "scraped_at": datetime.now().isoformat(),
                "date": _extract_date(item),
                "raw_item": item,
                "apify_dataset_id": run_data["dataset_id"],
                "apify_run_id": run_data["run_id"],
                "apify_actor_id": run_data.get("actor_id", DEFAULT_ACTOR_ID),
            }

            image_urls = _extract_image_urls(item)
            if image_urls:
                output["image_urls"] = image_urls

            image_url = image_urls[0] if image_urls else _extract_image_url(item)
            if image_url:
                output["image_url"] = image_url

            attachments_folder, attachment_files, download_errors = _download_image_attachments(
                source_hash,
                item_id,
                image_urls,
                download_session,
            )
            if attachments_folder:
                output["attachments_folder"] = attachments_folder
                output["attachment_files"] = attachment_files
            if download_errors:
                output["attachment_download_errors"] = download_errors

            filename = _next_output_filename(source_hash)
            filepath = os.path.join(OUTPUT_DIR, filename)
            _save_json(filepath, output)

            if url:
                seen_urls.add(url)
            seen_hashes.add(c_hash)
            created_files.append(filename)
    finally:
        download_session.close()
        _save_json(
            STATE_FILE,
            {
                "seen_urls": sorted(seen_urls),
                "seen_hashes": sorted(seen_hashes),
                "last_run": datetime.now().isoformat(),
            },
        )

    result_payload = {
        "created_count": len(created_files),
        "created_files": created_files,
        "skipped_count": skipped_count,
        "dataset_id": run_data["dataset_id"],
        "run_id": run_data["run_id"],
        "actor_id": run_data.get("actor_id", DEFAULT_ACTOR_ID),
        "source_count": len(enabled_pages),
        "manual_source_count": pages_bundle["manual_count"],
        "preconfigured_source_count": pages_bundle["preconfigured_count"],
    }

    print(f"Apify run completed. Dataset: {run_data['dataset_id']}")
    print(f"Configured pages: manual={pages_bundle['manual_count']} preconfigured={pages_bundle['preconfigured_count']}")
    print(f"Enabled source pages: {len(enabled_pages)}")
    print(f"Created files: {len(created_files)}")
    print(f"Skipped items: {skipped_count}")
    print(f"{RESULT_PREFIX}{json.dumps(result_payload, ensure_ascii=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
