#!/usr/bin/env python3
from single_source_scraper import run_single_source

BUZIMPRESS_URLS = [
    "https://buzimpress.ba/kategorija/buzim/",
]

if __name__ == "__main__":
    for target_url in BUZIMPRESS_URLS:
        run_single_source(target_url, "Buzim Press", "buzimpress_state.json")
