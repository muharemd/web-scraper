#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.fhmzbih.gov.ba/latinica/METEO/prognozaBI.php", "FHMZ BiH Meteo", "fhmzbih_meteo_state.json")
