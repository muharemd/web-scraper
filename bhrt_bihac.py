#!/usr/bin/env python3
from single_source_scraper import run_single_source

BHRT_BIHAC_URLS = [
    "https://www.bhrt.ba/rezultati-pretrage?q=Biha%C4%87",
]

if __name__ == "__main__":
    for target_url in BHRT_BIHAC_URLS:
        run_single_source(target_url, "BHRT Bihac", "bhrt_bihac_state.json")
