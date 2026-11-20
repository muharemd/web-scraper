#!/usr/bin/env python3
from single_source_scraper import run_single_source

DIJASPORA_MHRR_URLS = [
    "https://www.dijaspora.mhrr.gov.ba/kategorija/javni-pozivi",
]

if __name__ == "__main__":
    for target_url in DIJASPORA_MHRR_URLS:
        run_single_source(target_url, "Dijaspora MHRR", "dijaspora_mhrr_state.json")
