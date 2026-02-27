#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://euronews.ba/tema/3479/bihac",
        "Euronews Bihać",
        "euronews_bihac_state.json",
        region_terms=[
            "bihac",
            "bihać",
            "grad bihac",
            "grad bihać",
            "unsko-sanski",
            "una-sana",
            "usk",
            "cazin",
            "sanski most",
            "velika kladusa",
            "velika kladuša",
            "buzim",
            "bužim",
        ],
    )
