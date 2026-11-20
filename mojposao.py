#!/usr/bin/env python3
from single_source_scraper import run_single_source

if __name__ == "__main__":
    run_single_source("https://www.mojposao.ba/pretraga-poslova?locations=Biha%C4%87&locations=Cazin&locations=Velika+Kladu%C5%A1a&locations=Bosanska+Krupa&locations=Bu%C5%BEim&locations=Klju%C4%8D&locations=Sanski+Most&locations=Bosanski+Petrovac", "MojPosao - Unsko-sanski kanton", "mojposao_state.json", region_terms=["Bihać", "Cazin"])
