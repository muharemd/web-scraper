#!/bin/bash
# Script to remove API key from git history

cd /home/bihac-danas/web-scraper

echo "Creating backup..."
git branch backup-before-cleanup

echo "Replacing API key in git history..."
git filter-branch --force --tree-filter \
  'if [ -f rewrite_titles_deepseek.sh ]; then 
     sed -i "s/sk-e82a64e534624689909b4453b4e6f2d0/YOUR_API_KEY_REMOVED_FROM_HISTORY/g" rewrite_titles_deepseek.sh
   fi' \
  --prune-empty --tag-name-filter cat -- --all

echo "Cleaning up..."
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo ""
echo "✅ Done! Now you need to:"
echo "1. Force push to GitHub: git push origin --force --all"
echo "2. Verify the API key is not in GitHub history"
echo "3. Delete the old API key from DeepSeek dashboard"
echo "4. Update .deepseek_config with a new API key"
echo ""
echo "⚠️  WARNING: This will rewrite history. Coordinate with team members!"
