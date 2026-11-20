import hashlib
import json
import os
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .. import config
from ..utils import clean_text, content_hash, normalize_text


def next_output_filename(source_hash):
    date_part = datetime.now().strftime("%Y%m%d")
    existing = [
        f for f in os.listdir(config.JSON_DIR)
        if f.startswith(f"{source_hash}-{date_part}-") and f.endswith(".json")
    ]
    return f"{source_hash}-{date_part}-{len(existing) + 1:03d}.json"


def extract_article_links(listing_url, html):
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(listing_url).netloc.lower().replace("www.", "")
    links = []
    selectors = [
        "article a[href]",
        "h1 a[href], h2 a[href], h3 a[href]",
        ".post a[href], .news a[href], .entry a[href], .item a[href], tr a[href]",
        "a[href]",
    ]
    for selector in selectors:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            full_url = urljoin(listing_url, href)
            listing_base = (f"{urlparse(listing_url).scheme}://{urlparse(listing_url).netloc}"
                            f"{urlparse(listing_url).path}").rstrip("/")
            full_base = (f"{urlparse(full_url).scheme}://{urlparse(full_url).netloc}"
                         f"{urlparse(full_url).path}").rstrip("/")
            if full_base == listing_base:
                continue
            full_domain = urlparse(full_url).netloc.lower().replace("www.", "")
            if full_domain and base_domain and full_domain != base_domain:
                continue
            lowered = full_url.lower()
            if any(x in lowered for x in ["/feed", "/rss", ".xml", "wp-admin", "logout", "login"]):
                continue
            if any(lowered.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".doc", ".docx"]):
                continue
            if full_url not in links:
                links.append(full_url)
            if len(links) >= 20:
                return links
    return links


def is_low_quality_article(article):
    title = normalize_text(article.get("title", ""))
    content = clean_text(article.get("content", ""))
    if title in {"home", "naslovna", "pocetna", "početna"}:
        return True
    if len(title) < 6:
        return True
    if len(content) < 120:
        return True
    return False


def extract_title_content(url, html):
    soup = BeautifulSoup(html, "html.parser")
    # Title
    title = "Bez naslova"
    for selector in ["h1", "meta[property='og:title']", "title"]:
        if selector.startswith("meta"):
            elem = soup.select_one(selector)
            if elem and elem.get("content"):
                candidate = clean_text(elem.get("content"))
                if len(candidate) > 4:
                    title = candidate
                    break
        else:
            elem = soup.select_one(selector)
            if elem:
                candidate = clean_text(elem.get_text(" "))
                if len(candidate) > 4:
                    title = candidate
                    break
    # Content
    content = ""
    for selector in ["article", ".entry-content", ".post-content", ".article-content",
                     "main", "#content", ".content"]:
        elem = soup.select_one(selector)
        if elem:
            for trash in elem.select("script, style, iframe, nav, footer, header, aside"):
                trash.decompose()
            candidate = clean_text(elem.get_text(" "))
            if len(candidate) >= 120:
                content = candidate
                break
    if not content:
        paragraphs = [clean_text(p.get_text(" ")) for p in soup.select("p") if len(clean_text(p.get_text(" "))) > 35]
        content = clean_text(" ".join(paragraphs))
    # Image
    image_url = ""
    for selector in ["meta[property='og:image']", "meta[name='twitter:image']",
                     "article img[src]", "main img[src]", "img[src]"]:
        if selector.startswith("meta"):
            meta = soup.select_one(selector)
            if meta and meta.get("content"):
                image_url = urljoin(url, meta.get("content"))
                break
        else:
            img = soup.select_one(selector)
            if img and img.get("src"):
                image_url = urljoin(url, img.get("src"))
                break
    return {"title": title, "content": content or title, "url": url, "image_url": image_url}


def matches_filter(article, filter_terms):
    if not filter_terms:
        return True
    haystack = normalize_text(
        f"{article.get('title', '')} {article.get('content', '')} {article.get('url', '')}"
    )
    return any(term in haystack for term in filter_terms)
