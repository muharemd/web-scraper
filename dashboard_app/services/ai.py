import json
import os
import re

import requests

from .. import config
from ..utils import clean_text


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


def _extract_json_object(raw_text):
    text = (raw_text or "").strip()
    if not text:
        return None

    candidates = [text]

    if text.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_\-]*\s*", "", text)
        stripped = re.sub(r"\s*```$", "", stripped)
        candidates.append(stripped.strip())

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0).strip())

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _lookup_rewrite_text(payload, key_aliases):
    queue = [payload]
    seen_ids = set()

    while queue:
        current = queue.pop(0)
        current_id = id(current)
        if current_id in seen_ids:
            continue
        seen_ids.add(current_id)

        if isinstance(current, dict):
            for key in key_aliases:
                value = current.get(key)
                if isinstance(value, str) and clean_text(value):
                    return value
            for value in current.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    queue.append(item)

    return ""


def rewrite_title_and_content_custom(title, content, custom_prompt):
    """Rewrite title and content with DeepSeek using a custom user prompt."""
    title_text = clean_text(title)
    content_text = _clean_multiline_text(content)
    prompt_text = _clean_multiline_text(custom_prompt)

    if not title_text:
        return {"success": False, "error": "Title is required"}
    if not content_text:
        return {"success": False, "error": "Content is required"}
    if not prompt_text:
        return {"success": False, "error": "Custom prompt is required"}

    api_key = load_deepseek_api_key()
    if not api_key:
        return {"success": False, "error": "API key not found"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior Bosnian/Croatian editor. "
                    "Rewrite provided title and content while preserving facts and clarity. "
                    "Always return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Custom rewrite prompt:\n{prompt_text}\n\n"
                    f"Original title:\n{title_text}\n\n"
                    f"Original content:\n{content_text}\n\n"
                    "Return ONLY JSON with exactly these keys:\n"
                    "{\"title\":\"...\",\"content\":\"...\"}\n"
                    "No markdown code fences."
                ),
            },
        ],
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45,
        )
    except Exception as exc:
        return {"success": False, "error": f"Request failed: {exc}"}

    if response.status_code != 200:
        body_snippet = (response.text or "").strip().replace("\n", " ")[:300]
        return {
            "success": False,
            "error": f"API error: {response.status_code}. {body_snippet}",
        }

    raw_output = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    if not raw_output:
        return {"success": False, "error": "No rewrite content received from API"}

    parsed = _extract_json_object(raw_output)
    if not parsed:
        return {
            "success": False,
            "error": f"Could not parse JSON from model output: {raw_output[:240]}",
        }

    rewritten_title = clean_text(
        _lookup_rewrite_text(
            parsed,
            [
                "title",
                "rewritten_title",
                "headline",
                "new_title",
                "title_rewritten",
            ],
        )
    )
    rewritten_content = _clean_multiline_text(
        _lookup_rewrite_text(
            parsed,
            [
                "content",
                "rewritten_content",
                "body",
                "new_content",
                "content_rewritten",
                "text",
            ],
        )
    )

    if not rewritten_title and not rewritten_content:
        return {
            "success": False,
            "error": (
                "AI response did not include usable title/content fields. "
                "Try a clearer prompt, e.g. 'Return JSON with title and content keys only.'"
            ),
        }

    if not rewritten_title:
        rewritten_title = title_text
    if not rewritten_content:
        rewritten_content = content_text

    changed_title = rewritten_title != title_text
    changed_content = rewritten_content != content_text
    if not changed_title and not changed_content:
        return {
            "success": False,
            "error": (
                "AI returned the same title and content. "
                "Adjust your prompt to request a stronger rewrite."
            ),
        }

    return {
        "success": True,
        "original_title": title_text,
        "original_content": content_text,
        "rewritten_title": rewritten_title,
        "rewritten_content": rewritten_content,
        "changed_title": changed_title,
        "changed_content": changed_content,
    }


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
