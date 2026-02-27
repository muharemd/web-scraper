#!/usr/bin/env python3
from rss_bihac_scraper import run_rss_source

if __name__ == "__main__":
    run_rss_source("https://www.fokus.ba/tag/bihac/feed", "Fokus Bihać", "fokus_bihac_state.json")
