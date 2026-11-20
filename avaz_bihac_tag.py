#!/usr/bin/env python3
from rss_bihac_scraper import run_rss_source

if __name__ == "__main__":
    run_rss_source("https://www.avaz.ba/rss", "Avaz Bihać", "avaz_bihac_tag_state.json")
