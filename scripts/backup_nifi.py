#!/usr/bin/env python3
"""
NiFi Backup Script - FIXED VERSION
Properly counts processors inside process groups
"""

import os
import sys
import json
import gzip
import requests
from datetime import datetime
from github import Github, Auth

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
NIFI_HOST = os.environ.get('NIFI_HOST')
NIFI_USERNAME = os.environ.get('NIFI_USERNAME')
NIFI_PASSWORD = os.environ.get('NIFI_PASSWORD')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')


def get_nifi_token():
    """Authenticate with NiFi"""
    url = f"{NIFI_HOST}/nifi-api/access/token"
    response = requests.post(
        url,
        data={'username': NIFI_USERNAME, 'password': NIFI_PASSWORD},
        verify=False,
        timeout=30
    )
    response.raise_for_status()
    return response.text


def get_root_process_group_id(token):
    """Get root process group ID"""
    url = f"{NIFI_HOST}/nifi-api/flow/process-groups/root"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()['processGroupFlow']['id']


def download_flow(token, process_group_id):
    """Download flow from NiFi"""
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/download"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=120)
    response.raise_for_status()
    return response.content


def count_components_recursive(flow_contents):
    """Recursively count all components including nested ones"""
    stats = {
        'process_groups': 0,
        'processors': 0,
        'connections': 0,
        'input_ports': 0,
        'output_ports': 0,
        'funnels': 0,
        'labels': 0
    }
    
    # Count at this level
    stats['processors'] += len(flow_contents.get('processors', []))
    stats['connections'] += len(flow_contents.get('connections', []))
    stats['input_ports'] += len(flow_contents.get('inputPorts', []))
    stats['output_ports'] += len(flow_contents.get('outputPorts', []))
    stats['funnels'] += len(flow_contents.get('funnels', []))
    stats['labels'] += len(flow_contents.get('labels', []))
    
    # Recursively count in child process groups
    # NOTE: NiFi backup format has processors DIRECTLY in processGroups array
    # NOT in processGroups[].contents or processGroups[].component.contents
    for pg in flow_contents.get('processGroups', []):
        stats['process_groups'] += 1
        
        # Processors are directly in the pg object
        child_stats = count_components_recursive(pg)
        
        # Add child stats to total (except process_groups, we already counted that)
        stats['processors'] += child_stats['processors']
        stats['connections'] += child_stats['connections']
        stats['input_ports'] += child_stats['input_ports']
        stats['output_ports'] += child_stats['output_ports']
        stats['funnels'] += child_stats['funnels']
        stats['labels'] += child_stats['labels']
        stats['process_groups'] += child_stats['process_groups']
    
    return stats


def main():
    print("=" * 60)
    print("         NiFi Backup Script (FIXED)")
    print("=" * 60)
    print("")
    
    # Validate environment variables
    required_vars = {
        'NIFI_HOST': NIFI_HOST,
        'NIFI_USERNAME': NIFI_USERNAME,
        'NIFI_PASSWORD': NIFI_PASSWORD,
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO': GITHUB_REPO
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    print(f"🔗 NiFi Host: {NIFI_HOST}")
    print(f"📦 GitHub Repo: {GITHUB_REPO}")
    print("")
    
    try:
        # Step 1: Authenticate with NiFi
        print("Step 1: Authenticating with NiFi...")
        token = get_nifi_token()
        print("  ✅ Authentication successful")
        print("")
        
        # Step 2: Get root process group
        print("Step 2: Getting root process group...")
        root_pg_id = get_root_process_group_id(token)
        print(f"  ✅ Root PG ID: {root_pg_id}")
        print("")
        
        # Step 3: Download flow
        print("Step 3: Downloading flow from NiFi...")
        flow_data = download_flow(token, root_pg_id)
        print(f"  ✅ Downloaded flow ({len(flow_data):,} bytes)")
        print("")
        
        # Step 4: Parse and analyze flow
        print("Step 4: Analyzing flow structure...")
        flow_json = json.loads(flow_data)
        flow_contents = flow_json.get('flowContents', flow_json)
        
        # Use recursive counting
        stats = count_components_recursive(flow_contents)
        
        print(f"  📊 Flow Statistics:")
        print(f"     - Process Groups: {stats['process_groups']}")
        print(f"     - Processors: {stats['processors']}")
        print(f"     - Connections: {stats['connections']}")
        print(f"     - Input Ports: {stats['input_ports']}")
        print(f"     - Output Ports: {stats['output_ports']}")
        print(f"     - Funnels: {stats['funnels']}")
        print(f"     - Labels: {stats['labels']}")
        print("")
        
        # Step 5: Prepare backup
        print("Step 5: Preparing backup files...")
        timestamp = datetime.utcnow()
        backup_date = timestamp.strftime('%Y-%m-%d')
        backup_time = timestamp.strftime('%H-%M') + '-UTC'
        
        # Create metadata
        metadata = {
            'backup_timestamp': timestamp.isoformat() + 'Z',
            'backup_date': backup_date,
            'backup_time': backup_time,
            'nifi_host': NIFI_HOST,
            'root_process_group_id': root_pg_id,
            'statistics': stats
        }
        
        print(f"  📅 Backup Date: {backup_date}")
        print(f"  🕐 Backup Time: {backup_time}")
        print("")
        
        # Step 6: Connect to GitHub
        print("Step 6: Connecting to GitHub...")
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(GITHUB_REPO)
        print("  ✅ Connected successfully")
        print("")
        
        # Step 7: Upload to GitHub
        print("Step 7: Uploading backup to GitHub...")
        backup_path = f"{BACKUP_FOLDER}/{backup_date}/{backup_time}"
        
        # Upload flow.json.gz
        flow_file_path = f"{backup_path}/flow.json.gz"
        flow_compressed = gzip.compress(flow_data)
        
        try:
            repo.create_file(
                flow_file_path,
                f"Backup NiFi flow - {backup_date} {backup_time}",
                flow_compressed,
                branch=BACKUP_BRANCH
            )
            print(f"  ✅ Uploaded: {flow_file_path}")
        except Exception as e:
            print(f"  ⚠️  File may already exist, trying update...")
            contents = repo.get_contents(flow_file_path, ref=BACKUP_BRANCH)
            repo.update_file(
                flow_file_path,
                f"Update NiFi flow backup - {backup_date} {backup_time}",
                flow_compressed,
                contents.sha,
                branch=BACKUP_BRANCH
            )
            print(f"  ✅ Updated: {flow_file_path}")
        
        # Upload metadata.json
        metadata_file_path = f"{backup_path}/metadata.json"
        metadata_json = json.dumps(metadata, indent=2).encode('utf-8')
        
        try:
            repo.create_file(
                metadata_file_path,
                f"Backup metadata - {backup_date} {backup_time}",
                metadata_json,
                branch=BACKUP_BRANCH
            )
            print(f"  ✅ Uploaded: {metadata_file_path}")
        except Exception as e:
            print(f"  ⚠️  File may already exist, trying update...")
            contents = repo.get_contents(metadata_file_path, ref=BACKUP_BRANCH)
            repo.update_file(
                metadata_file_path,
                f"Update metadata - {backup_date} {backup_time}",
                metadata_json,
                contents.sha,
                branch=BACKUP_BRANCH
            )
            print(f"  ✅ Updated: {metadata_file_path}")
        
        print("")
        print("=" * 60)
        print("✅ BACKUP COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("")
        print(f"Backup location: {backup_path}")
        print(f"Total components: {sum(stats.values())}")
        print("")
        print("=" * 60)
        
        g.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()