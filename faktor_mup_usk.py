#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://faktor.ba/tag/mup-usk/", "Faktor MUP USK", "faktor_mup_usk_state.json")
    run_single_source("https://mupusk.gov.ba/category/konkursi/", "MUP USK Konkursi", "faktor_mup_usk_state.json")
