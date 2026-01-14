#!/usr/bin/env python3
"""
Script to dynamically add JARs to Dockerfile during build time.
Scans JAR manifest files and injects download commands into Dockerfile.
"""

import os
import json
from pathlib import Path


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


def generate_dockerfile_additions(jars_dict):
    """Generate RUN commands for downloading JARs"""
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
    """Update Dockerfile with JAR download commands"""
    # Scan for JARs
    requested_jars = scan_jars_folder(jars_folder)
    
    if not requested_jars:
        print("No JARs found to add")
        return
    
    print(f"Found {len(requested_jars)} JARs to add:")
    for jar_name in requested_jars:
        print(f"  - {jar_name}")
    
    # Read current Dockerfile
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Generate additions
    additions = generate_dockerfile_additions(requested_jars)
    
    # Find insertion point (before USER 1000 or marker)
    if '# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE' in content:
        # Insert before marker
        marker = '# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE'
        content = content.replace(marker, f"{additions}\n{marker}")
    elif 'USER 1000' in content:
        # Insert before USER 1000
        lines = content.split('\n')
        insert_index = next((i for i, line in enumerate(lines) if 'USER 1000' in line), len(lines))
        lines.insert(insert_index, additions)
        content = '\n'.join(lines)
    else:
        # Append at the end
        content += '\n' + additions
    
    # Write updated Dockerfile
    with open(dockerfile_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated Dockerfile with {len(requested_jars)} JAR(s)")


if __name__ == '__main__':
    # Get paths from arguments or use defaults
    dockerfile_path = os.environ.get('DOCKERFILE_PATH', 'Dockerfile')
    jars_folder = os.environ.get('JARS_FOLDER', 'jars')
    
    update_dockerfile(dockerfile_path, jars_folder)