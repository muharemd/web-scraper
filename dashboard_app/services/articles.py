import json
import os
import traceback

from .. import config


def get_articles(offset=0, limit=50):
    """Load article JSON files, sorted by modification time (newest first)."""
    articles = []
    if not os.path.exists(config.JSON_DIR):
        print(f"ERROR: JSON directory not found: {config.JSON_DIR}")
        return articles
    try:
        files = [f for f in os.listdir(config.JSON_DIR) if f.endswith(".json")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(config.JSON_DIR, x)), reverse=True)
        page_files = files[offset:(offset + limit)] if limit is not None else files[offset:]
        for filename in page_files:
            filepath = os.path.join(config.JSON_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                source_name = data.get("source_name", "Unknown")
                if source_name == "Unknown":
                    n = filename.lower()
                    if "dz" in n:        source_name = "Dom zdravlja"
                    elif "vod" in n:     source_name = "Vodovod"
                    elif "bihac" in n:   source_name = "Grad Bihać"
                    elif "usk" in n:     source_name = "USK"
                    elif "krajina" in n: source_name = "USN Krajina"
                    elif "komrad" in n:  source_name = "Komrad"
                    elif "radio" in n:   source_name = "Radio Bihać"
                    elif "rtv" in n:     source_name = "RTV USK"
                    elif "vlada" in n:   source_name = "Vlada USK"
                    elif "kb" in n:      source_name = "Kantonalna bolnica"
                    elif "kc" in n:      source_name = "Kantonalni centar"
                content = data.get("content", "")
                articles.append({
                    "filename": filename,
                    "title": data.get("title", "Nema naslova"),
                    "title_rewritten": data.get("title_rewritten", ""),
                    "content": content,
                    "content_preview": content,
                    "date": data.get("date", "Unknown"),
                    "published": data.get("published", ""),
                    "published_target": data.get("published_target", ""),
                    "source_name": source_name,
                    "url": data.get("url", "#"),
                    "is_new": not bool(data.get("published")),
                    "image_url": data.get("image_url", ""),
                    "wp_published": data.get("wp_published", ""),
                    "wp_url": data.get("wp_url", ""),
                    "wp_post_id": data.get("wp_post_id", ""),
                    "wp_category": data.get("wp_category", ""),
                })
            except Exception as e:
                print(f"ERROR reading {filename}: {e}")
    except Exception as e:
        print(f"ERROR in get_articles: {e}")
        traceback.print_exc()
    return articles
