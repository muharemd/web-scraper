#!/usr/bin/env python3

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import feedparser

OUTPUT_DIR = "facebook_ready_posts"
MAX_CONTENT_LEN = 900

BIHAC_STRONG_TERMS = {
    "bihać", "bihac", "bihaću", "bihacu",
    "grad bihać", "grad bihac", "općina bihać", "opcina bihac",
    "unsko-sanski", "unskosanski", "una-sana",
    "sanski most", "cazin", "bužim", "buzim", "velika kladuša", "kladusa",
}


def _clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_text(text):
    text = text.lower()
    text = text.replace("ć", "c").replace("č", "c").replace("š", "s").replace("ž", "z").replace("đ", "dj")
    return re.sub(r"\s+", " ", text).strip()


def _is_bihac_related(title, summary="", categories=None):
    full = f"{title} {summary}"
    if categories:
        full += " " + " ".join(categories)
    normalized = _normalize_text(full)
    padded = f" {normalized} "
    for term in BIHAC_STRONG_TERMS:
        normalized_term = _normalize_text(term)
        if f" {normalized_term} " in padded:
            return True
    return False


def _generate_content_hash(content):
    normalized = " ".join(content.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _load_state(state_file):
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            return set(data.get("scraped_urls", [])), set(data.get("content_hashes", []))
    return set(), set()


def _save_state(state_file, scraped_urls, content_hashes):
    state = {
        "scraped_urls": list(scraped_urls),
        "content_hashes": list(content_hashes),
        "last_run": datetime.now().isoformat(),
        "script_name": os.path.basename(sys.argv[0]),
    }
    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)


def _entry_date(entry):
    if getattr(entry, "published_parsed", None):
        dt = datetime(*entry.published_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    if getattr(entry, "updated_parsed", None):
        dt = datetime(*entry.updated_parsed[:6])
        return dt.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def _entry_image(entry):
    def _image_from_article_page(article_url):
        if not article_url:
            return None
        try:
            import requests

            resp = requests.get(
                article_url,
                timeout=12,
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            )
            resp.raise_for_status()
            html = resp.text
        except Exception:
            return None

        meta_patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pattern in meta_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip().replace("\\/", "/")
                if candidate:
                    return urljoin(article_url, candidate)

        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if img_match:
            candidate = img_match.group(1).strip().replace("\\/", "/")
            if candidate:
                return urljoin(article_url, candidate)

        return None

    candidates = []

    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("url"):
                candidates.append(media["url"])
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enclosure in entry.enclosures:
            if enclosure.get("href"):
                candidates.append(enclosure["href"])
    if hasattr(entry, "description"):
        match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
        if match:
            candidates.append(match.group(1))

    article_url = getattr(entry, "link", "")
    from_page = _image_from_article_page(article_url)
    if from_page:
        return from_page

    for candidate in candidates:
        candidate = candidate.replace("\\/", "/")
        if "static.klix.ba/media/images/vijesti/img32_" in candidate:
            return candidate.replace("/img32_", "/b_")
        if candidate:
            return candidate

    return None


def run_rss_source(feed_url, source_name, state_file):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    script_hash = hashlib.md5(os.path.basename(sys.argv[0]).encode()).hexdigest()[:12]
    scraped_urls, content_hashes = _load_state(state_file)

    print("=" * 60)
    print(f"📰 {source_name} RSS SCRAPER")
    print("=" * 60)
    print(f"Feed URL: {feed_url}")

    feed = feedparser.parse(feed_url)
    entries = feed.entries or []
    print(f"Fetched entries: {len(entries)}")

    new_saved = 0
    sequence = 1
    date_part = datetime.now().strftime("%Y%m%d")

    for entry in entries:
        title = _clean_text(getattr(entry, "title", ""))
        url = getattr(entry, "link", "")
        summary = _clean_text(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        categories = [tag.get("term", "") for tag in getattr(entry, "tags", []) if isinstance(tag, dict)]

        if not url or url in scraped_urls:
            continue
        if not _is_bihac_related(title, summary, categories):
            continue

        body = summary if summary else title
        body = body[:MAX_CONTENT_LEN] + ("..." if len(body) > MAX_CONTENT_LEN else "")
        content = f"{body}\n\n📰 Izvor: {source_name}\n🔗 Pročitaj više: {url}"
        content_hash = _generate_content_hash(content)
        if content_hash in content_hashes:
            scraped_urls.add(url)
            continue

        payload = {
            "title": title or "Bez naslova",
            "id": hashlib.md5(url.encode()).hexdigest()[:8],
            "content": content,
            "url": url,
            "scheduled_publish_time": None,
            "published": "",
            "source": script_hash,
            "source_name": source_name,
            "content_hash": content_hash,
            "scraped_at": datetime.now().isoformat(),
            "date": _entry_date(entry),
        }

        image_url = _entry_image(entry)
        if image_url:
            payload["image_url"] = image_url

        filename = f"{script_hash}-{date_part}-{sequence:03d}.json"
        sequence += 1
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

        scraped_urls.add(url)
        content_hashes.add(content_hash)
        new_saved += 1
        print(f"  💾 Saved: {filename} | {title[:70]}")

    _save_state(state_file, scraped_urls, content_hashes)
    print(f"✅ Finished. New Bihać-related posts saved: {new_saved}")
