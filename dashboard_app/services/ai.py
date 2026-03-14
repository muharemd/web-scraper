import json
import os

import requests

from .. import config


def load_deepseek_api_key():
    config_file = os.path.join(config.BASE_DIR, ".deepseek_config")
    try:
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if "DEEPSEEK_API_KEY=" in line:
                    value = line.split("DEEPSEEK_API_KEY=", 1)[1].strip()
                    return value.strip('"').strip("'")
    except Exception as e:
        print(f"ERROR loading DeepSeek API key: {e}")
    return None


def rewrite_single_title(filename):
    """Rewrite the title of one article JSON using the DeepSeek API."""
    filepath = os.path.join(config.JSON_DIR, os.path.basename(filename))
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("title_rewritten"):
            return {"success": False, "error": "Title already rewritten"}
        api_key = load_deepseek_api_key()
        if not api_key:
            return {"success": False, "error": "API key not found"}
        title = data.get("title", "")
        content = data.get("content", "")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite news titles to be short, catchy, and accurate "
                        "and please offer only one possibility. "
                        "All in Bosnian or Croatian language."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Rewrite this title using the article content:\nTitle: {title}\nContent: {content}",
                },
            ],
        }
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code != 200:
            return {"success": False, "error": f"API error: {response.status_code}"}
        rewritten = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not rewritten:
            return {"success": False, "error": "No rewritten title received from API"}
        data["title_rewritten"] = rewritten
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "original": title, "rewritten": rewritten}
    except Exception as e:
        return {"success": False, "error": str(e)}
