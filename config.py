import os
from datetime import datetime

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File Paths
JSON_DIR = "/home/bihac-danas/web-scraper/facebook_ready_posts"
WEBHOOK_URL = "https://hook.eu1.make.com/p1kanqk3w243rnyaio8gbeeiosvhddgb"
SERVER_IP = '31.31.74.183'
PORT = 8080

# Source Mappings (for identifying where articles come from)
SOURCE_MAPPINGS = {
    'dz': 'Dom zdravlja',
    'vod': 'Vodovod',
    'bihac': 'Grad Bihać',
    'usk': 'USK',
    'krajina': 'USN Krajina',
    'komrad': 'Komrad',
    'radio': 'Radio',
    'rtv': 'RTV',
    'zdravlje': 'Dom zdravlja',
    'mup': 'MUP USK',
    'adsba': 'ADS FBiH',
    'mojposao': 'Moj Posao',
    'klix': 'Klix',
    'avaz': 'Avaz',
}

def get_source_name(filename):
    """Detect source name from filename hash or prefix"""
    source_hash = filename.split('-')[0].lower() if '-' in filename else filename[:12].lower()
    for key, name in SOURCE_MAPPINGS.items():
        if key in source_hash:
            return name
    return "Unknown Source"
