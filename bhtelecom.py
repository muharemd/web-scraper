#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.bhtelecom.ba/category/javni-oglasi-za-posao/", "BH Telecom - Javni oglasi", "bhtelecom_state.json")
