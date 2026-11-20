#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.vijesti.ba/pretraga?keyword=biha%C4%87", "Vijesti.ba Bihać", "vijesti_ba_bihac_state.json")
