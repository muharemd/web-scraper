#!/usr/bin/env python3
from single_source_scraper import run_single_source

CRT_BA_URLS = [
    "https://crt.ba/",
]

if __name__ == "__main__":
    for target_url in CRT_BA_URLS:
        run_single_source(target_url, "CRT.ba", "crt_ba_state.json")
