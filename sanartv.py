#!/usr/bin/env python3
from single_source_scraper import run_single_source

SANARTV_URLS = [
    "https://sanartv.ba/",
]

if __name__ == "__main__":
    for target_url in SANARTV_URLS:
        run_single_source(target_url, "Sana RTV", "sanartv_state.json")
