#!/usr/bin/env python3
"""
Summarize scraper content coverage signals from generated JSON posts.

This report is most useful for posts generated after content coverage metadata
was added in single_source_scraper.py.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

POST_CONTENT_LIMIT = 900


def _clean_text(text):
    if not isinstance(text, str):
        return ""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split()).strip()


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _extract_source_name(payload):
    source_name = payload.get("source_name")
    if isinstance(source_name, str) and source_name.strip():
        return source_name.strip()

    source = payload.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip()

    return "unknown"


def _infer_full_length(payload):
    explicit = payload.get("content_full_length")
    if isinstance(explicit, int) and explicit >= 0:
        return explicit

    content = payload.get("content", "")
    if not isinstance(content, str):
        return 0

    if "\n\n📰 Izvor:" in content:
        content = content.split("\n\n📰 Izvor:", 1)[0]

    return len(_clean_text(content))


def _infer_coverage_label(payload, full_length):
    label = payload.get("content_coverage_label")
    if isinstance(label, str) and label.strip():
        return label.strip()

    if "content_full_length" not in payload:
        return "legacy_no_metadata"

    if full_length <= 0:
        return "empty"

    return "unknown"


def _iter_json_files(ready_dir):
    if not ready_dir.exists():
        return []
    return sorted(path for path in ready_dir.glob("*.json") if path.is_file())


def _load_payload(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def _iter_payload_records(payload):
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _format_percent(part, total):
    if total <= 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def build_report(paths, source_filter=None):
    global_counts = Counter()
    source_stats = defaultdict(lambda: {
        "total": 0,
        "labels": Counter(),
        "truncated": 0,
        "avg_full_length_total": 0,
        "avg_post_length_total": 0,
    })
    partial_examples = []

    for path in paths:
        payload = _load_payload(path)
        if payload is None:
            global_counts["invalid_json"] += 1
            continue

        records = _iter_payload_records(payload)
        if not records:
            global_counts["invalid_json"] += 1
            continue

        for record_index, record in enumerate(records):
            source_name = _extract_source_name(record)
            if source_filter and source_name.lower() != source_filter.lower():
                continue

            full_length = _infer_full_length(record)
            post_length = _safe_int(record.get("content_post_length"), default=min(full_length, POST_CONTENT_LIMIT))
            truncated = record.get("content_truncated_for_facebook")
            if not isinstance(truncated, bool):
                truncated = full_length > POST_CONTENT_LIMIT

            label = _infer_coverage_label(record, full_length)
            ratio = record.get("content_coverage_ratio")

            global_counts["total"] += 1
            global_counts[f"label:{label}"] += 1
            if truncated:
                global_counts["truncated"] += 1

            stats = source_stats[source_name]
            stats["total"] += 1
            stats["labels"][label] += 1
            stats["avg_full_length_total"] += full_length
            stats["avg_post_length_total"] += post_length
            if truncated:
                stats["truncated"] += 1

            if label in {"likely_partial", "possibly_partial"}:
                record_suffix = f"[{record_index}]" if len(records) > 1 else ""
                partial_examples.append({
                    "file": f"{path.name}{record_suffix}",
                    "source_name": source_name,
                    "label": label,
                    "ratio": ratio,
                    "url": record.get("url", ""),
                    "full_length": full_length,
                    "post_length": post_length,
                })

    return global_counts, source_stats, partial_examples


def print_report(global_counts, source_stats, partial_examples, max_examples):
    total = global_counts["total"]
    print("=" * 88)
    print("CONTENT COVERAGE REPORT")
    print("=" * 88)
    print(f"Total posts analyzed: {total}")
    print(f"Facebook-truncated posts: {global_counts['truncated']} ({_format_percent(global_counts['truncated'], total)})")
    print(f"Likely full: {global_counts['label:likely_full']} ({_format_percent(global_counts['label:likely_full'], total)})")
    print(f"Possibly partial: {global_counts['label:possibly_partial']} ({_format_percent(global_counts['label:possibly_partial'], total)})")
    print(f"Likely partial: {global_counts['label:likely_partial']} ({_format_percent(global_counts['label:likely_partial'], total)})")
    print(f"Unknown: {global_counts['label:unknown']} ({_format_percent(global_counts['label:unknown'], total)})")
    print(
        f"Legacy (no metadata): {global_counts['label:legacy_no_metadata']} "
        f"({_format_percent(global_counts['label:legacy_no_metadata'], total)})"
    )
    print(f"Invalid JSON skipped: {global_counts['invalid_json']}")
    print()

    print("Per-source summary:")
    print("-" * 88)
    header = (
        f"{'Source':36} {'Total':>5} {'Full':>5} {'PossPart':>8} {'LikPart':>7} "
        f"{'Unknown':>7} {'Legacy':>7} {'Trunc':>6} {'AvgFull':>8}"
    )
    print(header)
    print("-" * len(header))

    sorted_sources = sorted(
        source_stats.items(),
        key=lambda kv: (
            kv[1]["labels"]["likely_partial"] + kv[1]["labels"]["possibly_partial"],
            kv[1]["total"],
        ),
        reverse=True,
    )

    for source_name, stats in sorted_sources:
        total_source = stats["total"]
        avg_full = int(stats["avg_full_length_total"] / total_source) if total_source else 0
        print(
            f"{source_name[:36]:36} "
            f"{total_source:>5} "
            f"{stats['labels']['likely_full']:>5} "
            f"{stats['labels']['possibly_partial']:>8} "
            f"{stats['labels']['likely_partial']:>7} "
            f"{stats['labels']['unknown']:>7} "
            f"{stats['labels']['legacy_no_metadata']:>7} "
            f"{stats['truncated']:>6} "
            f"{avg_full:>8}"
        )

    print()
    print("Examples flagged as partial:")
    print("-" * 88)
    if not partial_examples:
        print("None")
        return

    partial_examples_sorted = sorted(
        partial_examples,
        key=lambda item: (
            0 if item["label"] == "likely_partial" else 1,
            item["full_length"],
        ),
    )

    for item in partial_examples_sorted[:max_examples]:
        ratio = item.get("ratio")
        ratio_text = f"ratio={ratio:.2f} " if isinstance(ratio, (int, float)) else ""
        print(
            f"{item['label']:16} {ratio_text}"
            f"full={item['full_length']:4} post={item['post_length']:4} "
            f"source={item['source_name']}"
        )
        print(f"  file={item['file']}")
        print(f"  url={item['url']}")


def main():
    parser = argparse.ArgumentParser(
        description="Report whether scraped content looks full or partial based on saved JSON metadata."
    )
    parser.add_argument(
        "--ready-dir",
        default="facebook_ready_posts",
        help="Directory containing generated JSON posts (default: facebook_ready_posts)",
    )
    parser.add_argument(
        "--source",
        default="",
        help="Only include a specific source_name (case-insensitive exact match)",
    )
    parser.add_argument(
        "--latest",
        type=int,
        default=0,
        help="Only analyze the latest N files by filename order (0 = all)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=12,
        help="How many partial examples to print",
    )
    args = parser.parse_args()

    ready_dir = Path(args.ready_dir)
    paths = _iter_json_files(ready_dir)

    if args.latest and args.latest > 0:
        paths = paths[-args.latest :]

    counts, sources, partial_examples = build_report(paths, source_filter=args.source.strip() or None)
    print_report(counts, sources, partial_examples, max_examples=max(1, args.max_examples))


if __name__ == "__main__":
    main()
