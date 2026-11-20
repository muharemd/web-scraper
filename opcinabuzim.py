#!/usr/bin/env python3
from single_source_scraper import run_single_source

OPCINABUZIM_URLS = [
    "https://opcinabuzim.ba/",
]

if __name__ == "__main__":
    for target_url in OPCINABUZIM_URLS:
        run_single_source(target_url, "Opcina Buzim", "opcinabuzim_state.json")
