#!/usr/bin/env python3
from single_source_scraper import run_single_source

USNKRAJINA_URLS = [
    "https://www.usnkrajina.ba/kategorija/kanton/1",
    "https://www.usnkrajina.ba/kategorija/sport/4",
    "https://www.usnkrajina.ba/kategorija/magazin/5",
]

if __name__ == "__main__":
    for target_url in USNKRAJINA_URLS:
        run_single_source(target_url, "USN Krajina", "usnkrajina_state.json")
