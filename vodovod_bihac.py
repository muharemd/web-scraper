#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source(
        "https://www.vodovod-bihac.ba/bs/kategorija/aktuelnosti/1",
        "Vodovod Bihac - Aktuelnosti",
        "vodovod_bihac_state.json",
    )
