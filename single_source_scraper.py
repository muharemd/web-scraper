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
FALLBACK_PARAGRAPH_LIMIT = 25
FALLBACK_PARAGRAPH_MIN_LEN = 40

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
    normalized = f"{parsed.netloc.lower()}{parsed.path}".rstrip("/")
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


def _is_article_candidate(link_url, listing_url):
    lowered = link_url.lower()
    if "najnovije-vijesti" in lowered:
        return False
    if any(token in lowered for token in ["/rss", "/feed", ".xml", "rss="]):
        return False
    if any(token in lowered for token in ["page_id=", "attachment_id=", "paged=", "?m=", "&m="]):
        return False
    # Skip taxonomy/archive pagination links and keep post URLs only.
    if any(token in lowered for token in ["/category/", "/tag/", "/author/", "/page/"]):
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
        "vijest", "vijesti", "novost", "novosti", "clanak", "article", "tema",
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
        raw_bytes = response.content
        if not raw_bytes:
            return None

        encodings = []

        # Prefer charset from page metadata when available.
        meta_match = re.search(br"charset\s*=\s*['\"]?([a-zA-Z0-9._-]+)", raw_bytes[:8192], flags=re.IGNORECASE)
        if meta_match:
            try:
                meta_encoding = meta_match.group(1).decode("ascii", errors="ignore").strip()
                if meta_encoding:
                    encodings.append(meta_encoding)
            except Exception:
                pass

        apparent = (response.apparent_encoding or "").strip()
        if apparent:
            encodings.append(apparent)

        declared = (response.encoding or "").strip()
        # requests often defaults to ISO-8859-1 when charset is missing.
        if declared and declared.lower() not in {"iso-8859-1", "latin-1", "us-ascii", "ascii"}:
            encodings.append(declared)

        encodings.extend(["utf-8", "cp1250", "iso-8859-2", declared])

        tried = set()
        for encoding in encodings:
            if not encoding:
                continue
            key = encoding.lower()
            if key in tried:
                continue
            tried.add(key)
            try:
                return raw_bytes.decode(encoding)
            except Exception:
                continue

        return raw_bytes.decode("utf-8", errors="replace")
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
            if href.lower().startswith("www.") or re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(?:/.*)?$", href, flags=re.IGNORECASE):
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


def _collect_page_paragraph_stats(soup):
    paragraph_lengths = []
    for paragraph in soup.select("p"):
        text = _clean_text(paragraph.get_text(" "))
        if len(text) >= 20:
            paragraph_lengths.append(len(text))

    return {
        "paragraph_count": len(paragraph_lengths),
        "paragraph_total_length": sum(paragraph_lengths),
    }


def _estimate_content_coverage(content_length, paragraph_count, paragraph_total_length):
    if content_length <= 0:
        return None, "empty"

    # Very short pages (or pages without real paragraph tags) are hard to classify.
    if paragraph_count < 3 or paragraph_total_length < 180:
        return None, "unknown"

    ratio = min(1.0, content_length / float(paragraph_total_length))
    if ratio >= 0.75:
        label = "likely_full"
    elif ratio >= 0.45:
        label = "possibly_partial"
    else:
        label = "likely_partial"

    return round(ratio, 3), label


def _extract_content_with_meta(soup):
    page_stats = _collect_page_paragraph_stats(soup)

    def _build_meta(content_text, method):
        content_length = len(content_text)
        ratio, coverage_label = _estimate_content_coverage(
            content_length,
            page_stats["paragraph_count"],
            page_stats["paragraph_total_length"],
        )
        return {
            "content": content_text,
            "method": method,
            "content_length": content_length,
            "page_paragraph_count": page_stats["paragraph_count"],
            "page_paragraph_total_length": page_stats["paragraph_total_length"],
            "coverage_ratio": ratio,
            "coverage_label": coverage_label,
        }

    selectors = ["article", ".entry-content", ".post-content", ".article-content", ".news-content", "main", "#content", ".content"]
    for selector in selectors:
        elem = soup.select_one(selector)
        if not elem:
            continue
        for trash in elem.select("script, style, iframe, nav, footer, header, aside, .entry-meta, .post-meta, .author, .byline, .meta, .entry-footer, .post-footer, .comment, .comments, .share, .social-share"):
            trash.decompose()
        text = _clean_text(elem.get_text(" "))
        if len(text) >= 140:
            return _build_meta(text, f"selector:{selector}")

    paragraphs = []
    for paragraph in soup.select("p")[:FALLBACK_PARAGRAPH_LIMIT]:
        txt = _clean_text(paragraph.get_text(" "))
        if len(txt) >= FALLBACK_PARAGRAPH_MIN_LEN:
            paragraphs.append(txt)
    joined = _clean_text(" ".join(paragraphs))
    if joined:
        return _build_meta(joined, "paragraph_fallback")

    meta_desc = soup.select_one("meta[name='description']")
    if meta_desc and meta_desc.get("content"):
        return _build_meta(_clean_text(meta_desc.get("content")), "meta_description")

    return _build_meta("", "none")


def _extract_content(soup):
    return _extract_content_with_meta(soup)["content"]


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
    def _first_src_from_srcset(srcset_value):
        if not srcset_value:
            return None
        first = srcset_value.split(",", 1)[0].strip()
        if not first:
            return None
        return first.split(" ", 1)[0].strip() or None

    def _img_candidate_url(img_tag):
        for attr in ["data-src", "data-lazy-src", "data-original", "data-image", "src"]:
            value = img_tag.get(attr)
            if value:
                return value

        srcset_candidate = _first_src_from_srcset(img_tag.get("data-srcset") or img_tag.get("srcset"))
        if srcset_candidate:
            return srcset_candidate
        return None

    def _looks_like_logo_or_ad(candidate_url, img_tag=None):
        lowered = (candidate_url or "").lower()
        if any(token in lowered for token in ["logo", "banner", "advert", "gravatar", "avatar", "v10.png", "/ads/", "adservice"]):
            return True

        if img_tag is not None:
            meta_text = " ".join(img_tag.get("class", []))
            meta_text = f"{meta_text} {img_tag.get('alt', '')} {img_tag.get('title', '')}".lower()
            if any(token in meta_text for token in ["logo", "banner", "advert", "avatar"]):
                return True

        return False

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
            "gravatar.com/avatar",
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
        "link[rel='image_src']",
    ]

    for selector in candidate_selectors:
        meta_img = soup.select_one(selector)
        if not meta_img:
            continue
        raw_candidate = meta_img.get("content") or meta_img.get("href")
        if raw_candidate:
            candidate = urljoin(page_url, raw_candidate)
            if _looks_like_logo_or_ad(candidate):
                continue
            if is_valid_image(candidate):
                return candidate

    image_selectors = [
        "img.wp-post-image",
        ".post-thumbnail img",
        ".td-post-featured-image img",
        ".tdb_single_featured_image img",
        "article img",
        ".entry-content img",
        ".post-content img",
        ".td-post-content img",
        "main img",
        ".content img",
        "img",
    ]

    for selector in image_selectors:
        for img in soup.select(selector):
            src = _img_candidate_url(img)
            if not src:
                continue
            candidate = urljoin(page_url, src)
            if _looks_like_logo_or_ad(candidate, img):
                continue
            if is_valid_image(candidate):
                return candidate

    return None


def _extract_article(url, source_name, session):
    html = _fetch_html(url, session)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    content_meta = _extract_content_with_meta(soup)
    content = content_meta.get("content") or title

    if not content_meta.get("content"):
        content_meta["content"] = content
        content_meta["content_length"] = len(content)
        content_meta["method"] = "title_fallback"
        content_meta["coverage_ratio"] = None
        content_meta["coverage_label"] = "unknown"

    if _is_generic_title(title):
        better_title = _derive_title_from_content(content)
        if better_title and not _is_generic_title(better_title):
            title = better_title

    return {
        "title": title,
        "content": content,
        "content_meta": content_meta,
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

        content_meta = article.get("content_meta", {})
        raw_content = _clean_text(article.get("content", ""))
        full_content_length = len(raw_content)
        post_content = raw_content[:MAX_CONTENT_LEN]
        post_content_length = len(post_content)
        content_truncated_for_facebook = full_content_length > MAX_CONTENT_LEN

        fb_content = f"{post_content}\n\n📰 Izvor: {source_name}\n🔗 Pročitaj više: {article['url']}"
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
            "content_full_length": full_content_length,
            "content_post_length": post_content_length,
            "content_truncated_for_facebook": content_truncated_for_facebook,
            "content_extraction_method": content_meta.get("method", "unknown"),
            "content_coverage_label": content_meta.get("coverage_label", "unknown"),
            "content_coverage_ratio": content_meta.get("coverage_ratio"),
            "page_paragraph_count": content_meta.get("page_paragraph_count", 0),
            "page_paragraph_total_length": content_meta.get("page_paragraph_total_length", 0),
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

        coverage_ratio = content_meta.get("coverage_ratio")
        coverage_ratio_text = f" ({coverage_ratio:.2f})" if coverage_ratio is not None else ""
        print(
            "     📏 Content stats: "
            f"full={full_content_length} "
            f"post={post_content_length} "
            f"truncated={'yes' if content_truncated_for_facebook else 'no'} "
            f"coverage={content_meta.get('coverage_label', 'unknown')}{coverage_ratio_text}"
        )
        time.sleep(0.2)

    _save_state(state_file, scraped_urls, content_hashes, url_content_hashes)
    print(f"✅ Finished. New posts saved: {new_saved} | Updated posts saved: {updated_saved}")
