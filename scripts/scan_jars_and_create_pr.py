#!/usr/bin/env python3
"""
Script to scan JARs folder, compare with existing Dockerfile entries,
and create a PR to add new JAR download commands.
"""

import os
import re
import json
from pathlib import Path
from github import Github, Auth
from datetime import datetime


def parse_dockerfile_jars(dockerfile_path: str) -> dict:
    """
    Parse existing JAR downloads from Dockerfile.
    Returns dict with jar_name -> download_url mapping.
    """
    existing_jars = {}
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    # Pattern to match curl commands downloading JARs
    # Matches: RUN curl -L "url" -o /path/to/jar.jar
    pattern = r'curl\s+-L\s+"([^"]+)"\s+.*?-o\s+([^\s\\]+\.jar)'
    
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    for url, jar_path in matches:
        jar_name = os.path.basename(jar_path)
        existing_jars[jar_name] = {
            'url': url,
            'path': jar_path
        }
    
    return existing_jars


def scan_jars_folder(jars_folder: str) -> dict:
    """
    Scan the JARs folder for JAR manifest files.
    Each JAR should have a corresponding .json manifest with download URL.
    
    Expected manifest format:
    {
        "name": "mysql-connector-j-9.5.0.jar",
        "url": "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar",
        "install_path": "/opt/nifi/nifi-current/lib/",
        "description": "MySQL JDBC Driver"
    }
    """
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
                    'description': manifest.get('description', ''),
                    'manifest_file': str(manifest_file)
                }
        except json.JSONDecodeError as e:
            print(f"Error parsing {manifest_file}: {e}")
    
    return requested_jars


def find_new_jars(existing_jars: dict, requested_jars: dict) -> dict:
    """
    Compare existing JARs in Dockerfile with requested JARs.
    Returns dict of new JARs that need to be added.
    """
    new_jars = {}
    
    for jar_name, jar_info in requested_jars.items():
        if jar_name not in existing_jars:
            new_jars[jar_name] = jar_info
        elif existing_jars[jar_name]['url'] != jar_info['url']:
            # JAR exists but URL is different (version update)
            jar_info['is_update'] = True
            jar_info['old_url'] = existing_jars[jar_name]['url']
            new_jars[jar_name] = jar_info
    
    return new_jars


def generate_dockerfile_additions(new_jars: dict) -> str:
    """
    Generate Dockerfile RUN commands for new JARs.
    """
    additions = []
    
    for jar_name, jar_info in new_jars.items():
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


def update_dockerfile_content(dockerfile_path: str, new_jars: dict) -> str:
    """
    Generate updated Dockerfile content with new JAR downloads.
    Inserts new JARs before the marker comment or USER 1000 line.
    """
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    additions = generate_dockerfile_additions(new_jars)
    
    # First try: Look for the marker comment
    marker_pattern = r'(# =+\n# NEW JARS WILL BE ADDED AUTOMATICALLY ABOVE THIS LINE)'
    
    if re.search(marker_pattern, content):
        updated_content = re.sub(
            marker_pattern,
            f"{additions}\n\\1",
            content
        )
    # Second try: Find the line "USER 1000" and insert before it
    elif re.search(r'(# Revert to NiFi user.*?\nUSER 1000)', content, re.DOTALL):
        user_pattern = r'(# Revert to NiFi user.*?\nUSER 1000)'
        updated_content = re.sub(
            user_pattern,
            f"{additions}\n\\1",
            content,
            flags=re.DOTALL
        )
    else:
        # Fallback: append before USER 1000 line
        lines = content.split('\n')
        insert_index = len(lines) - 1
        for i, line in enumerate(lines):
            if 'USER 1000' in line:
                insert_index = i
                break
        
        lines.insert(insert_index, additions)
        updated_content = '\n'.join(lines)
    
    return updated_content


def create_github_pr(
    new_jars: dict,
    updated_dockerfile: str,
    dockerfile_path: str,
    target_branch: str
):
    """
    Create a GitHub PR with the Dockerfile changes.
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('CIRCLE_PROJECT_REPONAME')
    repo_owner = os.environ.get('CIRCLE_PROJECT_USERNAME')

    # Debug: print environment variables
    print(f"DEBUG: GITHUB_TOKEN present: {bool(github_token)}")
    print(f"DEBUG: CIRCLE_PROJECT_REPONAME: {repo_name}")
    print(f"DEBUG: CIRCLE_PROJECT_USERNAME: {repo_owner}")

    if not all([github_token, repo_name, repo_owner]):
        missing = []
        if not github_token: missing.append('GITHUB_TOKEN')
        if not repo_name: missing.append('CIRCLE_PROJECT_REPONAME')
        if not repo_owner: missing.append('CIRCLE_PROJECT_USERNAME')
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Use new Auth.Token() method to avoid deprecation warning
    auth = Auth.Token(github_token)
    g = Github(auth=auth)

    # Try to get the repo with better error handling
    repo_full_name = f"{repo_owner}/{repo_name}"
    print(f"Attempting to access repository: {repo_full_name}")

    try:
        repo = g.get_repo(repo_full_name)
        print(f"Successfully accessed repository: {repo_full_name}")
    except Exception as e:
        print(f"ERROR: Failed to access repository '{repo_full_name}'")
        print(f"ERROR: {str(e)}")
        print("\nPossible causes:")
        print("1. Repository name is incorrect")
        print("2. GitHub token doesn't have access to this repository")
        print("3. GitHub token needs 'repo' scope")
        print(f"\nVerify the repository exists: https://github.com/{repo_full_name}")
        raise
    
    # Create branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jar_names = list(new_jars.keys())
    branch_name = f"auto/add-jars-{timestamp}"
    
    # Get the base branch
    base_branch = repo.get_branch(target_branch)
    base_sha = base_branch.commit.sha
    
    # Create new branch
    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base_sha
    )
    
    # Get current file to get its SHA
    try:
        current_file = repo.get_contents(dockerfile_path, ref=target_branch)
        file_sha = current_file.sha
    except Exception:
        file_sha = None
    
    # Create/Update file in new branch
    commit_message = f"Add new JAR(s): {', '.join(jar_names)} [skip ci]"
    
    if file_sha:
        repo.update_file(
            path=dockerfile_path,
            message=commit_message,
            content=updated_dockerfile,
            sha=file_sha,
            branch=branch_name
        )
    else:
        repo.create_file(
            path=dockerfile_path,
            message=commit_message,
            content=updated_dockerfile,
            branch=branch_name
        )
    
    # Create PR
    pr_title = f"[Auto] Add JAR(s): {', '.join(jar_names)}"
    
    pr_body = f"""## Automated JAR Addition

This PR was automatically generated by the CI pipeline.

### New JARs to be added:

| JAR Name | Description | URL |
|----------|-------------|-----|
"""
    
    for jar_name, jar_info in new_jars.items():
        description = jar_info.get('description', 'N/A')
        url = jar_info.get('url', 'N/A')
        is_update = jar_info.get('is_update', False)
        status = "🔄 UPDATE" if is_update else "✨ NEW"
        pr_body += f"| {jar_name} | {description} ({status}) | [Link]({url}) |\n"
    
    pr_body += """
### Checklist
- [ ] JAR URL is valid and accessible
- [ ] JAR is compatible with NiFi version
- [ ] Security review completed (if required)

### After Approval
Once this PR is merged, the pipeline will automatically:
1. Build the new Docker image
2. Push to ECR
3. Create a PR to update the ECS task definition
"""
    
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=target_branch
    )
    
    # Add labels if they exist
    try:
        pr.add_to_labels("automated", "jar-update")
    except Exception:
        pass  # Labels might not exist
    
    print(f"Created PR #{pr.number}: {pr.html_url}")
    return pr


def save_diff_report(existing_jars: dict, requested_jars: dict, new_jars: dict):
    """
    Save a JSON report of the JAR diff.
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'existing_jars': list(existing_jars.keys()),
        'requested_jars': list(requested_jars.keys()),
        'new_jars': {
            name: {
                'url': info['url'],
                'description': info.get('description', ''),
                'is_update': info.get('is_update', False)
            }
            for name, info in new_jars.items()
        },
        'action_required': len(new_jars) > 0
    }
    
    report_path = '/tmp/jar-diff-report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Diff report saved to {report_path}")
    return report


def main():
    # Get paths from environment
    dockerfile_path = os.environ.get('DOCKERFILE_PATH', 'workload/mfx-aggre-data-platform/custom_nifi/Dockerfile')
    jars_folder = os.environ.get('JARS_FOLDER', 'workload/mfx-aggre-data-platform/custom_nifi/jars')
    target_branch = os.environ.get('TARGET_BRANCH', 'main')
    
    print(f"Scanning Dockerfile: {dockerfile_path}")
    print(f"Scanning JARs folder: {jars_folder}")
    
    # Parse existing JARs from Dockerfile
    existing_jars = parse_dockerfile_jars(dockerfile_path)
    print(f"Found {len(existing_jars)} existing JARs in Dockerfile")
    for jar_name in existing_jars:
        print(f"  - {jar_name}")
    
    # Scan JARs folder for requested JARs
    requested_jars = scan_jars_folder(jars_folder)
    print(f"Found {len(requested_jars)} JAR manifests in {jars_folder}")
    for jar_name in requested_jars:
        print(f"  - {jar_name}")
    
    # Find new JARs
    new_jars = find_new_jars(existing_jars, requested_jars)
    print(f"Found {len(new_jars)} new/updated JARs to add")
    
    # Save diff report
    save_diff_report(existing_jars, requested_jars, new_jars)
    
    if not new_jars:
        print("No new JARs to add. Exiting.")
        return
    
    # Generate updated Dockerfile
    updated_dockerfile = update_dockerfile_content(dockerfile_path, new_jars)
    
    # Create GitHub PR
    try:
        pr = create_github_pr(
            new_jars=new_jars,
            updated_dockerfile=updated_dockerfile,
            dockerfile_path=dockerfile_path,
            target_branch=target_branch
        )
        print(f"Successfully created PR: {pr.html_url}")
    except Exception as e:
        print(f"Error creating PR: {e}")
        # Save updated Dockerfile locally for debugging
        with open('/tmp/updated-Dockerfile', 'w') as f:
            f.write(updated_dockerfile)
        print("Updated Dockerfile saved to /tmp/updated-Dockerfile")
        raise


if __name__ == '__main__':
    main()
