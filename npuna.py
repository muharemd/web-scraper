#!/usr/bin/env python3
from single_source_scraper import run_single_source

NPUNA_URLS = [
    "https://npuna.com/blog/",
]

if __name__ == "__main__":
    for target_url in NPUNA_URLS:
        run_single_source(target_url, "NPUNA", "npuna_state.json")
