#!/usr/bin/env python3
from single_source_scraper import run_single_source

DZBIHAC_URLS = [
    "https://www.dzbihac.com/index.php/en/medija-centar/novosti/clanci/",
]

if __name__ == "__main__":
    for target_url in DZBIHAC_URLS:
        run_single_source(target_url, "DZ Bihac", "dzbihac_state.json")
