#!/usr/bin/env python3
"""
NiFi Automated Rollback Script
Restores a NiFi flow from backup and uploads directly to NiFi
Usage: 
  BACKUP_DATE=YYYY-MM-DD BACKUP_TIME=HH-MM-UTC python rollback_nifi_automated.py
"""

import os
import sys
import json
import gzip
import requests
import time
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
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'medalizaidi/nifi-jar-automation-option2')
BACKUP_BRANCH = os.environ.get('BACKUP_BRANCH', 'main')
BACKUP_FOLDER = os.environ.get('BACKUP_FOLDER', 'nifi-backups')

# Pipeline parameters (from CircleCI)
BACKUP_DATE = os.environ.get('BACKUP_DATE', '')  # Format: YYYY-MM-DD
BACKUP_TIME = os.environ.get('BACKUP_TIME', '')  # Format: HH-MM-UTC

# Rollback settings
AUTO_CONFIRM = os.environ.get('AUTO_CONFIRM', 'false').lower() == 'true'
STOP_PROCESSORS = os.environ.get('STOP_PROCESSORS', 'true').lower() == 'true'
CREATE_PRE_BACKUP = os.environ.get('CREATE_PRE_BACKUP', 'true').lower() == 'true'


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


def get_process_group_details(token, process_group_id):
    """Get process group details including version"""
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()


def get_all_components(token, process_group_id):
    """Get all components in a process group"""
    url = f"{NIFI_HOST}/nifi-api/flow/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers, verify=False, timeout=30)
    response.raise_for_status()
    return response.json()['processGroupFlow']['flow']


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
    return response.json()


def stop_all_processors(token, process_group_id):
    """Stop all processors in the process group recursively"""
    print("  🛑 Stopping all processors...")
    
    flow = get_all_components(token, process_group_id)
    stopped_count = 0
    
    # Stop processors in this group
    processors = flow.get('processors', [])
    for processor in processors:
        if processor['status']['runStatus'] in ['Running', 'Validating']:
            try:
                stop_processor(token, processor['id'], processor['revision']['version'])
                stopped_count += 1
                print(f"     Stopped: {processor['component']['name']}")
            except Exception as e:
                print(f"     Warning: Could not stop {processor['component']['name']}: {e}")
    
    # Recursively stop processors in child groups
    child_groups = flow.get('processGroups', [])
    for child_group in child_groups:
        stopped_count += stop_all_processors(token, child_group['id'])
    
    return stopped_count


def delete_component(token, component_type, component_id, version):
    """Delete a component from NiFi"""
    url = f"{NIFI_HOST}/nifi-api/{component_type}/{component_id}"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'version': version}
    
    response = requests.delete(url, headers=headers, params=params, verify=False, timeout=30)
    response.raise_for_status()


def delete_all_components(token, process_group_id):
    """Delete all components from a process group"""
    print("  🗑️  Deleting existing components...")
    
    flow = get_all_components(token, process_group_id)
    deleted_count = 0
    
    # Delete in order: connections, processors, child process groups, ports, funnels
    
    # 1. Delete connections first
    for connection in flow.get('connections', []):
        try:
            delete_component(token, 'connections', connection['id'], connection['revision']['version'])
            deleted_count += 1
            print(f"     Deleted connection: {connection['id'][:8]}...")
        except Exception as e:
            print(f"     Warning: Could not delete connection: {e}")
    
    # 2. Delete processors
    for processor in flow.get('processors', []):
        try:
            delete_component(token, 'processors', processor['id'], processor['revision']['version'])
            deleted_count += 1
            print(f"     Deleted processor: {processor['component']['name']}")
        except Exception as e:
            print(f"     Warning: Could not delete processor: {e}")
    
    # 3. Delete input ports
    for port in flow.get('inputPorts', []):
        try:
            delete_component(token, 'input-ports', port['id'], port['revision']['version'])
            deleted_count += 1
            print(f"     Deleted input port: {port['component']['name']}")
        except Exception as e:
            print(f"     Warning: Could not delete input port: {e}")
    
    # 4. Delete output ports
    for port in flow.get('outputPorts', []):
        try:
            delete_component(token, 'output-ports', port['id'], port['revision']['version'])
            deleted_count += 1
            print(f"     Deleted output port: {port['component']['name']}")
        except Exception as e:
            print(f"     Warning: Could not delete output port: {e}")
    
    # 5. Delete funnels
    for funnel in flow.get('funnels', []):
        try:
            delete_component(token, 'funnels', funnel['id'], funnel['revision']['version'])
            deleted_count += 1
            print(f"     Deleted funnel")
        except Exception as e:
            print(f"     Warning: Could not delete funnel: {e}")
    
    # 6. Delete child process groups (recursive)
    for child_group in flow.get('processGroups', []):
        try:
            # First delete contents of child group
            delete_all_components(token, child_group['id'])
            # Then delete the group itself
            delete_component(token, 'process-groups', child_group['id'], child_group['revision']['version'])
            deleted_count += 1
            print(f"     Deleted process group: {child_group['component']['name']}")
        except Exception as e:
            print(f"     Warning: Could not delete process group: {e}")
    
    print(f"  ✅ Deleted {deleted_count} components")
    return deleted_count


def import_process_group_recursively(token, parent_pg_id, pg_data):
    """Recursively import a process group and all its contents"""
    
    # Create the process group
    import_url = f"{NIFI_HOST}/nifi-api/process-groups/{parent_pg_id}/process-groups"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Get component data
    component = pg_data.get('component', pg_data)
    
    payload = {
        'revision': {'version': 0},
        'component': {
            'name': component.get('name', 'Imported Process Group'),
            'position': component.get('position', {'x': 0, 'y': 0})
        }
    }
    
    response = requests.post(import_url, headers=headers, json=payload, verify=False, timeout=60)
    
    if response.status_code not in [200, 201]:
        print(f"     ⚠️  Warning: Could not create process group '{component.get('name')}': {response.status_code}")
        return 0
    
    result = response.json()
    new_pg_id = result['id']
    print(f"     ✅ Created process group: {component.get('name')} (ID: {new_pg_id[:8]}...)")
    
    imported = 1
    
    # Now import contents of this process group
    contents = pg_data.get('contents', component.get('contents', {}))
    
    if not contents:
        print(f"        ℹ️  Process group is empty")
        return imported
    
    # Import processors in this group
    for processor in contents.get('processors', []):
        try:
            proc_url = f"{NIFI_HOST}/nifi-api/process-groups/{new_pg_id}/processors"
            proc_component = processor.get('component', processor)
            
            proc_payload = {
                'revision': {'version': 0},
                'component': proc_component
            }
            
            proc_response = requests.post(proc_url, headers=headers, json=proc_payload, verify=False, timeout=60)
            if proc_response.status_code in [200, 201]:
                imported += 1
                print(f"        ✅ Imported processor: {proc_component.get('name', 'Unknown')}")
            else:
                print(f"        ⚠️  Warning: Could not import processor '{proc_component.get('name')}': {proc_response.status_code}")
                print(f"           Response: {proc_response.text[:200]}")
        except Exception as e:
            print(f"        ⚠️  Error importing processor: {e}")
    
    # Import connections in this group
    for connection in contents.get('connections', []):
        try:
            conn_url = f"{NIFI_HOST}/nifi-api/process-groups/{new_pg_id}/connections"
            conn_component = connection.get('component', connection)
            
            conn_payload = {
                'revision': {'version': 0},
                'component': conn_component
            }
            
            conn_response = requests.post(conn_url, headers=headers, json=conn_payload, verify=False, timeout=60)
            if conn_response.status_code in [200, 201]:
                imported += 1
                print(f"        ✅ Imported connection")
            else:
                print(f"        ⚠️  Warning: Could not import connection: {conn_response.status_code}")
        except Exception as e:
            print(f"        ⚠️  Error importing connection: {e}")
    
    # Import input ports
    for port in contents.get('inputPorts', []):
        try:
            port_url = f"{NIFI_HOST}/nifi-api/process-groups/{new_pg_id}/input-ports"
            port_component = port.get('component', port)
            
            port_payload = {
                'revision': {'version': 0},
                'component': port_component
            }
            
            port_response = requests.post(port_url, headers=headers, json=port_payload, verify=False, timeout=60)
            if port_response.status_code in [200, 201]:
                imported += 1
                print(f"        ✅ Imported input port: {port_component.get('name', 'Unknown')}")
            else:
                print(f"        ⚠️  Warning: Could not import input port: {port_response.status_code}")
        except Exception as e:
            print(f"        ⚠️  Error importing input port: {e}")
    
    # Import output ports
    for port in contents.get('outputPorts', []):
        try:
            port_url = f"{NIFI_HOST}/nifi-api/process-groups/{new_pg_id}/output-ports"
            port_component = port.get('component', port)
            
            port_payload = {
                'revision': {'version': 0},
                'component': port_component
            }
            
            port_response = requests.post(port_url, headers=headers, json=port_payload, verify=False, timeout=60)
            if port_response.status_code in [200, 201]:
                imported += 1
                print(f"        ✅ Imported output port: {port_component.get('name', 'Unknown')}")
            else:
                print(f"        ⚠️  Warning: Could not import output port: {port_response.status_code}")
        except Exception as e:
            print(f"        ⚠️  Error importing output port: {e}")
    
    # Import funnels
    for funnel in contents.get('funnels', []):
        try:
            funnel_url = f"{NIFI_HOST}/nifi-api/process-groups/{new_pg_id}/funnels"
            funnel_component = funnel.get('component', funnel)
            
            funnel_payload = {
                'revision': {'version': 0},
                'component': funnel_component
            }
            
            funnel_response = requests.post(funnel_url, headers=headers, json=funnel_payload, verify=False, timeout=60)
            if funnel_response.status_code in [200, 201]:
                imported += 1
                print(f"        ✅ Imported funnel")
            else:
                print(f"        ⚠️  Warning: Could not import funnel: {funnel_response.status_code}")
        except Exception as e:
            print(f"        ⚠️  Error importing funnel: {e}")
    
    # Recursively import child process groups
    for child_pg in contents.get('processGroups', []):
        try:
            child_imported = import_process_group_recursively(token, new_pg_id, child_pg)
            imported += child_imported
        except Exception as e:
            print(f"        ⚠️  Error importing child process group: {e}")
    
    return imported


def upload_flow_to_nifi(token, process_group_id, flow_json):
    """Upload flow snapshot to NiFi by importing all components"""
    
    # Parse the flow JSON
    try:
        flow_data = json.loads(flow_json)
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid flow JSON: {e}")
    
    print("  📤 Uploading flow to NiFi...")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Extract components from the flow
    flow_contents = flow_data.get('flowContents', flow_data)
    
    # Import each component type
    imported = 0
    
    # Import process groups (recursively with their contents)
    print("  📥 Importing process groups and their contents...")
    for pg in flow_contents.get('processGroups', []):
        try:
            pg_imported = import_process_group_recursively(token, process_group_id, pg)
            imported += pg_imported
        except Exception as e:
            print(f"     ⚠️  Error importing process group: {e}")
    
    # Import root-level processors
    print("  📥 Importing root-level processors...")
    for processor in flow_contents.get('processors', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/processors"
            proc_component = processor.get('component', processor)
            
            payload = {
                'revision': {'version': 0},
                'component': proc_component
            }
            
            response = requests.post(import_url, headers=headers, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported processor: {proc_component.get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import processor: {response.status_code}")
                print(f"        Response: {response.text[:200]}")
        except Exception as e:
            print(f"     ⚠️  Error importing processor: {e}")
    
    # Import root-level connections
    print("  📥 Importing root-level connections...")
    for connection in flow_contents.get('connections', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/connections"
            conn_component = connection.get('component', connection)
            
            payload = {
                'revision': {'version': 0},
                'component': conn_component
            }
            
            response = requests.post(import_url, headers=headers, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported connection")
            else:
                print(f"     ⚠️  Warning: Could not import connection: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Error importing connection: {e}")
    
    # Import root-level ports
    print("  📥 Importing root-level ports...")
    for port in flow_contents.get('inputPorts', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/input-ports"
            port_component = port.get('component', port)
            
            payload = {
                'revision': {'version': 0},
                'component': port_component
            }
            
            response = requests.post(import_url, headers=headers, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported input port: {port_component.get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import input port: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Error importing input port: {e}")
    
    for port in flow_contents.get('outputPorts', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/output-ports"
            port_component = port.get('component', port)
            
            payload = {
                'revision': {'version': 0},
                'component': port_component
            }
            
            response = requests.post(import_url, headers=headers, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported output port: {port_component.get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import output port: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Error importing output port: {e}")
    
    print(f"  ✅ Total imported: {imported} component(s)")
    
    if imported == 0:
        print("  ℹ️  Note: Backup appears to be empty (no components to import)")
    
    return {'imported': imported}
    """Upload flow snapshot to NiFi by replacing the process group content"""
    
    # Parse the flow JSON
    try:
        flow_data = json.loads(flow_json)
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid flow JSON: {e}")
    
    print("  📤 Uploading flow to NiFi...")
    
    # Get current process group to get the version
    pg_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}"
    headers = {'Authorization': f'Bearer {token}'}
    
    pg_response = requests.get(pg_url, headers=headers, verify=False, timeout=30)
    pg_response.raise_for_status()
    pg_data = pg_response.json()
    
    current_version = pg_data['revision']['version']
    
    # Method 1: Try to replace flow using the replace endpoint
    # This uploads the flow contents into the root process group
    print("  📥 Importing flow components...")
    
    # Extract components from the flow
    flow_contents = flow_data.get('flowContents', flow_data)
    
    # Import each component type
    imported = 0
    
    # Import process groups
    for pg in flow_contents.get('processGroups', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/process-groups"
            headers_json = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'revision': {
                    'version': 0
                },
                'component': pg.get('component', pg)
            }
            
            response = requests.post(import_url, headers=headers_json, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported process group: {pg.get('component', {}).get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import process group: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Warning: Error importing process group: {e}")
    
    # Import processors
    for processor in flow_contents.get('processors', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/processors"
            headers_json = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'revision': {
                    'version': 0
                },
                'component': processor.get('component', processor)
            }
            
            response = requests.post(import_url, headers=headers_json, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported processor: {processor.get('component', {}).get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import processor: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Warning: Error importing processor: {e}")
    
    # Import connections
    for connection in flow_contents.get('connections', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/connections"
            headers_json = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'revision': {
                    'version': 0
                },
                'component': connection.get('component', connection)
            }
            
            response = requests.post(import_url, headers=headers_json, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported connection")
            else:
                print(f"     ⚠️  Warning: Could not import connection: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Warning: Error importing connection: {e}")
    
    # Import input ports
    for port in flow_contents.get('inputPorts', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/input-ports"
            headers_json = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'revision': {
                    'version': 0
                },
                'component': port.get('component', port)
            }
            
            response = requests.post(import_url, headers=headers_json, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported input port: {port.get('component', {}).get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import input port: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Warning: Error importing input port: {e}")
    
    # Import output ports
    for port in flow_contents.get('outputPorts', []):
        try:
            import_url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/output-ports"
            headers_json = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'revision': {
                    'version': 0
                },
                'component': port.get('component', port)
            }
            
            response = requests.post(import_url, headers=headers_json, json=payload, verify=False, timeout=60)
            if response.status_code in [200, 201]:
                imported += 1
                print(f"     ✅ Imported output port: {port.get('component', {}).get('name', 'Unknown')}")
            else:
                print(f"     ⚠️  Warning: Could not import output port: {response.status_code}")
        except Exception as e:
            print(f"     ⚠️  Warning: Error importing output port: {e}")
    
    print(f"  ✅ Imported {imported} component(s)")
    
    if imported == 0:
        print("  ℹ️  Note: Backup appears to be empty (no components to import)")
    
    return {'imported': imported}


def backup_current_flow(token, process_group_id):
    """Create a backup of current flow before rollback"""
    url = f"{NIFI_HOST}/nifi-api/process-groups/{process_group_id}/download"
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get(url, headers=headers, verify=False, timeout=120)
    response.raise_for_status()
    
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    backup_file = f"/tmp/pre-rollback-backup-{timestamp}.json"
    
    with open(backup_file, 'wb') as f:
        f.write(response.content)
    
    print(f"  ✅ Pre-rollback backup saved: {backup_file}")
    return backup_file


def list_available_backups(repo, backup_folder):
    """List all available backups"""
    try:
        contents = repo.get_contents(backup_folder, ref=BACKUP_BRANCH)
        date_folders = [item for item in contents if item.type == "dir"]
        
        backups = []
        for date_folder in date_folders:
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
        
        # Try to decompress flow - handle both gzipped and plain JSON
        try:
            flow_json = gzip.decompress(flow_content)
            print(f"  ℹ️  File was gzip compressed")
        except gzip.BadGzipFile:
            # File is not gzipped, use as-is
            flow_json = flow_content
            print(f"  ℹ️  File is plain JSON (not compressed)")
        
        # Validate it's valid JSON
        try:
            json.loads(flow_json)
        except json.JSONDecodeError as e:
            raise Exception(f"Downloaded file is not valid JSON: {e}")
        
        return flow_json, metadata
    except Exception as e:
        raise Exception(f"Failed to download backup: {e}")


def main():
    print("=" * 60)
    print("    NiFi Automated Rollback Script")
    print("=" * 60)
    print("")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='NiFi Automated Rollback Script')
    parser.add_argument('--list-only', action='store_true', 
                       help='Only list available backups')
    parser.add_argument('--skip-stop', action='store_true',
                       help='Skip stopping processors (dangerous!)')
    parser.add_argument('--skip-backup', action='store_true',
                       help='Skip creating pre-rollback backup')
    args = parser.parse_args()
    
    # Validate GitHub variables
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
        
        try:
            repo = g.get_repo(GITHUB_REPO)
            print("  ✅ Connected successfully")
        except Exception as e:
            print(f"  ❌ Failed to access repository: {GITHUB_REPO}")
            print(f"  Error: {e}")
            print("")
            print("Check GITHUB_REPO format: owner/repo-name")
            g.close()
            sys.exit(1)
        
        # Step 2: List or rollback
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
            for i, backup in enumerate(backups[:10], 1):
                print(f"  {i}. {backup['date']} {backup['time']}")
            
            if len(backups) > 10:
                print(f"  ... and {len(backups) - 10} more")
            
            print("")
            if args.list_only:
                print("=" * 60)
                print("✅ BACKUP LIST COMPLETED")
                print("=" * 60)
                g.close()
                sys.exit(0)
            
            print("=" * 60)
            print("❌ ERROR: No backup date specified")
            print("")
            print("Set environment variables:")
            print("  export BACKUP_DATE='YYYY-MM-DD'")
            print("  export BACKUP_TIME='HH-MM-UTC'")
            print("=" * 60)
            g.close()
            sys.exit(1)
        
        # Validate time parameter
        if not BACKUP_TIME:
            print("  ❌ BACKUP_TIME not specified")
            sys.exit(1)
        
        backup_path = f"{BACKUP_FOLDER}/{BACKUP_DATE}/{BACKUP_TIME}"
        
        # Step 3: Download backup
        print(f"Step 2: Downloading backup from {BACKUP_DATE} {BACKUP_TIME}...")
        print(f"  📁 Backup path: {backup_path}")
        
        flow_json, metadata = download_backup(repo, backup_path)
        print(f"  ✅ Downloaded backup ({len(flow_json):,} bytes)")
        print(f"  📊 Backup metadata:")
        print(f"     - Timestamp: {metadata.get('backup_timestamp', 'N/A')}")
        print(f"     - Processors: {metadata.get('statistics', {}).get('processors', 0)}")
        print(f"     - Connections: {metadata.get('statistics', {}).get('connections', 0)}")
        print("")
        
        # Step 4: Authenticate with NiFi
        print("Step 3: Authenticating with NiFi...")
        token = get_nifi_token()
        print("  ✅ Authentication successful")
        print("")
        
        # Step 5: Get root process group
        print("Step 4: Getting root process group...")
        root_pg_id = get_root_process_group_id(token)
        print(f"  ✅ Root PG ID: {root_pg_id}")
        print("")
        
        # Step 6: Create pre-rollback backup
        if CREATE_PRE_BACKUP and not args.skip_backup:
            print("Step 5: Creating pre-rollback backup...")
            backup_file = backup_current_flow(token, root_pg_id)
            print("")
        
        # Step 7: Stop processors
        if STOP_PROCESSORS and not args.skip_stop:
            print("Step 6: Stopping all processors...")
            stopped_count = stop_all_processors(token, root_pg_id)
            print(f"  ✅ Stopped {stopped_count} processor(s)")
            print("  ⏳ Waiting 5 seconds for processors to stop...")
            time.sleep(5)
            print("")
        
        # Step 8: Confirmation
        print("=" * 60)
        print("⚠️  FINAL CONFIRMATION")
        print("=" * 60)
        print("")
        print("You are about to:")
        print(f"  1. DELETE all components from {NIFI_HOST}")
        print(f"  2. UPLOAD backup from {BACKUP_DATE} {BACKUP_TIME}")
        print("")
        print("This operation CANNOT be undone!")
        print("")
        
        if not AUTO_CONFIRM:
            try:
                confirm = input("Type 'DELETE AND REPLACE' to proceed: ")
                if confirm != "DELETE AND REPLACE":
                    print("")
                    print("❌ Rollback cancelled")
                    sys.exit(0)
            except (KeyboardInterrupt, EOFError):
                print("")
                print("❌ Rollback cancelled")
                sys.exit(0)
        else:
            print("⚠️  AUTO_CONFIRM=true, skipping manual confirmation")
        
        print("")
        
        # Step 9: Delete existing components
        print("Step 7: Deleting existing flow...")
        delete_all_components(token, root_pg_id)
        print("")
        
        # Step 10: Upload new flow
        print("Step 8: Uploading backup to NiFi...")
        result = upload_flow_to_nifi(token, root_pg_id, flow_json)
        print("")
        
        # Save artifacts
        output_file = f"/tmp/nifi-rollback-{BACKUP_DATE}-{BACKUP_TIME}.json"
        with open(output_file, 'wb') as f:
            f.write(flow_json)
        
        metadata_output = "/tmp/rollback-metadata.json"
        with open(metadata_output, 'w') as f:
            json.dump({
                'backup_date': BACKUP_DATE,
                'backup_time': BACKUP_TIME,
                'backup_path': backup_path,
                'nifi_host': NIFI_HOST,
                'root_process_group_id': root_pg_id,
                'rolled_back_at': datetime.utcnow().isoformat() + 'Z',
                'backup_metadata': metadata,
                'automated': True
            }, f, indent=2)
        
        print("=" * 60)
        print("✅ ROLLBACK COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("")
        print(f"  📅 Restored from: {BACKUP_DATE} {BACKUP_TIME}")
        print(f"  🔗 NiFi Host: {NIFI_HOST}")
        print("")
        print("Next steps:")
        print("  1. Go to NiFi UI and verify the flow")
        print("  2. Start processors manually")
        print("  3. Monitor for any issues")
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