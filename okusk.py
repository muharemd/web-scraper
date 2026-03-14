#!/usr/bin/env python3
from single_source_scraper import run_single_source

OKUSK_URLS = [
    "https://okusk.org/",
]

if __name__ == "__main__":
    for target_url in OKUSK_URLS:
        run_single_source(target_url, "OK USK", "okusk_state.json")
