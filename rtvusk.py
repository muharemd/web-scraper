#!/usr/bin/env python3
from single_source_scraper import run_single_source

RTVUSK_URLS = [
    "https://www.rtvusk.ba/kategorija/kanton-krajina/2",
    "https://www.rtvusk.ba/kategorija/kultura/13",
    "https://www.rtvusk.ba/kategorija/usk-krajina/20",
    "https://www.rtvusk.ba/kategorija/dijaspora-invest/28",
    "https://www.rtvusk.ba/kategorija/oglasi/30",
]

if __name__ == "__main__":
    for target_url in RTVUSK_URLS:
        run_single_source(target_url, "RTV USK", "rtvusk_state.json")
