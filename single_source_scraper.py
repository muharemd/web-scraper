#!/usr/bin/env python3

import hashlib
import json
import os
import re
import sys
import time
import warnings
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

OUTPUT_DIR = "facebook_ready_posts"
MAX_ARTICLES = 12
MAX_CONTENT_LEN = 900

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


def _clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()


def _generate_content_hash(content):
    if not content:
        return ""
    normalized = " ".join(content.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _load_state(state_file):
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            scraped_urls = set(data.get("scraped_urls", []))
            content_hashes = set(data.get("content_hashes", []))
            # Backward compatible with old state files that do not have URL-level hashes.
            raw_url_content_hashes = data.get("url_content_hashes", {})
            if not isinstance(raw_url_content_hashes, dict):
                raw_url_content_hashes = {}
            url_content_hashes = {
                str(url): str(content_hash)
                for url, content_hash in raw_url_content_hashes.items()
                if url and content_hash
            }
            return scraped_urls, content_hashes, url_content_hashes
    return set(), set(), {}


def _save_state(state_file, scraped_urls, content_hashes, url_content_hashes):
    state = {
        "scraped_urls": list(scraped_urls),
        "content_hashes": list(content_hashes),
        "url_content_hashes": url_content_hashes,
        "last_run": datetime.now().isoformat(),
        "script_name": os.path.basename(sys.argv[0]),
    }
    with open(state_file, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, ensure_ascii=False)


def _normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _is_article_candidate(link_url, listing_url):
    lowered = link_url.lower()
    if "najnovije-vijesti" in lowered:
        return False
    if any(token in lowered for token in ["/rss", "/feed", ".xml", "rss="]):
        return False
    if any(lowered.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip", ".doc", ".docx", ".mp4"]):
        return False
    if any(token in lowered for token in ["/kontakt", "/contact", "/about", "/author", "/login", "/wp-admin", "/cdn-cgi/"]):
        return False
    if _normalize_url(link_url) == _normalize_url(listing_url):
        return False

    path = urlparse(link_url).path.lower()
    if len(path.strip("/")) < 6:
        return False

    positive_tokens = [
        "vijest", "vijesti", "novost", "novosti", "clanak", "article", "tema", "tag", "kategorija", "category",
        "politika", "sport", "kultura", "magazin", "bihac", "usk", "grad-bihac"
    ]
    if any(token in lowered for token in positive_tokens):
        return True

    return path.count("/") >= 2


def _is_low_quality_article(article):
    title = _clean_text(article.get("title", "")).lower()
    content = _clean_text(article.get("content", ""))

    blocked_titles = {
        "haber.ba",
        "vijesti",
        "novosti",
        "naslovna",
        "home",
        "početna",
        "pocetna",
    }

    if title in blocked_titles:
        return True
    if title.startswith("najnovije vijesti"):
        return True
    if "haber.ba" in title:
        return True
    if len(title) < 8:
        return True
    if len(content) < 80:
        return True
    return False


def _is_region_related(article, region_terms):
    if not region_terms:
        return True

    searchable = _clean_text(
        f"{article.get('title', '')} {article.get('content', '')} {article.get('url', '')}"
    ).lower()
    searchable = searchable.replace("ć", "c").replace("č", "c").replace("š", "s").replace("ž", "z").replace("đ", "dj")
    padded = f" {searchable} "

    for term in region_terms:
        normalized_term = _clean_text(term).lower()
        normalized_term = normalized_term.replace("ć", "c").replace("č", "c").replace("š", "s").replace("ž", "z").replace("đ", "dj")
        if f" {normalized_term} " in padded:
            return True

    return False


def _fetch_html(url, session):
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        return response.text
    except Exception as exc:
        print(f"  ❌ Fetch failed: {url} | {exc}")
        return None


def _extract_listing_links(listing_url, session):
    html = _fetch_html(listing_url, session)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    links = []
    selectors = [
        "article a[href]",
        "h1 a[href], h2 a[href], h3 a[href]",
        ".post a[href], .news a[href], .entry a[href], .item a[href]",
        "a[href]",
    ]
    base_domain = urlparse(listing_url).netloc.lower().replace("www.", "")

    for selector in selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            full_url = urljoin(listing_url, href)
            full_domain = urlparse(full_url).netloc.lower().replace("www.", "")

            if full_domain != base_domain and base_domain not in full_domain and full_domain not in base_domain:
                continue
            if not _is_article_candidate(full_url, listing_url):
                continue

            if full_url not in links:
                links.append(full_url)
            if len(links) >= MAX_ARTICLES:
                return links

    return links[:MAX_ARTICLES]


def _extract_title(soup):
    selectors = ["h1", "meta[property='og:title']", "meta[name='twitter:title']", "title"]
    for selector in selectors:
        if selector.startswith("meta"):
            elem = soup.select_one(selector)
            if elem and elem.get("content"):
                value = _clean_text(elem.get("content"))
                if len(value) >= 5:
                    return value
        else:
            elem = soup.select_one(selector)
            if elem:
                value = _clean_text(elem.get_text(" "))
                if len(value) >= 5:
                    return value
    return "Bez naslova"


def _is_generic_title(title):
    normalized = _clean_text(title).lower()
    normalized = normalized.replace("ć", "c").replace("č", "c").replace("š", "s").replace("ž", "z").replace("đ", "dj")
    generic_markers = [
        "bez naslova",
        "home",
        "naslovna",
        "ju sluzba za zaposljavanje",
        "sluzba za zaposljavanje",
    ]
    if len(normalized) < 8:
        return True
    return any(marker in normalized for marker in generic_markers)


def _derive_title_from_content(content):
    text = _clean_text(content)
    if not text:
        return None

    colon_match = re.match(r"^(.{8,140}?)\s*:\s", text)
    if colon_match:
        candidate = _clean_text(colon_match.group(1))
        if len(candidate) >= 8:
            return candidate

    sentence_match = re.match(r"^(.{8,160}?)(?:[\.!\?]|$)", text)
    if sentence_match:
        candidate = _clean_text(sentence_match.group(1))
        if len(candidate) >= 8:
            return candidate

    words = text.split()
    if len(words) >= 3:
        return " ".join(words[:14])

    return None


def _extract_content(soup):
    selectors = ["article", ".entry-content", ".post-content", ".article-content", ".news-content", "main", "#content", ".content"]
    for selector in selectors:
        elem = soup.select_one(selector)
        if not elem:
            continue
        for trash in elem.select("script, style, iframe, nav, footer, header, aside, .entry-meta, .post-meta, .author, .byline, .meta, .entry-footer, .post-footer, .comment, .comments, .share, .social-share"):
            trash.decompose()
        text = _clean_text(elem.get_text(" "))
        if len(text) >= 140:
            return text

    paragraphs = []
    for paragraph in soup.select("p")[:25]:
        txt = _clean_text(paragraph.get_text(" "))
        if len(txt) >= 40:
            paragraphs.append(txt)
    joined = _clean_text(" ".join(paragraphs))
    if joined:
        return joined

    meta_desc = soup.select_one("meta[name='description']")
    if meta_desc and meta_desc.get("content"):
        return _clean_text(meta_desc.get("content"))

    return ""


def _extract_date(soup):
    today = datetime.now().strftime("%Y-%m-%d")
    for selector in ["meta[property='article:published_time']", "meta[name='pubdate']", "meta[name='date']"]:
        elem = soup.select_one(selector)
        if elem and elem.get("content"):
            match = re.search(r"\d{4}-\d{2}-\d{2}", elem.get("content"))
            if match:
                return match.group(0)

    text = soup.get_text(" ")
    for pattern in [r"(\d{2})\.(\d{2})\.(\d{4})", r"(\d{4})-(\d{2})-(\d{2})"]:
        match = re.search(pattern, text)
        if not match:
            continue
        groups = match.groups()
        if len(groups[0]) == 4:
            return f"{groups[0]}-{groups[1]}-{groups[2]}"
        return f"{groups[2]}-{groups[1]}-{groups[0]}"

    return today


def _extract_image(soup, page_url):
    def is_valid_image(url):
        if not url:
            return False

        lowered = url.lower()

        blocked_patterns = [
            "facebook.com/tr",
            "google-analytics.com",
            "googletagmanager.com",
            "doubleclick.net",
            "/pixel",
            "/track",
            "utm_",
            "noscript=1",
            "spacer.gif",
            "blank.gif",
            "logo",
        ]
        if any(pattern in lowered for pattern in blocked_patterns):
            return False

        if any(lowered.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]):
            return True

        good_markers = [
            "/wp-content/uploads/",
            "/uploads/",
            "/images/",
            "image",
        ]
        return any(marker in lowered for marker in good_markers)

    candidate_selectors = [
        "meta[property='og:image']",
        "meta[property='og:image:url']",
        "meta[name='twitter:image']",
        "meta[name='twitter:image:src']",
    ]

    for selector in candidate_selectors:
        meta_img = soup.select_one(selector)
        if meta_img and meta_img.get("content"):
            candidate = urljoin(page_url, meta_img.get("content"))
            if is_valid_image(candidate):
                return candidate

    for selector in ["article img[src]", "main img[src]", ".content img[src]", "img[src]"]:
        for img in soup.select(selector):
            src = img.get("src")
            if not src:
                continue
            candidate = urljoin(page_url, src)
            if is_valid_image(candidate):
                return candidate

    return None


def _extract_article(url, source_name, session):
    html = _fetch_html(url, session)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    content = _extract_content(soup) or title

    if _is_generic_title(title):
        better_title = _derive_title_from_content(content)
        if better_title and not _is_generic_title(better_title):
            title = better_title

    return {
        "title": title,
        "content": content,
        "url": url,
        "date": _extract_date(soup),
        "image_url": _extract_image(soup, url),
        "source_name": source_name,
    }


def _next_filename(script_hash):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_part = datetime.now().strftime("%Y%m%d")
    prefix = f"{script_hash}-{date_part}-"
    existing = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.startswith(prefix) and filename.endswith(".json"):
            try:
                existing.append(int(filename.replace(prefix, "").replace(".json", "")))
            except Exception:
                continue
    next_number = max(existing) + 1 if existing else 1
    return f"{script_hash}-{date_part}-{next_number:03d}.json"


def run_single_source(target_url, source_name, state_file, region_terms=None):
    script_name = os.path.basename(sys.argv[0])
    script_hash = hashlib.md5(script_name.encode()).hexdigest()[:12]
    scraped_urls, content_hashes, url_content_hashes = _load_state(state_file)
    new_saved = 0
    updated_saved = 0

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 60)
    print(f"🗂️  {source_name} SCRAPER")
    print("=" * 60)
    print(f"Source URL: {target_url}")

    links = _extract_listing_links(target_url, session)
    if not links:
        print("  ⚠️ No listing links found, using source page as fallback")
        links = [target_url]

    for link in links:
        seen_before = link in scraped_urls

        article = _extract_article(link, source_name, session)
        if not article:
            continue
        if not _is_region_related(article, region_terms):
            scraped_urls.add(link)
            print(f"  ⏭️ Skipping non-region item: {article.get('title', '')[:70]}")
            continue
        if _is_low_quality_article(article):
            scraped_urls.add(link)
            print(f"  ⏭️ Skipping low-quality item: {article.get('title', '')[:70]}")
            continue

        fb_content = f"{article['content'][:MAX_CONTENT_LEN]}\n\n📰 Izvor: {source_name}\n🔗 Pročitaj više: {article['url']}"
        content_hash = _generate_content_hash(fb_content)
        previous_hash = url_content_hashes.get(link)

        if seen_before and previous_hash == content_hash:
            continue

        if content_hash in content_hashes and previous_hash != content_hash:
            scraped_urls.add(link)
            url_content_hashes[link] = content_hash
            continue

        payload = {
            "title": article["title"],
            "id": hashlib.md5(article["url"].encode()).hexdigest()[:8],
            "content": fb_content,
            "url": article["url"],
            "scheduled_publish_time": None,
            "published": "",
            "source": script_hash,
            "source_name": source_name,
            "content_hash": content_hash,
            "scraped_at": datetime.now().isoformat(),
            "date": article["date"],
        }
        if article.get("image_url"):
            payload["image_url"] = article["image_url"]

        filename = _next_filename(script_hash)
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

        scraped_urls.add(link)
        content_hashes.add(content_hash)
        url_content_hashes[link] = content_hash

        if seen_before:
            updated_saved += 1
            print(f"  ♻️ Updated: {filename} | {article['title'][:70]}")
        else:
            new_saved += 1
            print(f"  💾 Saved: {filename} | {article['title'][:70]}")
        time.sleep(0.2)

    _save_state(state_file, scraped_urls, content_hashes, url_content_hashes)
    print(f"✅ Finished. New posts saved: {new_saved} | Updated posts saved: {updated_saved}")
