#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.ads.gov.ba/bs-latn-ba/open-vacancies?page=1&rows=9&searchByStatus=Open", "ADS - Slobodna radna mjesta", "ads_gov_state.json")
