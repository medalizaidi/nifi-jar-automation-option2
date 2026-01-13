# Troubleshooting: 404 GitHub Repository Error

## Error Message

```
Error creating PR: 404 {"message": "Not Found", "documentation_url": "https://docs.github.com/rest/repos/repos#get-a-repository", "status": "404"}
```

This error occurs when the script cannot access the GitHub repository.

## Root Causes

### 1. Incorrect Repository Name

The script uses CircleCI environment variables to determine the repository:
- `CIRCLE_PROJECT_USERNAME` - Repository owner (user or organization)
- `CIRCLE_PROJECT_REPONAME` - Repository name

**Check the Debug Output:**

In the updated script, you'll now see:
```
DEBUG: GITHUB_TOKEN present: True
DEBUG: CIRCLE_PROJECT_REPONAME: <repo-name>
DEBUG: CIRCLE_PROJECT_USERNAME: <owner-name>
Attempting to access repository: <owner-name>/<repo-name>
```

**Verify the Repository:**

1. Check if the repository name in the logs matches your actual GitHub repository
2. Visit: `https://github.com/<owner-name>/<repo-name>` to verify it exists

### 2. GitHub Token Missing or Invalid

**Check Token Presence:**
- The debug output shows: `DEBUG: GITHUB_TOKEN present: True/False`
- If `False`, the token is not set in CircleCI context

**Verify Token in CircleCI:**

1. Go to CircleCI: **Project Settings** → **Contexts**
2. Find the `github-context` context
3. Check if `GITHUB_TOKEN` environment variable exists
4. If missing, add it with your GitHub Personal Access Token

**Create GitHub Token:**

If you need to create a new token:

1. Go to: https://github.com/settings/tokens
2. Click: **Generate new token** → **Generate new token (classic)**
3. Give it a name: `CircleCI Automation`
4. Select scopes:
   - ✅ `repo` (all repo permissions)
   - ✅ `workflow` (if using GitHub Actions)
5. Click **Generate token**
6. Copy the token (you won't see it again!)
7. Add it to CircleCI context as `GITHUB_TOKEN`

### 3. GitHub Token Lacks Permissions

Even if the token exists, it needs the correct permissions.

**Required Scopes:**
- `repo` - Full control of private repositories
  - Includes: `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`, `security_events`

**Check Token Scopes:**

You can verify token scopes using the GitHub API:

```bash
# Replace YOUR_TOKEN with your actual token
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Check scopes in response headers
curl -I -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
# Look for: X-OAuth-Scopes: repo, workflow
```

**Fix:**
1. Go to: https://github.com/settings/tokens
2. Find your token
3. Click **Update token**
4. Ensure `repo` scope is checked
5. Save and update the token in CircleCI

### 4. Token Doesn't Have Access to Repository

If your repository is in an **organization**, the token must have access.

**For Organization Repositories:**

1. **SSO Organizations:**
   - If your org uses SSO, you must authorize the token
   - Go to: https://github.com/settings/tokens
   - Find your token
   - Click **Configure SSO**
   - Authorize for your organization

2. **Organization Permissions:**
   - The token owner must have write access to the repository
   - Check: Repository Settings → Manage Access
   - Verify your user has **Write** or **Admin** permissions

### 5. Wrong CircleCI Context

The workflow uses `github-context` but the token might be in a different context.

**Check Workflow Configuration:**

In `.circleci/config.yml`:

```yaml
workflows:
  jar-to-deployment:
    jobs:
      - scan-jars-and-create-dockerfile-pr:
          context:
            - github-context  # ← Token must be in this context
```

**Verify Context:**

1. Go to CircleCI: **Organization Settings** → **Contexts**
2. Find `github-context`
3. Ensure `GITHUB_TOKEN` is defined there
4. If using a different context name, update the workflow

## Quick Fix Steps

### Step 1: Check Environment Variables in CircleCI Job

With the updated scripts, the debug output will show:

```
DEBUG: GITHUB_TOKEN present: True/False
DEBUG: CIRCLE_PROJECT_REPONAME: your-repo-name
DEBUG: CIRCLE_PROJECT_USERNAME: your-org-or-username
Attempting to access repository: your-org-or-username/your-repo-name
```

### Step 2: Verify Repository Name

Check if `your-org-or-username/your-repo-name` matches your actual GitHub repository URL.

**If Incorrect:**

CircleCI's `CIRCLE_PROJECT_USERNAME` and `CIRCLE_PROJECT_REPONAME` should be automatically set. If they're wrong:

1. Check if you're using CircleCI's GitHub integration
2. Verify the repository is properly connected in CircleCI
3. Try re-following the project in CircleCI

### Step 3: Verify GitHub Token

1. Go to CircleCI → Project Settings → Contexts
2. Open `github-context`
3. Check `GITHUB_TOKEN` exists
4. Test token access:

```bash
# In CircleCI, add a debug step:
- run:
    name: Test GitHub Token
    command: |
      curl -H "Authorization: token $GITHUB_TOKEN" \
           https://api.github.com/repos/$CIRCLE_PROJECT_USERNAME/$CIRCLE_PROJECT_REPONAME
```

Expected output: Repository JSON (not 404)

### Step 4: Update GitHub Token Scopes

1. Go to: https://github.com/settings/tokens
2. Find your token or create a new one
3. Ensure these scopes are checked:
   - ✅ `repo` (Full control of private repositories)
4. If changed, update token in CircleCI context
5. Re-run the pipeline

### Step 5: Check Organization SSO

If repository is in an organization with SSO:

1. Go to: https://github.com/settings/tokens
2. Find your token
3. Look for "Configure SSO" button next to your organization
4. Click and authorize
5. Re-run pipeline

## Testing the Fix

After making changes, test with a simple curl command in CircleCI:

```yaml
# Add this as a test job in .circleci/config.yml
test-github-access:
  docker:
    - image: cimg/base:current
  steps:
    - run:
        name: Test GitHub API Access
        command: |
          echo "Testing access to: $CIRCLE_PROJECT_USERNAME/$CIRCLE_PROJECT_REPONAME"

          # Test authentication
          curl -H "Authorization: token $GITHUB_TOKEN" \
               https://api.github.com/user

          # Test repository access
          curl -H "Authorization: token $GITHUB_TOKEN" \
               https://api.github.com/repos/$CIRCLE_PROJECT_USERNAME/$CIRCLE_PROJECT_REPONAME
```

Run this job and check:
- First curl shows your user info
- Second curl shows repository info (not 404)

## Alternative: Manual Override

If CircleCI variables are incorrect, you can manually override them:

```yaml
# In .circleci/config.yml
- run:
    name: Scan JARs and create Dockerfile PR
    command: python scripts/scan_jars_and_create_pr.py
    environment:
      DOCKERFILE_PATH: workload/mfx-aggre-data-platform/custom_nifi/Dockerfile
      JARS_FOLDER: workload/mfx-aggre-data-platform/custom_nifi/jars
      TARGET_BRANCH: master
      CIRCLE_PROJECT_USERNAME: your-actual-org  # ← Override here
      CIRCLE_PROJECT_REPONAME: your-actual-repo # ← Override here
```

## Still Not Working?

### Check Script Updates Applied

Ensure you've pushed the updated scripts:

```bash
# Check if you have the latest version
git pull origin master

# Verify the imports include Auth
grep "from github import Github, Auth" scripts/scan_jars_and_create_pr.py
grep "from github import Github, Auth" scripts/update_task_definition.py

# If not found, the updates haven't been pushed
git add scripts/
git commit -m "Fix GitHub authentication and add debug logging"
git push origin master
```

### Manual Repository Test

Test GitHub access locally with Python:

```python
#!/usr/bin/env python3
from github import Github, Auth

# Replace with your values
GITHUB_TOKEN = "your_token_here"
REPO_OWNER = "your_org_or_username"
REPO_NAME = "your_repo_name"

auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)

try:
    repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    print(f"✅ Successfully accessed: {repo.full_name}")
    print(f"   Description: {repo.description}")
    print(f"   Private: {repo.private}")
except Exception as e:
    print(f"❌ Error: {e}")
```

Save as `test_github_access.py` and run:
```bash
python test_github_access.py
```

### Check CircleCI Integration

1. Go to CircleCI → Project Settings
2. Click **GitHub Permissions**
3. Verify CircleCI has access to your repository
4. If not, click **Authorize with GitHub**

## Summary Checklist

- [ ] Updated scripts with new Auth.Token() method
- [ ] GitHub token exists in `github-context` in CircleCI
- [ ] Token has `repo` scope
- [ ] Token is authorized for organization (if SSO)
- [ ] Repository name in debug output matches actual repository
- [ ] CIRCLE_PROJECT_USERNAME and CIRCLE_PROJECT_REPONAME are correct
- [ ] CircleCI has GitHub integration enabled
- [ ] User has write access to repository

## Getting Help

If still stuck, collect this information:

1. Debug output from the job (with sensitive data redacted):
   ```
   DEBUG: GITHUB_TOKEN present: True/False
   DEBUG: CIRCLE_PROJECT_REPONAME: <repo>
   DEBUG: CIRCLE_PROJECT_USERNAME: <owner>
   Attempting to access repository: <owner>/<repo>
   ```

2. Does this URL work? `https://github.com/<owner>/<repo>`

3. Token scopes from:
   ```bash
   curl -I -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
   # Look for: X-OAuth-Scopes header
   ```

4. CircleCI context configuration screenshot (redact token value)
