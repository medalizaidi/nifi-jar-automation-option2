#!/usr/bin/env python3
"""
Script to update ECS task definition with new Docker image tag.
Creates a PR with the updated task definition.
"""

import os
import re
from datetime import datetime
from github import Github


def update_task_definition_content(task_def_path: str, image_tag: str, aws_account_id: str, aws_region: str) -> str:
    """
    Update the ECS task definition with the new image tag.
    """
    with open(task_def_path, 'r') as f:
        content = f.read()
    
    # Pattern to match the image line in task definition
    # Looking for: "image" : "ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPO:TAG"
    ecr_pattern = r'("image"\s*:\s*")(\d+\.dkr\.ecr\.[^"]+\.amazonaws\.com/apache-nifi-with-custom-jars-repo):([^"]+)(")'
    
    def replace_image(match):
        prefix = match.group(1)
        ecr_url = match.group(2)
        suffix = match.group(4)
        return f'{prefix}{ecr_url}:{image_tag}{suffix}'
    
    updated_content = re.sub(ecr_pattern, replace_image, content)
    
    # Also update any explicit image references
    simple_pattern = rf'({aws_account_id}\.dkr\.ecr\.{aws_region}\.amazonaws\.com/apache-nifi-with-custom-jars-repo):[\w.-]+'
    updated_content = re.sub(
        simple_pattern,
        rf'\1:{image_tag}',
        updated_content
    )
    
    return updated_content


def get_current_image_tag(task_def_path: str) -> str:
    """
    Extract the current image tag from the task definition.
    """
    with open(task_def_path, 'r') as f:
        content = f.read()
    
    pattern = r'"image"\s*:\s*"[^"]+:([^"]+)"'
    match = re.search(pattern, content)
    
    if match:
        return match.group(1)
    return "unknown"


def create_github_pr(
    updated_content: str,
    task_def_path: str,
    image_tag: str,
    old_tag: str,
    target_branch: str
):
    """
    Create a GitHub PR with the task definition changes.
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    repo_name = os.environ.get('CIRCLE_PROJECT_REPONAME')
    repo_owner = os.environ.get('CIRCLE_PROJECT_USERNAME')
    
    if not all([github_token, repo_name, repo_owner]):
        raise ValueError("Missing required environment variables")
    
    g = Github(github_token)
    repo = g.get_repo(f"{repo_owner}/{repo_name}")
    
    # Create branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"auto/update-task-def-{image_tag}"
    
    # Get the base branch
    base_branch = repo.get_branch(target_branch)
    base_sha = base_branch.commit.sha
    
    # Create new branch
    repo.create_git_ref(
        ref=f"refs/heads/{branch_name}",
        sha=base_sha
    )
    
    # Get current file SHA
    current_file = repo.get_contents(task_def_path, ref=target_branch)
    
    # Update file in new branch
    commit_message = f"Update NiFi image to {image_tag}"
    
    repo.update_file(
        path=task_def_path,
        message=commit_message,
        content=updated_content,
        sha=current_file.sha,
        branch=branch_name
    )
    
    # Create PR
    pr_title = f"[Auto] Update NiFi Docker image to {image_tag}"
    
    pr_body = f"""## Automated Task Definition Update

This PR was automatically generated after a successful Docker image build.

### Changes
- **Previous image tag:** `{old_tag}`
- **New image tag:** `{image_tag}`

### What triggered this?
A Dockerfile change was merged, triggering:
1. ✅ Docker image build
2. ✅ Push to ECR
3. 📝 This PR to update the task definition

### After Approval
Once this PR is merged:
1. Run `terraform plan` to verify the changes
2. Apply the Terraform changes to update the ECS service

### Rollback
If issues occur, revert this PR or update the image tag to the previous version: `{old_tag}`
"""
    
    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=target_branch
    )
    
    # Add labels
    try:
        pr.add_to_labels("automated", "infrastructure", "ecs")
    except Exception:
        pass
    
    print(f"Created PR #{pr.number}: {pr.html_url}")
    return pr


def main():
    # Get configuration from environment
    task_def_path = os.environ.get('TASK_DEF_PATH', 'workload/mfx-aggre-data-platform/ecs_task_definition.tf')
    target_branch = os.environ.get('TARGET_BRANCH', 'master')
    aws_account_id = os.environ.get('AWS_ACCOUNT_ID')
    aws_region = os.environ.get('AWS_REGION', 'ap-northeast-1')
    
    # Read image tag from workspace
    image_tag_file = '/tmp/image-tag.txt'
    if os.path.exists(image_tag_file):
        with open(image_tag_file, 'r') as f:
            image_tag = f.read().strip()
    else:
        # Fallback to environment variable
        image_tag = os.environ.get('IMAGE_TAG', os.environ.get('CIRCLE_SHA1', '')[:7])
    
    if not image_tag:
        raise ValueError("No image tag provided")
    
    print(f"Updating task definition: {task_def_path}")
    print(f"New image tag: {image_tag}")
    
    # Get current tag for comparison
    old_tag = get_current_image_tag(task_def_path)
    print(f"Current image tag: {old_tag}")
    
    if old_tag == image_tag:
        print("Image tag is already up to date. Skipping PR creation.")
        return
    
    # Update task definition content
    updated_content = update_task_definition_content(
        task_def_path=task_def_path,
        image_tag=image_tag,
        aws_account_id=aws_account_id,
        aws_region=aws_region
    )
    
    # Create GitHub PR
    pr = create_github_pr(
        updated_content=updated_content,
        task_def_path=task_def_path,
        image_tag=image_tag,
        old_tag=old_tag,
        target_branch=target_branch
    )
    
    print(f"Successfully created PR: {pr.html_url}")


if __name__ == '__main__':
    main()
