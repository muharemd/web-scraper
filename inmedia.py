#!/usr/bin/env python3
from single_source_scraper import run_single_source

INMEDIA_URLS = [
    "https://www.inmedia.ba/",
    "https://www.inmedia.ba/category/lokalne-teme/",
]

if __name__ == "__main__":
    for target_url in INMEDIA_URLS:
        run_single_source(target_url, "InMedia", "inmedia_state.json")
