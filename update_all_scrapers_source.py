#!/usr/bin/env python3
"""
Add source_name to all scraper JSON outputs
"""

scrapers = {
    'dzbinac.py': 'Dom zdravlja Bihać',
    'vladausk.py': 'Vlada USK',
    'kbbihac.py': 'Kantonalna bolnica',
    'kcbihac.py': 'Kantonalni centar',
    'rtvusk.py': 'RTV USK',
    'radiobihac.py': 'Radio Bihać',
    'vodovod-bihac.py': 'Vodovod Bihać',
    'usnkrajina.py': 'USN Krajina',
    'komrad-bihac.py': 'Komrad Bihać',
    'bihac-org.py': 'Grad Bihać'
}

for scraper, source_name in scrapers.items():
    print(f"Updating {scraper} to include source_name: {source_name}")
    # Each scraper needs to add: "source_name": "Human Readable Name"
    # to the JSON output
