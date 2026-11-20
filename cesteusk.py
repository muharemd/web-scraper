#!/usr/bin/env python3
from single_source_scraper import run_single_source

CESTEUSK_URLS = [
    "https://cesteusk.com/kategorija/konkursi/",
    "https://cesteusk.com/",
]

if __name__ == "__main__":
    for target_url in CESTEUSK_URLS:
        run_single_source(target_url, "Ceste USK", "cesteusk_state.json")
