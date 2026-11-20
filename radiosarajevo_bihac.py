#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://radiosarajevo.ba/pretraga?keywords=Biha%C4%87",
        "Radio Sarajevo",
        "radiosarajevo_bihac_state.json",
        region_terms=["bihac", "bihać", "bihaću", "bihačani"]
    )
