#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.boljiposao.com/poslovi/zupanija/unsko-sanski-kanton/", "Bolji Posao - Unsko-sanski kanton", "boljiposao_state.json", region_terms=["Bihać", "Unsko"])
