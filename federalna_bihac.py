#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://federalna.ba/search?q=Biha%C4%87&page=1",
        "Federalna Bihać",
        "federalna_bihac_state.json",
        region_terms=["bihać", "bihac", "bihaćki", "bihački", "usk", "unsko-sanski", "unsko sanski"],
    )
