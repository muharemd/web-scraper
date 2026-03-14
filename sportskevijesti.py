#!/usr/bin/env python3
from single_source_scraper import run_single_source

SPORTSKEVIJESTI_URLS = [
    "https://sportskevijesti.com/tag/nk-jedinstvo-bihac/",
]

if __name__ == "__main__":
    for target_url in SPORTSKEVIJESTI_URLS:
        run_single_source(target_url, "Sportske Vijesti", "sportskevijesti_state.json")
