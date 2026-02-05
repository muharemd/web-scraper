#!/bin/bash

echo "=== Fixing ALL remaining wrong paths ==="

# Find all files with web-scraper and fix them
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.txt" -o -name "*.log" -o -name "*.json" \) \
  -exec grep -l "web-scraper" {} \; 2>/dev/null | while read file; do
    echo "Fixing: $file"
    sed -i 's|/home/bihac-danas/web-scraper|/home/bihac-danas/web-scraper|g' "$file"
done

# Also fix any remaining relative path issues
for file in *.py; do
    if [ -f "$file" ]; then
        # Fix any paths that might have been missed
        sed -i 's|/home/bihac-danas/web-scraper/scraper-env|/home/bihac-danas/scraper-env|g' "$file"
    fi
done

echo "=== Done! ==="
