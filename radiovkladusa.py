#!/usr/bin/env python3
from single_source_scraper import run_single_source

RADIOVLADUSA_URLS = [
    "https://www.radiovkladusa.ba/",
]

if __name__ == "__main__":
    for target_url in RADIOVLADUSA_URLS:
        run_single_source(target_url, "Radio Velika Kladuša", "radiovkladusa_state.json")
