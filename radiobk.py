#!/usr/bin/env python3
from single_source_scraper import run_single_source

RADIOBK_URLS = [
    "https://radiobk.ba/category/sportske-novosti/",
    "https://radiobk.ba/",
]

if __name__ == "__main__":
    for target_url in RADIOBK_URLS:
        run_single_source(target_url, "Radio BK", "radiobk_state.json")
