#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://ba.jooble.org/SearchResult?rgns=Unsko-sanski%20kanton", "Jooble - Unsko-sanski kanton", "jooble_state.json", region_terms=["Bihać", "Unsko"])
