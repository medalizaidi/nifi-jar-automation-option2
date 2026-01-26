#!/usr/bin/env python3
"""
NiFi Backup Script
Backs up NiFi flow definitions and commits to GitHub
Structure: nifi-backups/YYYY-MM-DD/HH-MM-UTC/
"""

import os
import sys
import json
import requests
from datetime import datetime
from github import Github

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
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'medalizaidi/nifi-jar-automation-option2')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')


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


def export_flow(token, process_group_id):
    """Export the entire flow as JSON"""
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/download"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=120)
    response.raise_for_status()
    return response.content


def get_flow_info(token, process_group_id):
    """Get flow information for metadata"""
    url = f"{NIFI_HOST}/nifi-api/flow/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()


def commit_file_to_github(g, repo, file_path, content, commit_message):
    """Commit a file to GitHub (create or update)"""
    try:
        # Check if file exists
        existing = repo.get_contents(file_path, ref=BACKUP_BRANCH)
        repo.update_file(
            file_path,
            commit_message,
            content,
            existing.sha,
            branch=BACKUP_BRANCH
        )
        print(f"  ✅ Updated: {file_path}")
    except Exception as e:
        if "404" in str(e):
            repo.create_file(
                file_path,
                commit_message,
                content,
                branch=BACKUP_BRANCH
            )
            print(f"  ✅ Created: {file_path}")
        else:
            raise e


def main():
    print("=" * 60)
    print("         NiFi Backup Script")
    print("=" * 60)
    print("")
    
    # Validate required environment variables
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
    
    # Get current timestamp
    now = datetime.utcnow()
    date_folder = now.strftime('%Y-%m-%d')
    time_folder = now.strftime('%H-%M-UTC')
    backup_path = f"{BACKUP_FOLDER}/{date_folder}/{time_folder}"
    
    print(f"📅 Date: {date_folder}")
    print(f"🕐 Time: {time_folder}")
    print(f"📁 Backup Path: {backup_path}")
    print(f"🔗 NiFi Host: {NIFI_HOST}")
    print(f"📦 GitHub Repo: {GITHUB_REPO}")
    print("")
    
    try:
        # Step 1: Authenticate with NiFi
        print("Step 1: Authenticating with NiFi...")
        token = get_nifi_token()
        print("  ✅ Authentication successful")
        
        # Step 2: Get root process group
        print("Step 2: Getting root process group...")
        root_pg_id = get_root_process_group_id(token)
        print(f"  ✅ Root PG ID: {root_pg_id}")
        
        # Step 3: Export the flow
        print("Step 3: Exporting NiFi flow...")
        flow_content = export_flow(token, root_pg_id)
        print(f"  ✅ Flow exported ({len(flow_content):,} bytes)")
        
        # Step 4: Get flow metadata
        print("Step 4: Getting flow metadata...")
        flow_info = get_flow_info(token, root_pg_id)
        
        flow_data = flow_info.get('processGroupFlow', {}).get('flow', {})
        metadata = {
            'backup_timestamp': now.isoformat() + 'Z',
            'backup_date': date_folder,
            'backup_time': time_folder,
            'nifi_host': NIFI_HOST,
            'root_process_group_id': root_pg_id,
            'statistics': {
                'process_groups': len(flow_data.get('processGroups', [])),
                'processors': len(flow_data.get('processors', [])),
                'connections': len(flow_data.get('connections', [])),
                'input_ports': len(flow_data.get('inputPorts', [])),
                'output_ports': len(flow_data.get('outputPorts', [])),
                'funnels': len(flow_data.get('funnels', [])),
                'labels': len(flow_data.get('labels', []))
            }
        }
        print(f"  ✅ Metadata collected")
        print(f"     - Process Groups: {metadata['statistics']['process_groups']}")
        print(f"     - Processors: {metadata['statistics']['processors']}")
        print(f"     - Connections: {metadata['statistics']['connections']}")
        
        # Step 5: Commit to GitHub
        print("Step 5: Committing to GitHub...")
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        
        commit_msg = f"NiFi backup: {date_folder} {time_folder}"
        
        # Commit flow file
        commit_file_to_github(
            g, repo,
            f"{backup_path}/flow.json.gz",
            flow_content,
            commit_msg
        )
        
        # Commit metadata
        commit_file_to_github(
            g, repo,
            f"{backup_path}/metadata.json",
            json.dumps(metadata, indent=2),
            commit_msg
        )
        
        print("")
        print("=" * 60)
        print("✅ BACKUP COMPLETED SUCCESSFULLY")
        print(f"   📁 Location: {backup_path}/")
        print(f"   📄 Files: flow.json.gz, metadata.json")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: Cannot connect to NiFi at {NIFI_HOST}")
        print(f"   Details: {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
