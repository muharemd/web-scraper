#!/usr/bin/env python3
from single_source_scraper import run_single_source

KBBIHAC_URLS = [
    "https://www.kbbihac.ba/novosti",
]

if __name__ == "__main__":
    for target_url in KBBIHAC_URLS:
        run_single_source(target_url, "KB Bihac", "kbbihac_state.json")
