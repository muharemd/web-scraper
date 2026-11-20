#!/usr/bin/env python3
from single_source_scraper import run_single_source

GRADCAZIN_URLS = [
    "https://gradcazin.gov.ba/novosti",
]

if __name__ == "__main__":
    for target_url in GRADCAZIN_URLS:
        run_single_source(target_url, "Grad Cazin", "gradcazin_state.json")
