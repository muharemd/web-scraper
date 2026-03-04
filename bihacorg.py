#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.bihac.org/obavijesti", "Grad Bihać - Obavijesti", "bihacorg_state.json")
    run_single_source("https://www.bihac.org/javni-pozivi", "Grad Bihać - Javni Pozivi", "bihacorg_state.json")
