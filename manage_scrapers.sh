cat > manage_scrapers.sh << 'EOF'
#!/bin/bash
echo "=== News Scrapers Management ==="
echo "1. Run dzbihac scraper"
echo "2. Run vladausk scraper"
echo "3. Check output directory"
echo "4. View logs"
echo "5. Setup crontab"
echo "6. Exit"
echo -n "Choose option: "
read choice

case $choice in
    1)
        echo "Running dzbihac scraper..."
        source scraper-env/bin/activate
        python dzbinac.py
        ;;
    2)
        echo "Running vladausk scraper..."
        source scraper-env/bin/activate
        python vladausk.py
        ;;
    3)
        echo "Files in facebook_ready_posts/:"
        ls -lht facebook_ready_posts/ | head -20
        echo -n "View a file? (enter filename or n): "
        read filename
        if [ "$filename" != "n" ] && [ "$filename" != "" ]; then
            python -m json.tool "facebook_ready_posts/$filename" | head -50
        fi
        ;;
    4)
        echo "=== Logs ==="
        echo "dzbihac.log:"
        tail -20 dzbihac.log 2>/dev/null || echo "No log file"
        echo ""
        echo "vladausk.log:"
        tail -20 vladausk.log 2>/dev/null || echo "No log file"
        ;;
    5)
        echo "Setting up crontab..."
        (crontab -l 2>/dev/null; echo "# News scrapers - run daily at 9 AM") | crontab -
        (crontab -l 2>/dev/null; echo "0 9 * * * cd /home/bihac-danas/web-scraper cd /home/bihac-danas/web-scraper && cd /home/bihac-danas/web-scraper &&  /home/bihac-danas/scraper-env/bin/python3 dzbinac.py >> /home/bihac-danas/web-scraper/dzbihac.log 2>&1") | crontab -
        (crontab -l 2>/dev/null; echo "30 9 * * * cd /home/bihac-danas/web-scraper cd /home/bihac-danas/web-scraper && cd /home/bihac-danas/web-scraper &&  /home/bihac-danas/scraper-env/bin/python3 vladausk.py >> /home/bihac-danas/web-scraper/vladausk.log 2>&1") | crontab -
        echo "Crontab set up!"
        ;;
    6)
        echo "Goodbye!"
        ;;
    *)
        echo "Invalid option"
        ;;
esac
EOF

