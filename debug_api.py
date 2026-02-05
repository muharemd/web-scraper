#!/usr/bin/env python3
"""
Debug script to check for API endpoints in Oslobođenje search
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import json
import re

SEARCH_URL = "https://www.oslobodjenje.ba/pretraga/"
SEARCH_TERM = "bihac"

# Create session
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
})

# Get the search page
response = session.get(f"{SEARCH_URL}?search={quote(SEARCH_TERM)}")
soup = BeautifulSoup(response.content, 'html.parser')

# Look for script tags that might contain API endpoints
print("=== SCRIPT TAGS ===")
script_tags = soup.find_all('script')
for script in script_tags[:10]:  # Check first 10 scripts
    src = script.get('src', '')
    if src:
        print(f"Script src: {src}")
    
    # Check inline scripts for API endpoints
    if script.string:
        content = script.string[:500]
        if 'api' in content.lower() or 'search' in content.lower():
            print(f"Inline script contains API/search references:")
            print(content)
            print("-" * 50)

# Look for JSON-LD or structured data
print("\n=== STRUCTURED DATA ===")
for script in soup.find_all('script', type='application/ld+json'):
    try:
        data = json.loads(script.string)
        print(f"JSON-LD data: {json.dumps(data, indent=2)[:500]}...")
    except:
        pass

# Check for iframe or other embeds
print("\n=== IFRAMES ===")
for iframe in soup.find_all('iframe'):
    print(f"Iframe src: {iframe.get('src')}")

# Check network traffic pattern by looking at XHR patterns in scripts
print("\n=== LOOKING FOR XHR/API PATTERNS ===")
for script in script_tags:
    if script.string:
        # Look for fetch, axios, jQuery.ajax patterns
        patterns = [
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.(?:get|post)\(["\']([^"\']+)["\']',
            r'\$\.(?:ajax|get|post)\(["\']([^"\']+)["\']',
            r'url:\s*["\']([^"\']+)["\']',
            r'apiUrl:\s*["\']([^"\']+)["\']',
            r'endpoint:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, script.string, re.IGNORECASE)
            for match in matches:
                if 'search' in match.lower() or 'query' in match.lower():
                    print(f"Found potential API endpoint: {match}")

# Try to find the actual search results container
print("\n=== SEARCHING FOR RESULTS CONTAINER ===")
# Look for common search result selectors
result_selectors = [
    '.search-results',
    '.results',
    '.listing',
    '.articles',
    '.posts',
    '[data-results]',
    '#results',
    '.searchResults'
]

for selector in result_selectors:
    elements = soup.select(selector)
    if elements:
        print(f"Found element with selector '{selector}':")
        for elem in elements[:2]:
            print(f"  HTML snippet: {str(elem)[:200]}...")
            print(f"  Classes: {elem.get('class', [])}")
            print(f"  ID: {elem.get('id', '')}")

# Check if there's a "no results" message
no_results_texts = [
    'Nema rezultata',
    'Nije pronađen',
    'No results',
    '0 results'
]

for text in no_results_texts:
    if text in response.text:
        print(f"\nFound 'no results' text: {text}")

print("\n=== CHECKING FOR PAGINATION ===")
pagination = soup.select('.pagination, .pages, .page-numbers, nav[aria-label*="pagination"]')
if pagination:
    print("Found pagination elements")
else:
    print("No pagination found - might be single page or no results")

# Save a snippet of the HTML to see structure
print("\n=== SAVING HTML SNIPPET ===")
with open('search_page_snippet.html', 'w', encoding='utf-8') as f:
    # Get just the body content
    body = soup.find('body')
    if body:
        f.write(str(body)[:5000])
        print("Saved body snippet to search_page_snippet.html")
