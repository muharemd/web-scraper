#!/usr/bin/env python3
from single_source_scraper import run_single_source

PZUSK_URLS = [
    "https://www.pzusk.ba/",
]

if __name__ == "__main__":
    for target_url in PZUSK_URLS:
        run_single_source(target_url, "PZ USK", "pzusk_state.json")
