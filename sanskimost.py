#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://sanskimost.gov.ba/index.php/obavijesti",
        "Sanski Most - Obavijesti",
        "sanskimost_state.json",
    )
