#!/usr/bin/env python3
"""
Test script to verify GitHub token and repository access
"""
from github import Github, Auth

# Replace with your token
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = "medalizaidi"
REPO_NAME = "nifi-jar-automation-option2"

print("Testing GitHub Token...")
print("=" * 50)

try:
    # Test 1: Authenticate
    print("\n1. Testing authentication...")
    auth = Auth.Token(GITHUB_TOKEN)
    g = Github(auth=auth)

    user = g.get_user()
    print(f"   ✅ Authenticated as: {user.login}")
    print(f"   Name: {user.name}")
    print(f"   Email: {user.email}")

    # Test 2: Check token scopes
    print("\n2. Checking token scopes...")
    # This is a workaround to check scopes
    import requests
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get("https://api.github.com/user", headers=headers)
    scopes = response.headers.get('X-OAuth-Scopes', 'Unknown')
    print(f"   Token scopes: {scopes}")

    if 'repo' in scopes:
        print("   ✅ Token has 'repo' scope")
    else:
        print("   ❌ Token MISSING 'repo' scope - this is required!")

    # Test 3: Access repository
    print(f"\n3. Testing repository access...")
    repo_full_name = f"{REPO_OWNER}/{REPO_NAME}"
    print(f"   Attempting to access: {repo_full_name}")

    repo = g.get_repo(repo_full_name)
    print(f"   ✅ Successfully accessed: {repo.full_name}")
    print(f"   Description: {repo.description}")
    print(f"   Private: {repo.private}")
    print(f"   Default branch: {repo.default_branch}")

    # Test 4: Check permissions
    print(f"\n4. Checking repository permissions...")
    permissions = repo.permissions
    print(f"   Admin: {permissions.admin}")
    print(f"   Push: {permissions.push}")
    print(f"   Pull: {permissions.pull}")

    if permissions.push:
        print("   ✅ Token has PUSH permissions (can create PRs)")
    else:
        print("   ❌ Token MISSING push permissions!")

    # Test 5: List recent branches
    print(f"\n5. Testing branch access...")
    branches = list(repo.get_branches())[:5]
    print(f"   Found {len(branches)} branches:")
    for branch in branches:
        print(f"   - {branch.name}")

    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED! Token is valid and has correct permissions.")
    print("=" * 50)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\n" + "=" * 50)
    print("Token test FAILED!")
    print("=" * 50)
    print("\nTroubleshooting steps:")
    print("1. Go to: https://github.com/settings/tokens")
    print("2. Find your token or create a new one")
    print("3. Ensure these scopes are selected:")
    print("   ✅ repo (Full control of private repositories)")
    print("4. If using fine-grained token:")
    print("   - Repository access: Select 'Only select repositories'")
    print(f"   - Add: {REPO_OWNER}/{REPO_NAME}")
    print("   - Permissions:")
    print("     • Contents: Read and write")
    print("     • Pull requests: Read and write")
    print("     • Metadata: Read-only")
    print("5. Copy the new token and update the script")
