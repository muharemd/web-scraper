#!/usr/bin/env python3
import sys
import os

# Add current directory to Python path to find the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from single_source_scraper import run_single_source

VLADAUSK_URLS = [
    "https://vladausk.ba/v4/novost/konkursi-za-popunu-upraznjenih-radnih-mjesta/672",
    "https://vladausk.ba/v4/index/skupstina-usk/10",
    "https://vladausk.ba/v4/index/ministarstvo-finansija/1",
    "https://vladausk.ba/v4/index/ministarstvo-obrazovanja-nauke-kulture-i-sporta/2",
    "https://vladausk.ba/v4/index/ministarstvo-pravosudja-i-uprave/3",
    "https://vladausk.ba/v4/index/ministarstvo-privrede/4",
    "https://vladausk.ba/v4/index/ministarstvo-za-gradjenje-prostorno-uredjenje-i-zastite-okolisa/5",
    "https://vladausk.ba/v4/index/ministarstvo-unutrasnjih-poslova/6",
    "https://vladausk.ba/v4/index/ministarstvo-za-pitanje-boraca-i-rvi/7",
    "https://vladausk.ba/v4/index/ministarstvo-zdravstva-i-socijalne-politike/8",
    "https://vladausk.ba/v4/index/ministarstvo-poljoprivrede-vodoprivrede-i-sumarstvo/9",
    "https://vladausk.ba/v4/preuzimanja",
    "https://vladausk.ba/v4/vrsta/javne-rasprave/3",
    "https://vladausk.ba/v4/vrsta/javni-pozivi-i-konkursi/4",
    "https://vladausk.ba/v4/vrsta/javni-pozivi-i-konkursi/5",
    "https://vladausk.ba/v4/vrsta/vladaob/7",
    "https://vladausk.ba/v4/vrsta/kategorija/26",
]

if __name__ == "__main__":
    for target_url in VLADAUSK_URLS:
        run_single_source(target_url, "Vlada USK - Konkursi", "vladausk_state.json")
