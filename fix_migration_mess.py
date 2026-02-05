#!/usr/bin/env python3
# fix_migration_mess.py - Fix the paths messed up by migrate.py

import os
import re
import glob

def fix_file(filepath):
    """Fix paths in a single file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Fix 1: Remove the double web-scraper
        updated = content.replace('/home/bihac-danas/web-scraper/', '/home/bihac-danas/web-scraper/')
        
        # Fix 2: Python venv should be in home directory, not web-scraper
        updated = updated.replace('/home/bihac-danas/scraper-env/', '/home/bihac-danas/scraper-env/')
        
        if content != updated:
            with open(filepath, 'w') as f:
                f.write(updated)
            print(f"✓ Fixed: {filepath}")
            return True
        else:
            print(f"  Already correct: {filepath}")
            return False
    
    except Exception as e:
        print(f"✗ Error: {filepath}: {e}")
        return False

def main():
    print("=== Fixing migration mess ===")
    
    # Get all Python and Bash scripts in current directory
    scripts = []
    for ext in ('*.py', '*.sh'):
        scripts.extend(glob.glob(ext))
    
    print(f"Found {len(scripts)} scripts to fix")
    print("=" * 60)
    
    fixed_count = 0
    for script in scripts:
        if fix_file(script):
            fixed_count += 1
    
    print("=" * 60)
    print(f"Fixed {fixed_count}/{len(scripts)} files")
    print("\nIMPORTANT: Check run_all_scrapers.sh manually!")
    print("Python path should be: /home/bihac-danas/scraper-env/bin/python3")

if __name__ == "__main__":
    main()
