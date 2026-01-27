#!/usr/bin/env python3
"""
NiFi Backup Structure Inspector
Shows the actual structure of the backup to understand where processors are
"""

import os
import sys
import json
import gzip
from github import Github, Auth

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_DATE = os.environ.get('BACKUP_DATE', '2026-01-27')
BACKUP_TIME = os.environ.get('BACKUP_TIME', '00-01-UTC')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')


def print_structure(obj, indent=0, max_depth=10, current_depth=0):
    """Recursively print object structure"""
    if current_depth > max_depth:
        print("  " * indent + "... (max depth reached)")
        return
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                if isinstance(value, list):
                    print("  " * indent + f"📋 {key}: [{len(value)} items]")
                    if len(value) > 0:
                        print("  " * indent + f"   First item type: {type(value[0]).__name__}")
                        if isinstance(value[0], dict):
                            print_structure(value[0], indent + 2, max_depth, current_depth + 1)
                else:
                    print("  " * indent + f"📁 {key}:")
                    print_structure(value, indent + 1, max_depth, current_depth + 1)
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:50] + "..."
                print("  " * indent + f"📄 {key}: {value_str}")
    elif isinstance(obj, list):
        print("  " * indent + f"List with {len(obj)} items")
        if len(obj) > 0 and isinstance(obj[0], dict):
            print_structure(obj[0], indent, max_depth, current_depth + 1)


def main():
    print("=" * 60)
    print("    NiFi Backup Structure Inspector")
    print("=" * 60)
    print("")
    
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("❌ Missing GITHUB_TOKEN or GITHUB_REPO")
        sys.exit(1)
    
    try:
        # Connect to GitHub
        print(f"📦 Repository: {GITHUB_REPO}")
        print(f"📅 Backup Date: {BACKUP_DATE}")
        print(f"🕐 Backup Time: {BACKUP_TIME}")
        print("")
        
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(GITHUB_REPO)
        
        # Download backup
        backup_path = f"{BACKUP_FOLDER}/{BACKUP_DATE}/{BACKUP_TIME}"
        flow_file = repo.get_contents(f"{backup_path}/flow.json.gz", ref=BACKUP_BRANCH)
        flow_content = flow_file.decoded_content
        
        # Try to decompress
        try:
            flow_json = gzip.decompress(flow_content)
        except:
            flow_json = flow_content
        
        # Parse JSON
        flow_data = json.loads(flow_json)
        
        print("=" * 60)
        print("BACKUP STRUCTURE")
        print("=" * 60)
        print("")
        
        # Show top-level keys
        print("🔑 Top-level keys:")
        for key in flow_data.keys():
            print(f"  - {key}")
        print("")
        
        # Show full structure
        print("=" * 60)
        print("FULL STRUCTURE")
        print("=" * 60)
        print("")
        print_structure(flow_data, max_depth=5)
        print("")
        
        # Look specifically for process groups
        print("=" * 60)
        print("PROCESS GROUPS ANALYSIS")
        print("=" * 60)
        print("")
        
        flow_contents = flow_data.get('flowContents', flow_data)
        process_groups = flow_contents.get('processGroups', [])
        
        print(f"Found {len(process_groups)} process group(s)")
        print("")
        
        for i, pg in enumerate(process_groups):
            print(f"Process Group {i + 1}:")
            print(f"  Keys: {list(pg.keys())}")
            print("")
            
            # Check different possible locations for contents
            if 'contents' in pg:
                print(f"  ✅ Has 'contents' key")
                contents = pg['contents']
                print(f"     Contents keys: {list(contents.keys())}")
                print(f"     Processors: {len(contents.get('processors', []))}")
                print(f"     Connections: {len(contents.get('connections', []))}")
            
            if 'component' in pg:
                print(f"  ✅ Has 'component' key")
                component = pg['component']
                print(f"     Component keys: {list(component.keys())}")
                
                if 'contents' in component:
                    print(f"     Component has 'contents'")
                    contents = component['contents']
                    print(f"     Contents keys: {list(contents.keys())}")
                    print(f"     Processors: {len(contents.get('processors', []))}")
                    print(f"     Connections: {len(contents.get('connections', []))}")
            
            print("")
        
        # Save full structure to file
        output_file = "/tmp/backup-structure.json"
        with open(output_file, 'w') as f:
            json.dump(flow_data, f, indent=2)
        print(f"💾 Full backup saved to: {output_file}")
        print("")
        
        g.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()