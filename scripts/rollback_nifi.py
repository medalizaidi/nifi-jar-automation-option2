#!/usr/bin/env python3
"""
NiFi Rollback Script
Restores a NiFi flow from a specific backup by date
Usage: 
  python rollback_nifi.py                    # List available backups
  python rollback_nifi.py --list-only        # Only list, don't connect to NiFi
  BACKUP_DATE=YYYY-MM-DD BACKUP_TIME=HH-MM-UTC python rollback_nifi.py
"""

import os
import sys
import json
import gzip
import requests
import argparse
from datetime import datetime
from github import Github, Auth

# Disable SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===========================================
# Configuration from Environment Variables
# ===========================================
NIFI_HOST = os.environ.get('NIFI_HOST')
NIFI_USERNAME = os.environ.get('NIFI_USERNAME')
NIFI_PASSWORD = os.environ.get('NIFI_PASSWORD')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'avaxops/nifi-jar-automation-option2')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')

# Pipeline parameters (from CircleCI)
BACKUP_DATE = os.environ.get('BACKUP_DATE', '')  # Format: YYYY-MM-DD
BACKUP_TIME = os.environ.get('BACKUP_TIME', '')  # Format: HH-MM-UTC


def get_nifi_token():
    """Authenticate with NiFi and get access token"""
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
    """Get the root process group ID"""
    url = f"{NIFI_HOST}/nifi-api/flow/process-groups/root"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()['processGroupFlow']['id']


def get_process_group_version(token, process_group_id):
    """Get the current version of the process group"""
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()['revision']['version']


def stop_all_processors(token, process_group_id):
    """Stop all processors in the process group"""
    url = f"{NIFI_HOST}/nifi-api/flow/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    
    flow = response.json()['processGroupFlow']['flow']
    processors = flow.get('processors', [])
    
    stopped_count = 0
    for processor in processors:
        if processor['status']['runStatus'] == 'Running':
            stop_processor(token, processor['id'], processor['revision']['version'])
            stopped_count += 1
    
    return stopped_count


def stop_processor(token, processor_id, version):
    """Stop a specific processor"""
    url = f"{NIFI_HOST}/nifi-api/processors/{processor_id}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'revision': {'version': version},
        'component': {'id': processor_id, 'state': 'STOPPED'}
    }
    response = requests.put(url, headers=headers, json=payload, verify=False, timeout=30)
    response.raise_for_status()


def upload_flow_version(token, process_group_id, flow_content):
    """Upload a flow version to NiFi (replace existing flow)"""
    # Note: NiFi doesn't have a direct "restore from backup" API
    # This is a simplified approach - in production you may need to:
    # 1. Stop all processors
    # 2. Delete existing components
    # 3. Upload new flow definition
    # 4. Start processors
    
    # For now, we'll use the process group upload endpoint
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/process-groups/upload"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # The flow_content is the backup JSON
    response = requests.post(
        url, 
        headers=headers, 
        data=flow_content,
        verify=False, 
        timeout=120
    )
    response.raise_for_status()
    return response.json()


def list_available_backups(repo, backup_folder):
    """List all available backups"""
    try:
        contents = repo.get_contents(backup_folder, ref=BACKUP_BRANCH)
        date_folders = [item for item in contents if item.type == "dir"]
        
        backups = []
        for date_folder in date_folders:
            # Get time folders within each date
            time_contents = repo.get_contents(date_folder.path, ref=BACKUP_BRANCH)
            time_folders = [item for item in time_contents if item.type == "dir"]
            
            for time_folder in time_folders:
                backups.append({
                    'date': date_folder.name,
                    'time': time_folder.name,
                    'path': time_folder.path
                })
        
        return sorted(backups, key=lambda x: (x['date'], x['time']), reverse=True)
    except Exception as e:
        return []


def download_backup(repo, backup_path):
    """Download backup files from GitHub"""
    try:
        # Get flow.json.gz
        flow_file = repo.get_contents(f"{backup_path}/flow.json.gz", ref=BACKUP_BRANCH)
        flow_content = flow_file.decoded_content
        
        # Get metadata.json
        metadata_file = repo.get_contents(f"{backup_path}/metadata.json", ref=BACKUP_BRANCH)
        metadata_content = metadata_file.decoded_content
        metadata = json.loads(metadata_content)
        
        # Decompress flow
        flow_json = gzip.decompress(flow_content)
        
        return flow_json, metadata
    except Exception as e:
        raise Exception(f"Failed to download backup: {e}")


def main():
    print("=" * 60)
    print("         NiFi Rollback Script")
    print("=" * 60)
    print("")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='NiFi Rollback Script')
    parser.add_argument('--list-only', action='store_true', 
                       help='Only list available backups, do not connect to NiFi')
    args = parser.parse_args()
    
    # Validate required environment variables for GitHub
    github_vars = {
        'GITHUB_TOKEN': GITHUB_TOKEN,
        'GITHUB_REPO': GITHUB_REPO
    }
    
    missing = [k for k, v in github_vars.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Validate NiFi variables only if not in list-only mode
    if not args.list_only:
        nifi_vars = {
            'NIFI_HOST': NIFI_HOST,
            'NIFI_USERNAME': NIFI_USERNAME,
            'NIFI_PASSWORD': NIFI_PASSWORD
        }
        
        missing_nifi = [k for k, v in nifi_vars.items() if not v]
        if missing_nifi:
            print(f"❌ Missing environment variables: {', '.join(missing_nifi)}")
            sys.exit(1)
        
        print(f"🔗 NiFi Host: {NIFI_HOST}")
    
    print(f"📦 GitHub Repo: {GITHUB_REPO}")
    print("")
    
    try:
        # Step 1: Connect to GitHub
        print("Step 1: Connecting to GitHub...")
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(GITHUB_REPO)
        print("  ✅ Connected successfully")
        
        # Step 2: List available backups if no date specified
        if not BACKUP_DATE:
            print("")
            print("Step 2: Listing available backups...")
            backups = list_available_backups(repo, BACKUP_FOLDER)
            
            if not backups:
                print("  ❌ No backups found")
                sys.exit(1)
            
            print(f"  ✅ Found {len(backups)} backups")
            print("")
            print("Available backups (most recent first):")
            print("-" * 60)
            for i, backup in enumerate(backups[:10], 1):  # Show last 10
                print(f"  {i}. {backup['date']} {backup['time']}")
            
            if len(backups) > 10:
                print(f"  ... and {len(backups) - 10} more")
            
            print("")
            print("=" * 60)
            
            # If in list-only mode, exit successfully
            if args.list_only:
                print("✅ BACKUP LIST COMPLETED")
                print("=" * 60)
                g.close()
                sys.exit(0)
            
            # Otherwise, show error that no date was specified
            print("❌ ERROR: No backup date specified")
            print("")
            print("To rollback, set these environment variables:")
            print("  - BACKUP_DATE (format: YYYY-MM-DD)")
            print("  - BACKUP_TIME (format: HH-MM-UTC)")
            print("")
            print("Example:")
            print(f"  export BACKUP_DATE='{backups[0]['date']}'")
            print(f"  export BACKUP_TIME='{backups[0]['time']}'")
            print("=" * 60)
            g.close()
            sys.exit(1)
        
        # Step 3: Validate and locate backup
        print(f"Step 2: Locating backup from {BACKUP_DATE} {BACKUP_TIME}...")
        
        if not BACKUP_TIME:
            print("  ❌ BACKUP_TIME not specified")
            print("")
            print("Available times for this date:")
            date_path = f"{BACKUP_FOLDER}/{BACKUP_DATE}"
            try:
                time_contents = repo.get_contents(date_path, ref=BACKUP_BRANCH)
                time_folders = [item.name for item in time_contents if item.type == "dir"]
                for time in sorted(time_folders):
                    print(f"    - {time}")
            except:
                print("    (No backups found for this date)")
            sys.exit(1)
        
        backup_path = f"{BACKUP_FOLDER}/{BACKUP_DATE}/{BACKUP_TIME}"
        print(f"  📁 Backup path: {backup_path}")
        
        # Step 4: Download backup
        print("Step 3: Downloading backup from GitHub...")
        flow_json, metadata = download_backup(repo, backup_path)
        print(f"  ✅ Downloaded backup ({len(flow_json):,} bytes)")
        print(f"  📊 Backup metadata:")
        print(f"     - Timestamp: {metadata.get('backup_timestamp', 'N/A')}")
        print(f"     - Processors: {metadata.get('statistics', {}).get('processors', 0)}")
        print(f"     - Connections: {metadata.get('statistics', {}).get('connections', 0)}")
        
        # Step 5: Authenticate with NiFi
        print("Step 4: Authenticating with NiFi...")
        token = get_nifi_token()
        print("  ✅ Authentication successful")
        
        # Step 6: Get root process group
        print("Step 5: Getting root process group...")
        root_pg_id = get_root_process_group_id(token)
        print(f"  ✅ Root PG ID: {root_pg_id}")
        
        # Step 7: Create pre-rollback backup
        print("Step 6: Creating pre-rollback backup...")
        from datetime import datetime
        pre_backup_time = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        print(f"  ℹ️  Pre-rollback backup timestamp: {pre_backup_time}")
        print("  ⚠️  Note: Implement backup before rollback in production!")
        
        # Step 8: Stop all processors (safety measure)
        print("Step 7: Stopping all processors...")
        print("  ⚠️  This will stop all running processors")
        print("  ℹ️  Implement this in production for safe rollback")
        # stopped_count = stop_all_processors(token, root_pg_id)
        # print(f"  ✅ Stopped {stopped_count} processors")
        
        # Step 9: Display rollback plan
        print("")
        print("=" * 60)
        print("🔄 ROLLBACK PLAN")
        print("=" * 60)
        print(f"Source Backup:")
        print(f"  - Date: {BACKUP_DATE}")
        print(f"  - Time: {BACKUP_TIME}")
        print(f"  - Path: {backup_path}")
        print("")
        print(f"Target NiFi:")
        print(f"  - Host: {NIFI_HOST}")
        print(f"  - Root PG: {root_pg_id}")
        print("")
        print("Components to restore:")
        stats = metadata.get('statistics', {})
        print(f"  - {stats.get('processors', 0)} Processors")
        print(f"  - {stats.get('connections', 0)} Connections")
        print(f"  - {stats.get('process_groups', 0)} Process Groups")
        print(f"  - {stats.get('input_ports', 0)} Input Ports")
        print(f"  - {stats.get('output_ports', 0)} Output Ports")
        print("")
        print("=" * 60)
        print("")
        print("⚠️  IMPORTANT: NiFi Rollback Requires Manual Steps")
        print("")
        print("This script downloads the backup, but NiFi doesn't have")
        print("a simple 'restore' API. To complete the rollback:")
        print("")
        print("Option 1: Using NiFi UI (Recommended)")
        print("  1. Stop all processors in NiFi UI")
        print("  2. Go to the root canvas")
        print("  3. Right-click → Upload → Select flow.json.gz")
        print("  4. Review changes and merge/replace as needed")
        print("  5. Start processors")
        print("")
        print("Option 2: Using NiFi Registry")
        print("  1. Upload backup to NiFi Registry")
        print("  2. Use version control to rollback")
        print("")
        print("Option 3: Programmatic (Advanced)")
        print("  1. Stop all processors via API")
        print("  2. Delete all components via API")
        print("  3. Upload new flow definition")
        print("  4. Start processors via API")
        print("")
        print(f"Backup file downloaded to: /tmp/nifi-rollback-{BACKUP_DATE}-{BACKUP_TIME}.json")
        print("=" * 60)
        
        # Save flow to temp file for manual upload
        output_file = f"/tmp/nifi-rollback-{BACKUP_DATE}-{BACKUP_TIME}.json"
        with open(output_file, 'wb') as f:
            f.write(flow_json)
        print(f"✅ Backup saved locally: {output_file}")
        
        print("")
        print("=" * 60)
        print("✅ ROLLBACK PREPARATION COMPLETED")
        print("   📄 Backup downloaded and ready")
        print("   ⚠️  Manual steps required (see above)")
        print("=" * 60)
        
        g.close()
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: Cannot connect to NiFi at {NIFI_HOST}")
        print(f"   Details: {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()