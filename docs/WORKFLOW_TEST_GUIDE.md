# Testing the Sequential Workflow

This guide walks you through testing the complete workflow from JAR manifest addition to task definition PR creation.

## Workflow Overview

```
Developer adds JAR manifest → PR merged to master
                ↓
┌─────────────────────────────────┐
│ 1. scan-jars-and-create-        │  Detects new JAR, creates
│    dockerfile-pr                │  PR to update Dockerfile
└─────────────────────────────────┘
                ↓ (Dockerfile PR approved & merged)
┌─────────────────────────────────┐
│ 2. build-and-push-image         │  Builds Docker, pushes to ECR
└─────────────────────────────────┘
                ↓
┌─────────────────────────────────┐
│ 3. create-task-definition-pr    │  Creates PR to update
│                                 │  ecs_task_definition.tf
└─────────────────────────────────┘
                ↓
           ✅ DONE!
     (Task Def PR ready for review)
```

## Prerequisites

Before testing, ensure you have:
- [ ] CircleCI configured with required contexts:
  - `github-context` with `GITHUB_TOKEN`
  - `aws-context` with `AWS_ACCOUNT_ID` and `AWS_REGION`
- [ ] Permissions to push to master branch
- [ ] Access to CircleCI dashboard
- [ ] Access to GitHub repository
- [ ] Access to AWS ECR (to verify image push)

## End-to-End Test

### Step 1: Add a Test JAR Manifest

Create a new JAR manifest file to trigger the workflow:

```bash
# Create a test JAR manifest
cat > workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json <<'EOF'
{
  "name": "mysql-connector-j-9.5.0.jar",
  "url": "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar",
  "install_path": "/opt/nifi/nifi-current/lib/",
  "description": "MySQL JDBC Driver"
}
EOF

# Commit and push to master
git add workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json
git commit -m "test: Add MySQL connector JAR manifest for workflow testing"
git push origin master
```

**Expected Outcome:**
- All 3 jobs will run in CircleCI
- Job 1 will complete and create a Dockerfile PR
- Jobs 2 and 3 will also run (because workflow runs all jobs on master)

**Verify:**
1. Go to CircleCI dashboard
2. Find the pipeline triggered by your commit
3. Check that Job 1 (`scan-jars-and-create-dockerfile-pr`) completes successfully
4. Look in the artifacts for `jar-diff-report.json`
5. Check GitHub for a new PR with title like: `[Auto] Add JAR(s): mysql-connector-j-9.5.0.jar`

**CircleCI Job 1 Logs Should Show:**
```
Found 1 existing JARs in Dockerfile
  - postgresql-42.7.1.jar
Found 2 JAR manifests in workload/.../jars
  - postgresql-42.7.1.jar
  - mysql-connector-j-9.5.0.jar
Found 1 new/updated JARs to add
Created PR #XX: https://github.com/.../pull/XX
```

---

### Step 2: Review the Dockerfile PR

**Check the PR content:**

1. Go to the GitHub PR created by Job 1
2. Review the changes - should add lines like:

```dockerfile
# Download MySQL JDBC Driver
RUN curl -L "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar" \
        -o /opt/nifi/nifi-current/lib/mysql-connector-j-9.5.0.jar && \
        chown 1000:1000 /opt/nifi/nifi-current/lib/mysql-connector-j-9.5.0.jar
```

3. Verify the PR body includes:
   - Table of new JARs
   - Checklist items
   - Information about next steps

**Do NOT merge yet** - first verify Job 2 and 3 from Step 1 completed

---

### Step 3: Verify Job 2 and Job 3 from Initial Push

**Check Job 2 (`build-and-push-image`):**

1. In CircleCI, check Job 2 status
2. It should complete successfully
3. Logs should show:
   ```
   Successfully built abc123def
   Successfully tagged XXX.dkr.ecr.region.amazonaws.com/apache-nifi-with-custom-jars-repo:abc1234
   The push refers to repository [XXX.dkr.ecr.region.amazonaws.com/...]
   ```

**Verify in AWS ECR:**
```bash
# Check latest image in ECR
aws ecr describe-images \
  --repository-name apache-nifi-with-custom-jars-repo \
  --region ${AWS_REGION} \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1]' \
  --output json
```

**Check Job 3 (`create-task-definition-pr`):**

1. Job 3 should run after Job 2 completes
2. It will create a PR to update the task definition
3. However, this PR updates the image tag from the current Dockerfile build
4. Check GitHub for a PR like: `[Auto] Update NiFi Docker image to abc1234`

**Note:** This first task definition PR is based on the current Dockerfile (without the new JAR yet)

---

### Step 4: Merge the Dockerfile PR

Now merge the Dockerfile PR from Step 1:

```bash
# Option 1: Via GitHub UI
# Go to the PR and click "Merge"

# Option 2: Via GitHub CLI
gh pr list  # Find the PR number
gh pr merge <PR_NUMBER> --merge --delete-branch
```

**Expected Outcome:**
- Merging triggers a new CircleCI pipeline
- All 3 jobs run again
- Job 1 will find no new JARs (will still complete but with message "No new JARs to add")
- Job 2 will build with the updated Dockerfile (now includes MySQL JAR)
- Job 3 will create a new task definition PR with the new image tag

**Verify:**
1. New pipeline starts in CircleCI
2. Job 1 completes with "No new JARs to add. Exiting."
3. Job 2 builds Docker image with new tag
4. Job 3 creates a new task definition PR

---

### Step 5: Verify the New Build Includes the JAR

**Check Job 2 Dockerfile build:**

The Docker image should now include the MySQL JAR in the build steps.

**Check Job 3 PR:**

1. Find the new task definition PR
2. It should show image tag update
3. The PR body should indicate:
   - Previous image tag
   - New image tag (from the build with MySQL JAR)

**Verify the image in ECR includes the JAR:**
```bash
# Get the latest image tag
IMAGE_TAG=$(aws ecr describe-images \
  --repository-name apache-nifi-with-custom-jars-repo \
  --region ${AWS_REGION} \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1].imageTags[0]' \
  --output text)

echo "Latest image tag: $IMAGE_TAG"

# Optional: Pull and inspect the image locally
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker pull ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/apache-nifi-with-custom-jars-repo:${IMAGE_TAG}

# Check if JAR exists in the image
docker run --rm \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/apache-nifi-with-custom-jars-repo:${IMAGE_TAG} \
  ls -la /opt/nifi/nifi-current/lib/ | grep mysql
```

---

### Step 6: Merge the Task Definition PR

Finally, merge the task definition PR:

```bash
gh pr list  # Find the latest task definition PR
gh pr merge <PR_NUMBER> --merge --delete-branch
```

**Expected Outcome:**
- Task definition file is updated with new image tag
- Ready for terraform apply to deploy

**Verify:**
```bash
# Check the task definition file
cat workload/mfx-aggre-data-platform/ecs_task_definition.tf | grep -A 5 "image"
# Should show the new image tag
```

---

### Step 7: Cleanup (Optional)

If this was a test, you can clean up:

```bash
# Remove the test JAR manifest
git rm workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json
git commit -m "test: Remove MySQL connector JAR manifest (cleanup)"
git push origin master
```

This will trigger the workflow again, and Job 1 will detect no new JARs.

---

## What to Monitor

### In CircleCI

For each pipeline run, check:

1. **Pipeline View:**
   - All 3 jobs are listed
   - Job dependencies are respected (Job 3 waits for Job 2)

2. **Job 1 Logs:**
   - Dockerfile parsing
   - JAR folder scanning
   - JAR diff comparison
   - PR creation (if new JARs found)

3. **Job 2 Logs:**
   - Docker build output
   - ECR login
   - Image push confirmation
   - Workspace persistence (image-tag.txt)

4. **Job 3 Logs:**
   - Workspace attachment
   - Image tag reading
   - Task definition update
   - PR creation

### In GitHub

1. **Pull Requests:**
   - Dockerfile PR from Job 1 (if new JARs)
   - Task definition PR from Job 3

2. **PR Labels:**
   - Should have `automated` label
   - Dockerfile PR: `jar-update` label
   - Task def PR: `infrastructure`, `ecs` labels

### In AWS ECR

1. **Image Repository:**
   ```bash
   aws ecr describe-images \
     --repository-name apache-nifi-with-custom-jars-repo \
     --region ${AWS_REGION} \
     --query 'imageDetails[*].[imageTags[0],imagePushedAt]' \
     --output table
   ```

2. **Verify Tags:**
   - Each build creates a tag matching `${CIRCLE_SHA1:0:7}`
   - Also updates the `latest` tag

---

## Common Issues and Solutions

### Issue 1: Job 1 doesn't create PR

**Symptoms:**
- Job 1 completes but no PR created
- Logs show "No new JARs to add"

**Causes:**
- JAR manifest already exists in Dockerfile
- JAR manifest format is incorrect

**Solutions:**
1. Check existing JARs in Dockerfile
2. Verify manifest JSON format matches expected schema
3. Use a different JAR name

---

### Issue 2: Job 2 fails to build

**Symptoms:**
- Docker build fails
- ECR login fails

**Causes:**
- Dockerfile syntax error
- AWS credentials not configured
- ECR repository doesn't exist

**Solutions:**
1. Test Dockerfile build locally:
   ```bash
   cd workload/mfx-aggre-data-platform/custom_nifi
   docker build -t test-nifi .
   ```
2. Verify AWS context in CircleCI
3. Check ECR repository exists

---

### Issue 3: Job 3 doesn't get image tag

**Symptoms:**
- Job 3 fails with "No image tag provided"

**Causes:**
- Workspace not persisted from Job 2
- Job 2 didn't complete successfully

**Solutions:**
1. Check Job 2 completed successfully
2. Verify `persist_to_workspace` in Job 2
3. Verify `attach_workspace` in Job 3
4. Check `/tmp/image-tag.txt` was created

---

### Issue 4: Jobs run in wrong order

**Symptoms:**
- Job 3 starts before Job 2 completes

**Causes:**
- Workflow dependencies incorrect

**Solutions:**
1. Check `.circleci/config.yml` workflow section
2. Verify Job 3 has `requires: - build-and-push-image`

---

## Success Criteria

A successful workflow test demonstrates:

- ✅ Job 1 detects new JAR and creates Dockerfile PR
- ✅ Job 2 builds Docker image and pushes to ECR
- ✅ Job 3 waits for Job 2 and creates task definition PR
- ✅ PRs are properly formatted with correct information
- ✅ Docker image contains the new JAR
- ✅ Task definition references correct image tag
- ✅ All jobs complete without errors

---

## Quick Reference Commands

```bash
# Check CircleCI recent pipelines
# Go to: https://app.circleci.com/pipelines/github/<org>/<repo>

# List recent PRs
gh pr list --limit 5

# Check ECR images
aws ecr describe-images \
  --repository-name apache-nifi-with-custom-jars-repo \
  --region ${AWS_REGION} \
  --max-items 5

# View specific PR
gh pr view <PR_NUMBER>

# View CircleCI workflow status
# (requires circleci CLI)
circleci open
```

---

## Expected Timeline

For a complete workflow test:

1. **Step 1-3:** ~5-10 minutes (first pipeline run)
2. **Step 4:** ~1 minute (merge PR)
3. **Step 5:** ~5-10 minutes (second pipeline run)
4. **Step 6:** ~1 minute (merge PR)
5. **Total:** ~15-25 minutes

---

## Next Steps After Testing

Once you've verified the workflow works correctly:

1. **Document the process** for your team
2. **Set up notifications** for PR creation (Slack, email)
3. **Configure branch protection** for automated PRs
4. **Add approval requirements** for Dockerfile and task definition PRs
5. **Monitor ECR storage** and set up image lifecycle policies
