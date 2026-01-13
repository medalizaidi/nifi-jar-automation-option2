# Quick Start: Testing the Workflow

## Overview

This is a guide to quickly test your NiFi JAR automation workflow that follows this pattern:

```
JAR manifest added → Dockerfile PR → Docker build → Task definition PR
```

## 🚀 Quick Test (3 commands)

```bash
# 1. Run the test script
./scripts/start_workflow_test.sh

# 2. Wait for Job 1, then merge the Dockerfile PR
gh pr list
gh pr merge <PR_NUMBER> --merge

# 3. Wait for Jobs 2 & 3, then merge the task definition PR
gh pr merge <PR_NUMBER> --merge
```

## 📋 What the Workflow Does

### Current State
You have 1 JAR currently configured:
- `postgresql-42.7.1.jar`

### The 3-Job Pipeline

**Job 1: `scan-jars-and-create-dockerfile-pr`**
- Scans `workload/mfx-aggre-data-platform/custom_nifi/jars/*.json` files
- Compares with existing JARs in Dockerfile
- Creates a PR to add new JAR download commands to Dockerfile

**Job 2: `build-and-push-image`**
- Builds Docker image from `workload/mfx-aggre-data-platform/custom_nifi/Dockerfile`
- Tags with commit SHA (e.g., `abc1234`)
- Pushes to ECR: `apache-nifi-with-custom-jars-repo`

**Job 3: `create-task-definition-pr`**
- Waits for Job 2 to complete
- Reads image tag from Job 2
- Creates PR to update `workload/mfx-aggre-data-platform/ecs_task_definition.tf`

## 🧪 Testing Step-by-Step

### Option 1: Automated Test (Recommended)

```bash
./scripts/start_workflow_test.sh
```

This script will:
1. Ask you to select a test JAR (MySQL, MariaDB, or MongoDB)
2. Create the JAR manifest file
3. Commit and push to master
4. Display next steps

### Option 2: Manual Test

```bash
# 1. Create a test JAR manifest
cat > workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json <<'EOF'
{
  "name": "mysql-connector-j-9.5.0.jar",
  "url": "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar",
  "install_path": "/opt/nifi/nifi-current/lib/",
  "description": "MySQL JDBC Driver"
}
EOF

# 2. Commit and push
git add workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json
git commit -m "test: Add MySQL connector for workflow testing"
git push origin master

# 3. Monitor CircleCI
# Go to: https://app.circleci.com/pipelines/github/<org>/<repo>

# 4. After Job 1 completes, check for PR
gh pr list

# 5. Merge the Dockerfile PR
gh pr merge <PR_NUMBER> --merge

# 6. Wait for new pipeline, then merge task definition PR
gh pr merge <PR_NUMBER> --merge
```

## 📊 Monitoring

### Check Pipeline Status
```bash
# View CircleCI (requires browser)
open https://app.circleci.com/pipelines/github/<org>/<repo>

# List GitHub PRs
gh pr list

# Check recent ECR images
aws ecr describe-images \
  --repository-name apache-nifi-with-custom-jars-repo \
  --region ${AWS_REGION} \
  --query 'sort_by(imageDetails,& imagePushedAt)[-5:]'
```

### Expected Timeline

| Step | Duration | What's Happening |
|------|----------|------------------|
| Push to master | ~1 min | Pipeline starts |
| Job 1 | ~2-3 min | Scans JARs, creates Dockerfile PR |
| Job 2 | ~5-7 min | Builds Docker image, pushes to ECR |
| Job 3 | ~1-2 min | Creates task definition PR |
| Merge Dockerfile PR | ~1 min | Manual review & merge |
| New pipeline | ~5-10 min | Builds with new JAR |
| **Total** | **~15-25 min** | Complete workflow |

## ✅ Success Indicators

After the first push (with JAR manifest):
- ✅ Job 1 creates PR: `[Auto] Add JAR(s): mysql-connector-j-9.5.0.jar`
- ✅ Job 2 builds and pushes image to ECR
- ✅ Job 3 creates PR: `[Auto] Update NiFi Docker image to <sha>`

After merging Dockerfile PR:
- ✅ New pipeline starts automatically
- ✅ Job 1 shows "No new JARs to add"
- ✅ Job 2 builds with updated Dockerfile (includes new JAR)
- ✅ Job 3 creates new task definition PR with latest image tag

## 🧹 Cleanup After Testing

```bash
# Remove test JAR manifest
git rm workload/mfx-aggre-data-platform/custom_nifi/jars/mysql-connector-j-9.5.0.json
git commit -m "test: Cleanup test JAR manifest"
git push origin master
```

## 🔍 Troubleshooting

### Job 1 says "No new JARs to add"

**Cause:** JAR already exists in Dockerfile
**Solution:** Use a different JAR name or remove existing one first

### Job 2 fails to build

**Cause:** Docker build error or AWS credentials issue
**Solution:** Check Dockerfile syntax and AWS context in CircleCI

### Job 3 doesn't run

**Cause:** Job 2 didn't complete successfully
**Solution:** Check Job 2 logs for errors

### No PR created

**Cause:** Missing `GITHUB_TOKEN` in CircleCI context
**Solution:** Add `GITHUB_TOKEN` to `github-context` in CircleCI

## 📚 Detailed Documentation

For complete information, see:
- **[WORKFLOW_TEST_GUIDE.md](./WORKFLOW_TEST_GUIDE.md)** - Comprehensive testing guide
- **Python scripts:**
  - `scripts/scan_jars_and_create_pr.py` - Job 1 logic
  - `scripts/update_task_definition.py` - Job 3 logic
- **CircleCI config:** `.circleci/config.yml`

## 🎯 Expected Workflow Flow

```
┌─────────────────────────────┐
│  You: Add JAR manifest      │
│  workload/.../jars/X.json   │
└──────────┬──────────────────┘
           │
           │ git push origin master
           ↓
┌─────────────────────────────┐
│  CircleCI: All 3 jobs run   │
│  Job 1: Creates Dockerfile  │
│         PR                  │
│  Job 2: Builds current      │
│         Dockerfile          │
│  Job 3: Creates task def PR │
└──────────┬──────────────────┘
           │
           │ You: Merge Dockerfile PR
           ↓
┌─────────────────────────────┐
│  CircleCI: New pipeline     │
│  Job 1: No new JARs         │
│  Job 2: Builds with new JAR │
│  Job 3: New task def PR     │
└──────────┬──────────────────┘
           │
           │ You: Merge task def PR
           ↓
┌─────────────────────────────┐
│  Ready for terraform apply  │
│  to deploy to ECS           │
└─────────────────────────────┘
```

## ⚙️ Prerequisites

Before testing, ensure:
- [ ] You're on `master` branch
- [ ] No uncommitted changes (`git status`)
- [ ] CircleCI contexts configured:
  - `github-context` with `GITHUB_TOKEN`
  - `aws-context` with `AWS_ACCOUNT_ID`, `AWS_REGION`
- [ ] ECR repository exists: `apache-nifi-with-custom-jars-repo`
- [ ] You have push access to master

## 💡 Tips

- **First time?** Use the automated script: `./scripts/start_workflow_test.sh`
- **Monitoring:** Keep CircleCI dashboard and GitHub PRs open in browser tabs
- **Debugging:** Check artifacts in Job 1 for `jar-diff-report.json`
- **Verification:** After final merge, verify image tag in task definition matches ECR

## 🆘 Need Help?

1. Check CircleCI job logs for detailed error messages
2. Review `docs/WORKFLOW_TEST_GUIDE.md` for troubleshooting section
3. Verify all environment variables are set in CircleCI contexts
4. Ensure AWS permissions are correct for ECR operations
