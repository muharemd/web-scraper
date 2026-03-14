#!/usr/bin/env python3
from single_source_scraper import run_single_source

CZUSK_URLS = [
    "https://www.czusk.ba/",
]

if __name__ == "__main__":
    for target_url in CZUSK_URLS:
        run_single_source(target_url, "CZUSK", "czusk_state.json")
