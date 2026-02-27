#!/usr/bin/env python3
from rss_bihac_scraper import run_rss_source

if __name__ == "__main__":
    run_rss_source("https://www.klix.ba/rss", "Klix Bihać", "klix_tag_bihac_state.json")
