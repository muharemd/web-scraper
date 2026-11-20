#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://naslovi.net/vesti/biha%C4%87/",
        "Naslovi.net Bihac",
        "naslovi_bihac_state.json",
        region_terms=["Bihac", "Unsko", "USK"],
    )
