#!/usr/bin/env python3
from single_source_scraper import run_single_source

CAZIN_BA_URLS = [
    "https://cazin.ba/category/cazin/",
]

if __name__ == "__main__":
    for target_url in CAZIN_BA_URLS:
        run_single_source(target_url, "Cazin.ba", "cazin_ba_state.json")
