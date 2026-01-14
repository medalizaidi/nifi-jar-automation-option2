#!/usr/bin/env python3
"""
Script to dynamically add ONLY NEW JARs to Dockerfile during build time.
Compares JAR manifests with existing Dockerfile entries and only adds missing JARs.
"""

import os
import re
import json
from pathlib import Path


def parse_dockerfile_jars(dockerfile_path):
    """
    Parse existing JAR downloads from Dockerfile.
    Returns set of JAR names already in Dockerfile.
    """
    existing_jars = set()
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Pattern to match curl commands downloading JARs
    # Matches: RUN curl -L "url" -o /path/to/jar.jar
    pattern = r'curl\s+-L\s+"([^"]+)"\s+.*?-o\s+([^\s\\]+\.jar)'
    
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    for url, jar_path in matches:
        jar_name = os.path.basename(jar_path)
        existing_jars.add(jar_name)
    
    return existing_jars


def scan_jars_folder(jars_folder):
    """Scan JARs folder for manifest files"""
    requested_jars = {}
    jars_path = Path(jars_folder)
    
    if not jars_path.exists():
        print(f"JARs folder not found: {jars_folder}")
        return requested_jars
    
    for manifest_file in jars_path.glob("*.json"):
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            jar_name = manifest.get('name')
            if jar_name:
                requested_jars[jar_name] = {
                    'url': manifest.get('url'),
                    'install_path': manifest.get('install_path', '/opt/nifi/nifi-current/lib/'),
                    'description': manifest.get('description', '')
                }
        except json.JSONDecodeError as e:
            print(f"Error parsing {manifest_file}: {e}")
    
    return requested_jars


def find_new_jars(existing_jars, requested_jars):
    """
    Compare existing JARs in Dockerfile with requested JARs.
    Returns dict of NEW JARs that need to be added.
    """
    new_jars = {}
    
    for jar_name, jar_info in requested_jars.items():
        if jar_name not in existing_jars:
            new_jars[jar_name] = jar_info
            print(f"  ✨ NEW: {jar_name}")
        else:
            print(f"  ✓ EXISTING: {jar_name}")
    
    return new_jars


def generate_dockerfile_additions(jars_dict):
    """Generate RUN commands for downloading JARs"""
    if not jars_dict:
        return ""
    
    additions = []
    
    for jar_name, jar_info in jars_dict.items():
        url = jar_info['url']
        install_path = jar_info['install_path'].rstrip('/')
        description = jar_info.get('description', jar_name)
        full_path = f"{install_path}/{jar_name}"
        
        addition = f"""
# Download {description}
RUN curl -L "{url}" \\
        -o {full_path} && \\
        chown 1000:1000 {full_path}
"""
        additions.append(addition)
    
    return '\n'.join(additions)


def update_dockerfile(dockerfile_path, jars_folder):
    """Update Dockerfile with ONLY NEW JAR download commands"""
    print(f"\n{'='*60}")
    print("Scanning for NEW JARs to add to Dockerfile")
    print(f"{'='*60}\n")
    
    # Parse existing JARs from Dockerfile
    existing_jars = parse_dockerfile_jars(dockerfile_path)
    print(f"Found {len(existing_jars)} existing JARs in Dockerfile:")
    for jar in sorted(existing_jars):
        print(f"  - {jar}")
    
    # Scan for requested JARs
    print(f"\nScanning JAR manifests in {jars_folder}...")
    requested_jars = scan_jars_folder(jars_folder)
    print(f"Found {len(requested_jars)} JAR manifests")
    
    # Find NEW JARs
    print(f"\nComparing manifests with Dockerfile:")
    new_jars = find_new_jars(existing_jars, requested_jars)
    
    if not new_jars:
        print(f"\n{'='*60}")
        print("✅ No new JARs to add - Dockerfile is up to date")
        print(f"{'='*60}\n")
        return
    
    print(f"\n{'='*60}")
    print(f"Found {len(new_jars)} NEW JAR(s) to add:")
    for jar_name in new_jars.keys():
        print(f"  ✨ {jar_name}")
    print(f"{'='*60}\n")
    
    # Read current Dockerfile
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Generate additions for NEW JARs only
    additions = generate_dockerfile_additions(new_jars)
    
    # Find insertion point (before USER 1000 or marker)
    if '# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE' in content:
        # Insert before marker
        marker = '# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE'
        content = content.replace(marker, f"{additions}\n{marker}")
        print(f"✅ Inserted {len(new_jars)} new JAR(s) before marker comment")
    elif 'USER 1000' in content:
        # Insert before USER 1000
        lines = content.split('\n')
        insert_index = next((i for i, line in enumerate(lines) if 'USER 1000' in line), len(lines))
        lines.insert(insert_index, additions)
        content = '\n'.join(lines)
        print(f"✅ Inserted {len(new_jars)} new JAR(s) before USER 1000")
    else:
        # Append at the end
        content += '\n' + additions
        print(f"✅ Appended {len(new_jars)} new JAR(s) to end of Dockerfile")
    
    # Write updated Dockerfile
    with open(dockerfile_path, 'w') as f:
        f.write(content)
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully updated Dockerfile with {len(new_jars)} new JAR(s)")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    # Get paths from environment or use defaults
    dockerfile_path = os.environ.get('DOCKERFILE_PATH', 'Dockerfile')
    jars_folder = os.environ.get('JARS_FOLDER', 'jars')
    
    update_dockerfile(dockerfile_path, jars_folder)