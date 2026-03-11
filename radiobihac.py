#!/usr/bin/env python3
from single_source_scraper import run_single_source

RADIOBIHAC_URLS = [
    "https://www.radiobihac.com/kategorija/rtv-bihac/7",
    "https://www.radiobihac.com/kategorija/usk/8",
    "https://www.radiobihac.com/kategorija/sport/18",
    "https://www.radiobihac.com/kategorija/obavijesti/17",
]

if __name__ == "__main__":
    for target_url in RADIOBIHAC_URLS:
        run_single_source(target_url, "Radio Bihac", "radiobihac_state.json")
