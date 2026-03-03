#!/usr/bin/env python3

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://usk-szz.ba"
LISTING_URL = f"{BASE_URL}/oglasi"
STATE_FILE = "usk_szz_oglasi_state.json"
OUTPUT_DIR = "facebook_ready_posts"
SOURCE_NAME = "SZZ USK Oglasi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").replace("\n", " ")).strip()


def _generate_content_hash(content):
    normalized = " ".join(content.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _load_state(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            valid_urls = {
                url
                for url in data.get("scraped_urls", [])
                if isinstance(url, str) and "/eidoglasGetData/" in url
            }
            return valid_urls, set(data.get("content_hashes", []))
    return set(), set()


def _save_state(path, scraped_urls, content_hashes):
    state = {
        "scraped_urls": list(scraped_urls),
        "content_hashes": list(content_hashes),
        "last_run": datetime.now().isoformat(),
        "script_name": os.path.basename(sys.argv[0]),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)


def _fetch_html(url, session):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    return response.text


def _parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    items = []
    for row in table.find_all("tr"):
        row_id = (row.get("id") or "").strip()
        if not row_id.isdigit():
            continue

        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        title = _clean_text(cols[1].get_text(" ", strip=True))
        company = _clean_text(cols[2].get_text(" ", strip=True))
        open_until = _clean_text(cols[3].get_text(" ", strip=True))
        if not title:
            continue

        items.append(
            {
                "id": int(row_id),
                "title": title,
                "company": company,
                "open_until": open_until,
            }
        )

    return items


def _fetch_detail(oglas_id, session):
    detail_url = f"{BASE_URL}/eidoglasGetData/{oglas_id}"
    response = session.get(detail_url, timeout=25)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list) and data:
        return data[0]
    return {}


def _compose_title(row, detail):
    headline = _clean_text(row.get("title")) or "N/A"
    company = _clean_text(row.get("company")) or "N/A"
    opis_poslova = _clean_text(detail.get("opis_poslova")) or "N/A"

    return (
        f"Naslov: {headline}\n"
        f"Firma: {company}\n"
        f"Opis poslova: {opis_poslova}"
    )


def _document_links(detail):
    links = []

    attachment = _clean_text(detail.get("prilog"))
    if attachment and attachment.lower() != "null":
        links.append(urljoin(BASE_URL, f"/public/storage/uploads/oglasiprilog/{attachment}"))

    images_raw = detail.get("slike")
    if images_raw:
        try:
            parsed = json.loads(images_raw) if isinstance(images_raw, str) else images_raw
            if isinstance(parsed, list):
                for name in parsed:
                    filename = _clean_text(name)
                    if filename:
                        links.append(urljoin(BASE_URL, f"/public/storage/uploads/oglasiprilog/{filename}"))
        except Exception:
            pass

    deduped = []
    seen = set()
    for link in links:
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped


def _compose_content(row, detail):
    lines = []
    lines.append(f"Naslov: {row['title']}")
    lines.append(f"Firma: {row['company'] or 'N/A'}")
    lines.append(f"Otvoren do: {row['open_until'] or 'N/A'}")
    if detail.get("mjesto_zaposlenja"):
        lines.append(f"Mjesto zaposlenja: {_clean_text(detail.get('mjesto_zaposlenja'))}")
    if detail.get("broj_izvrsilaca"):
        lines.append(f"Broj izvršilaca: {_clean_text(detail.get('broj_izvrsilaca'))}")

    if detail.get("opis_poslova"):
        lines.append("")
        lines.append(f"Opis poslova: {_clean_text(detail.get('opis_poslova'))}")

    if detail.get("potrebna_dokumentacija"):
        lines.append("")
        lines.append(f"Potrebna dokumentacija: {_clean_text(detail.get('potrebna_dokumentacija'))}")

    if detail.get("datum_objave"):
        lines.append(f"Objavljen: {_clean_text(detail.get('datum_objave'))}")

    if detail.get("prijava_email"):
        lines.append(f"Email za prijavu: {_clean_text(detail.get('prijava_email'))}")
    if detail.get("telefon"):
        lines.append(f"Telefon: {_clean_text(detail.get('telefon'))}")
    if detail.get("adresa"):
        lines.append(f"Adresa: {_clean_text(detail.get('adresa'))}")

    external_link = _clean_text(detail.get("link"))
    if external_link:
        lines.append(f"Link: {external_link}")

    doc_links = _document_links(detail)
    if doc_links:
        lines.append("")
        lines.append("Dokumenti:")
        for idx, link in enumerate(doc_links, start=1):
            lines.append(f"{idx}. {link}")

    content = "\n".join(line for line in lines if line is not None)
    return f"{content}\n\n📰 Izvor: {SOURCE_NAME}\n🔗 Pročitaj više: {BASE_URL}/oglasi"


def _public_source_url(detail):
    external_link = _clean_text(detail.get("link"))
    if external_link and external_link.startswith(("http://", "https://")):
        return external_link

    attachment = _clean_text(detail.get("prilog"))
    if attachment and attachment.lower() != "null":
        return urljoin(BASE_URL, f"/public/storage/uploads/oglasiprilog/{attachment}")

    return LISTING_URL


def _image_from_detail(detail):
    doc_links = _document_links(detail)
    for link in doc_links:
        lowered = link.lower()
        if lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")):
            return link

    profile_image = _clean_text(detail.get("profile_image"))
    if profile_image and profile_image.lower() != "null":
        return urljoin(BASE_URL, f"/public/storage/profile_images/{profile_image}")
    return None


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    script_hash = hashlib.md5(os.path.basename(sys.argv[0]).encode()).hexdigest()[:12]
    scraped_urls, content_hashes = _load_state(STATE_FILE)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 60)
    print(f"🗂️  {SOURCE_NAME} SCRAPER")
    print("=" * 60)
    print(f"Source URL: {LISTING_URL}")

    html = _fetch_html(LISTING_URL, session)
    rows = _parse_rows(html)
    print(f"Found oglasi: {len(rows)}")

    new_saved = 0
    for row in rows:
        detail_api_url = f"{BASE_URL}/eidoglasGetData/{row['id']}"
        if detail_api_url in scraped_urls:
            continue

        detail = _fetch_detail(row["id"], session)
        content = _compose_content(row, detail)
        content_hash = _generate_content_hash(content)
        if content_hash in content_hashes:
            scraped_urls.add(detail_api_url)
            continue

        date_value = _clean_text(detail.get("datum_objave")) or datetime.now().strftime("%Y-%m-%d")
        payload = {
            "title": _compose_title(row, detail),
            "id": hashlib.md5(detail_api_url.encode()).hexdigest()[:8],
            "content": content,
            "url": _public_source_url(detail),
            "raw_url": detail_api_url,
            "scheduled_publish_time": None,
            "published": "",
            "source": script_hash,
            "source_name": SOURCE_NAME,
            "content_hash": content_hash,
            "scraped_at": datetime.now().isoformat(),
            "date": date_value,
        }

        image_url = _image_from_detail(detail)
        if image_url:
            payload["image_url"] = image_url

        all_doc_links = _document_links(detail)
        if all_doc_links:
            payload["image_urls"] = all_doc_links

        date_part = datetime.now().strftime("%Y%m%d")
        existing = [
            name
            for name in os.listdir(OUTPUT_DIR)
            if name.startswith(f"{script_hash}-{date_part}-") and name.endswith(".json")
        ]
        next_num = len(existing) + 1
        filename = f"{script_hash}-{date_part}-{next_num:03d}.json"

        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        scraped_urls.add(detail_api_url)
        content_hashes.add(content_hash)
        new_saved += 1
        print(f"  💾 Saved: {filename} | {row['title'][:70]}")

    _save_state(STATE_FILE, scraped_urls, content_hashes)
    print(f"✅ Finished. New posts saved: {new_saved}")


if __name__ == "__main__":
    run()