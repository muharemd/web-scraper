import hashlib
import json
import os
import re

from . import config


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).replace("\r", " ").replace("\n", " ")).strip()


def content_hash(text):
    normalized = " ".join(text.split()).lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def normalize_text(text):
    value = clean_text(text).lower()
    return (
        value.replace("ć", "c")
        .replace("č", "c")
        .replace("š", "s")
        .replace("ž", "z")
        .replace("đ", "dj")
    )


def extract_tagged_json(prefix, text):
    """Parse one JSON payload from a tagged stdout line."""
    for line in (text or "").splitlines():
        if line.startswith(prefix):
            try:
                return json.loads(line[len(prefix):].strip())
            except Exception:
                return None
    return None


def load_custom_state():
    if os.path.exists(config.CUSTOM_SCRAPE_STATE_FILE):
        try:
            with open(config.CUSTOM_SCRAPE_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_custom_state(state):
    with open(config.CUSTOM_SCRAPE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
