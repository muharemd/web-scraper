#!/bin/bash

echo "=== Fixing all paths properly ==="

# Remove ALL web-scraper patterns
find . -type f \( -name "*.py" -o -name "*.sh" \) -exec sed -i 's|/home/bihac-danas/web-scraper/|/home/bihac-danas/web-scraper/|g' {} \;

# Fix the Python path in run_all_scrapers.sh
sed -i 's|PYTHON="/home/bihac-danas/scraper-env/bin/python3"|PYTHON="/home/bihac-danas/scraper-env/bin/python3"|g' run_all_scrapers.sh
sed -i 's|PYTHON="/home/bihac-danas/scraper-env/bin/python3"|PYTHON="/home/bihac-danas/scraper-env/bin/python3"|g' run_all_scrapers.sh

# Fix manage_scrapers.sh cron lines
sed -i 's|cd /home/bihac-danas/web-scraper && /home/bihac-danas/scraper-env/bin/python|cd /home/bihac-danas/web-scraper && /home/bihac-danas/scraper-env/bin/python3|g' manage_scrapers.sh

# Fix cleanup_script.sh paths
sed -i 's|/home/bihac-danas/web-scraper/|/home/bihac-danas/web-scraper/|g' cleanup_script.sh

# Fix the crontab line in cleanup_script.sh
sed -i 's|echo "0 2 \* \* \* /home/bihac-danas/web-scraper/cleanup_script.sh|echo "0 2 * * * /home/bihac-danas/web-scraper/cleanup_script.sh|g' cleanup_script.sh

echo "=== Paths fixed! ==="
