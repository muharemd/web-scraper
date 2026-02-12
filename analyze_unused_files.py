#!/usr/bin/env python3
"""
Analyze files in the web-scraper directory to identify unused files
"""

import os
import re
from pathlib import Path

# Active scrapers from run_all_scrapers.sh
ACTIVE_SCRAPERS = [
    "vladausk.py",
    "kbbihac.py",
    "kcbihac.py",
    "rtvusk.py",
    "radiobihac.py",
    "vodovod-bihac.py",
    "usnkrajina.py",
    "bihac-org.py",
    "bihamk-rss.py",
    "prostornobihac.py",
    "grad-cazin.py",
    "opcina-buzim.py",
    "sanski-most.py",
    "crt_ba.py",
    "pufbih.py",
    "uino.py",
    "ussume.py",
    "zzousk.py",
    "cesteusk.py",
    "antikorupcijausk.py",
    "pravosudje.py",
    "radiovkladusa.py",
    "sanartv.py",
    "npuna.py",
]

# Core system files that are always needed
CORE_FILES = [
    "run_all_scrapers.sh",
    "scraper_log.txt",
    "README.md",
    "dashboard.py",
    "dashboard_users.json",
]

# Essential directories
ESSENTIAL_DIRS = [
    "scraper-env",
    "facebook_ready_posts",
    "templates",
]

def get_state_file_for_scraper(scraper_name):
    """Get the expected state file name for a scraper"""
    # Remove .py extension and replace - with _
    base_name = scraper_name.replace('.py', '').replace('-', '_')
    return f"{base_name}_state.json"

def analyze_files():
    """Analyze all files and categorize them"""
    
    workspace = Path("/home/bihac-danas/web-scraper")
    
    # Expected state files for active scrapers
    expected_state_files = set()
    for scraper in ACTIVE_SCRAPERS:
        state_file = get_state_file_for_scraper(scraper)
        expected_state_files.add(state_file)
    
    # Files that should be kept
    keep_files = set(ACTIVE_SCRAPERS + CORE_FILES + list(expected_state_files))
    
    # Get all files in workspace (excluding directories)
    all_files = []
    for item in workspace.iterdir():
        if item.is_file():
            all_files.append(item.name)
        elif item.is_dir() and item.name not in ESSENTIAL_DIRS:
            # List directories that might be removable
            pass
    
    # Categorize files
    categories = {
        'active_scrapers': [],
        'state_files_active': [],
        'core_system': [],
        'commented_scrapers': [],
        'state_files_unused': [],
        'debug_files': [],
        'utility_scripts': [],
        'other_python': [],
        'html_files': [],
        'text_files': [],
        'unknown': [],
    }
    
    for filename in sorted(all_files):
        if filename in ACTIVE_SCRAPERS:
            categories['active_scrapers'].append(filename)
        elif filename in CORE_FILES:
            categories['core_system'].append(filename)
        elif filename in expected_state_files:
            categories['state_files_active'].append(filename)
        elif filename.endswith('_state.json'):
            categories['state_files_unused'].append(filename)
        elif filename.startswith('debug_'):
            categories['debug_files'].append(filename)
        elif filename in ['dzbinac.py', 'komrad-bihac.py', 'klix_feed.py']:
            categories['commented_scrapers'].append(filename)
        elif filename.endswith('.sh') and filename not in CORE_FILES:
            categories['utility_scripts'].append(filename)
        elif filename.endswith('.py') and filename not in ACTIVE_SCRAPERS:
            categories['other_python'].append(filename)
        elif filename.endswith('.html'):
            categories['html_files'].append(filename)
        elif filename.endswith('.txt') and filename not in CORE_FILES:
            categories['text_files'].append(filename)
        elif filename == 'deleteme':
            categories['debug_files'].append(filename)
        else:
            categories['unknown'].append(filename)
    
    # Print report
    print("=" * 80)
    print("FILE ANALYSIS REPORT - Web Scraper Directory")
    print("=" * 80)
    print()
    
    print("✅ ESSENTIAL FILES (KEEP THESE)")
    print("-" * 80)
    print(f"\n🟢 Active Scrapers ({len(categories['active_scrapers'])} files):")
    for f in categories['active_scrapers']:
        print(f"  ✓ {f}")
    
    print(f"\n🟢 State Files for Active Scrapers ({len(categories['state_files_active'])} files):")
    for f in categories['state_files_active']:
        print(f"  ✓ {f}")
    
    print(f"\n🟢 Core System Files ({len(categories['core_system'])} files):")
    for f in categories['core_system']:
        print(f"  ✓ {f}")
    
    print(f"\n🟢 Essential Directories:")
    for d in ESSENTIAL_DIRS:
        if (workspace / d).exists():
            print(f"  ✓ {d}/")
    
    print("\n" + "=" * 80)
    print("⚠️  POTENTIALLY REMOVABLE FILES")
    print("=" * 80)
    
    print(f"\n🔴 Commented Out / Inactive Scrapers ({len(categories['commented_scrapers'])} files):")
    for f in categories['commented_scrapers']:
        print(f"  ✗ {f}")
    
    print(f"\n🔴 State Files for Unused Scrapers ({len(categories['state_files_unused'])} files):")
    for f in categories['state_files_unused']:
        print(f"  ✗ {f}")
    
    print(f"\n🔴 Debug/Development Files ({len(categories['debug_files'])} files):")
    for f in categories['debug_files']:
        print(f"  ✗ {f}")
    
    print(f"\n🟡 Utility Scripts (may or may not be needed) ({len(categories['utility_scripts'])} files):")
    for f in categories['utility_scripts']:
        print(f"  ? {f}")
    
    print(f"\n🔴 Other Python Scripts (not in active list) ({len(categories['other_python'])} files):")
    for f in categories['other_python']:
        print(f"  ✗ {f}")
    
    print(f"\n🔴 HTML Files ({len(categories['html_files'])} files):")
    for f in categories['html_files']:
        print(f"  ✗ {f}")
    
    print(f"\n🔴 Text Files ({len(categories['text_files'])} files):")
    for f in categories['text_files']:
        print(f"  ✗ {f}")
    
    if categories['unknown']:
        print(f"\n❓ Unknown/Other Files ({len(categories['unknown'])} files):")
        for f in categories['unknown']:
            print(f"  ? {f}")
    
    # Generate deletion script
    print("\n" + "=" * 80)
    print("📝 SUMMARY")
    print("=" * 80)
    
    total_keep = (len(categories['active_scrapers']) + 
                  len(categories['state_files_active']) + 
                  len(categories['core_system']))
    
    removable = (categories['commented_scrapers'] + 
                 categories['state_files_unused'] + 
                 categories['debug_files'] + 
                 categories['other_python'] + 
                 categories['html_files'] + 
                 categories['text_files'])
    
    print(f"Files to KEEP: {total_keep}")
    print(f"Files potentially REMOVABLE: {len(removable)}")
    print(f"Files to REVIEW (utilities): {len(categories['utility_scripts'])}")
    
    # Create removal script
    print("\n" + "=" * 80)
    print("🗑️  REMOVAL SCRIPT")
    print("=" * 80)
    print("\nTo remove identified files, create and run this script:\n")
    
    script_content = """#!/bin/bash
# Remove unused files from web-scraper directory
# Generated by analyze_unused_files.py

cd /home/bihac-danas/web-scraper

echo "Removing unused files..."
"""
    
    for filename in removable:
        script_content += f'rm -v "{filename}"\n'
    
    script_content += '\necho ""\necho "Done! Removed ' + str(len(removable)) + ' files."\n'
    
    # Save the script
    script_path = workspace / "remove_unused_files.sh"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    
    print(f"Script saved to: remove_unused_files.sh")
    print(f"\nTo execute: ./remove_unused_files.sh")
    
    print("\n" + "=" * 80)
    print("⚠️  FILES TO REVIEW MANUALLY")
    print("=" * 80)
    print("\nThese utility scripts should be reviewed manually:")
    for f in categories['utility_scripts']:
        print(f"  - {f}")

if __name__ == "__main__":
    analyze_files()
