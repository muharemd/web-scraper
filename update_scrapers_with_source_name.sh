#!/bin/bash

# Array of scrapers and their source names
declare -A SCRAPERS=(
    ["dzbinac.py"]="Dom zdravlja Bihać"
    ["vladausk.py"]="Vlada USK"
    ["kbbihac.py"]="Kantonalna bolnica"
    ["kcbihac.py"]="Kantonalni centar"
    ["rtvusk.py"]="RTV USK"
    ["radiobihac.py"]="Radio Bihać"
    ["vodovod-bihac.py"]="Vodovod Bihać"
    ["usnkrajina.py"]="USN Krajina"
    ["komrad-bihac.py"]="Komrad Bihać"
    ["bihac-org.py"]="Grad Bihać"
)

for scraper in "${!SCRAPERS[@]}"; do
    source_name="${SCRAPERS[$scraper]}"
    
    if [ -f "$scraper" ]; then
        echo "Updating $scraper with source_name: $source_name"
        
        # Check if already has source_name
        if grep -q '"source_name":' "$scraper"; then
            echo "  Already has source_name, skipping..."
            continue
        fi
        
        # Find the JSON return statement and add source_name
        # Look for pattern like: return { ... "source": self.script_hash, ... }
        python3 -c "
import re
import sys

filename = '$scraper'
source_name = '$source_name'

with open(filename, 'r') as f:
    content = f.read()

# Pattern to find JSON return with source field
# Try multiple patterns
patterns = [
    # Pattern 1: After source field
    r'(\"source\"\s*:\s*[^,]+),\s*\n',
    # Pattern 2: In the return statement before the closing brace
    r'(return\s*\{[^}]+)(\"source\"\s*:\s*[^,]+),',
    # Pattern 3: Any return with dictionary
    r'(return\s*\{[^}]+\})',
]

updated = False
for i, pattern in enumerate(patterns):
    try:
        # Add source_name after source field
        replacement = r'\1,\n        \"source_name\": \"' + source_name + '\",'
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if new_content != content:
            with open(filename, 'w') as f:
                f.write(new_content)
            print(f'  Updated using pattern {i+1}')
            updated = True
            break
    except Exception as e:
        continue

if not updated:
    print(f'  Could not update {filename} automatically')
    print(f'  Manual update needed: Add \"source_name\": \"{source_name}\" to JSON output')
        "
    else
        echo "  File not found: $scraper"
    fi
    
    echo ""
done
