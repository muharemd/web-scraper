#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://fmrsp.gov.ba/obavijest", "FMRSP - Obavijesti", "fmrsp_state.json")
