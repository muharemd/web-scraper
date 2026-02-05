#!/usr/bin/env python3
"""
Debug script to check Oslobođenje search page structure
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import json

SEARCH_URL = "https://www.oslobodjenje.ba/pretraga/"
SEARCH_TERM = "bihac"

# Create session with headers
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
})

# Make the request
search_page_url = f"{SEARCH_URL}?search={quote(SEARCH_TERM)}"
print(f"Fetching: {search_page_url}")

response = session.get(search_page_url, timeout=30)
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")

# Save raw HTML for inspection
with open('debug_search.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
print("Saved raw HTML to debug_search.html")

# Parse with BeautifulSoup
soup = BeautifulSoup(response.content, 'html.parser')

# Find all links
print("\n=== ALL LINKS ON PAGE ===")
all_links = soup.find_all('a', href=True)
for link in all_links[:20]:  # First 20 links
    href = link.get('href', '')
    text = link.get_text(strip=True)[:100]
    print(f"Link: {href}")
    print(f"Text: {text}")
    print(f"Class: {link.get('class', '')}")
    print("-" * 50)

# Look for article containers
print("\n=== POSSIBLE ARTICLE CONTAINERS ===")
for div in soup.find_all(['div', 'article', 'section']):
    classes = div.get('class', [])
    if classes:
        print(f"Element: {div.name}, Classes: {classes}")

# Look for search results specifically
print("\n=== SEARCH RESULTS INFO ===")
results_info = soup.find_all(text=lambda t: 'rezult' in t.lower() or 'nađen' in t.lower())
for text in results_info:
    print(f"Found text: {text[:200]}")

# Save the parsed HTML structure
with open('debug_soup.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())
print("\nSaved parsed HTML to debug_soup.html")
