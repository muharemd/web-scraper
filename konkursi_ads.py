#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://konkursi.ads.gov.ba/", "Konkursi ADS", "konkursi_ads_state.json")
