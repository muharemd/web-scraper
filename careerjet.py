#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.careerjet.ba/posao/Unsko-sanski-kanton", "Careerjet - Unsko-sanski kanton", "careerjet_state.json", region_terms=["Bihać", "Unsko"])
