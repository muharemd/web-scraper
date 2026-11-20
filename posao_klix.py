#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://posao.klix.ba/oglasi?q=Biha%C4%87", "Klix Posao - Bihać", "posao_klix_state.json")
