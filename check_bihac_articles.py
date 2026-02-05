#!/usr/bin/env python3
"""
Check if Oslobođenje has any Bihać articles at all
"""

import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.oslobodjenje.ba"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
})

# Check homepage for any Bihać mentions
print("Checking homepage for Bihać mentions...")
response = session.get(BASE_URL)
soup = BeautifulSoup(response.content, 'html.parser')

# Get all text and check for Bihać
all_text = soup.get_text().lower()
if 'bihac' in all_text or 'bihać' in all_text:
    print("Found Bihać mentions on homepage")
    
    # Find where it's mentioned
    for element in soup.find_all(text=re.compile(r'bihac|bihać', re.IGNORECASE)):
        parent = element.parent
        if parent.name in ['a', 'h1', 'h2', 'h3', 'h4', 'p']:
            print(f"Found in {parent.name}: {element[:100]}...")
            if parent.name == 'a' and parent.get('href'):
                print(f"  Link: {parent.get('href')}")
else:
    print("No Bihać mentions found on homepage")

# Try different search terms
search_terms = ['bihac', 'bihać', 'bihacki', 'usk', 'una-sana']
print(f"\nTrying different search terms: {search_terms}")

for term in search_terms:
    print(f"\nSearching for: {term}")
    search_url = f"https://www.oslobodjenje.ba/pretraga/?search={term}"
    response = session.get(search_url)
    
    # Simple check for article links
    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a', href=True)
    article_links = [l for l in links if '/clanak/' in l['href'] or '/vijesti/' in l['href']]
    
    print(f"Found {len(article_links)} potential article links")
    if article_links:
        for link in article_links[:3]:
            print(f"  - {link['href']} ({link.get_text()[:50]}...)")
