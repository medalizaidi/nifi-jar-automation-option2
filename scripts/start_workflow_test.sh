#!/bin/bash
# Quick start script to test the workflow
# This creates a test JAR manifest and pushes to master to trigger the workflow

set -e

echo "🧪 Starting Workflow Test"
echo "========================="
echo ""

# Check if on master branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "master" ] && [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Warning: You are on branch '$CURRENT_BRANCH', not 'master' or 'main'"
    echo "The workflow is configured to run on 'master' branch only."
    read -p "Do you want to switch to master? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git checkout master
    else
        echo "Exiting. Please switch to master branch manually."
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  You have uncommitted changes."
    echo "Please commit or stash them before running this test."
    git status --short
    exit 1
fi

echo "Step 1: Creating Test JAR Manifest"
echo "-----------------------------------"

# Ask which JAR to test with
echo ""
echo "Select a test JAR to add:"
echo "  1) MySQL Connector J 9.5.0 (recommended)"
echo "  2) MariaDB Connector J 3.3.2"
echo "  3) MongoDB Driver 5.0.0"
echo "  4) Custom (enter manually)"
echo ""
read -p "Enter choice (1-4): " CHOICE

case $CHOICE in
    1)
        JAR_NAME="mysql-connector-j-9.5.0.jar"
        JAR_URL="https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/9.5.0/mysql-connector-j-9.5.0.jar"
        JAR_DESC="MySQL JDBC Driver"
        ;;
    2)
        JAR_NAME="mariadb-java-client-3.3.2.jar"
        JAR_URL="https://repo1.maven.org/maven2/org/mariadb/jdbc/mariadb-java-client/3.3.2/mariadb-java-client-3.3.2.jar"
        JAR_DESC="MariaDB JDBC Driver"
        ;;
    3)
        JAR_NAME="mongodb-driver-sync-5.0.0.jar"
        JAR_URL="https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-sync/5.0.0/mongodb-driver-sync-5.0.0.jar"
        JAR_DESC="MongoDB Sync Driver"
        ;;
    4)
        read -p "Enter JAR name (e.g., example-1.0.0.jar): " JAR_NAME
        read -p "Enter JAR URL: " JAR_URL
        read -p "Enter description: " JAR_DESC
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

JAR_FILE="workload/mfx-aggre-data-platform/custom_nifi/jars/${JAR_NAME%.jar}.json"

# Check if manifest already exists
if [ -f "$JAR_FILE" ]; then
    echo "❌ Error: JAR manifest already exists: $JAR_FILE"
    echo "The workflow will not detect it as a new JAR."
    echo ""
    echo "To test, either:"
    echo "  1. Remove the existing manifest first: rm $JAR_FILE"
    echo "  2. Choose a different JAR"
    exit 1
fi

# Create the manifest
cat > "$JAR_FILE" <<EOF
{
  "name": "$JAR_NAME",
  "url": "$JAR_URL",
  "install_path": "/opt/nifi/nifi-current/lib/",
  "description": "$JAR_DESC"
}
EOF

echo "✅ Created: $JAR_FILE"
echo ""
cat "$JAR_FILE"
echo ""

# Commit and push
echo "Step 2: Committing and Pushing to Master"
echo "-----------------------------------------"

git add "$JAR_FILE"
git commit -m "test: Add $JAR_NAME for workflow testing

This commit tests the complete workflow:
1. scan-jars-and-create-dockerfile-pr
2. build-and-push-image
3. create-task-definition-pr"

echo "✅ Committed"
echo ""

read -p "Push to master and trigger the workflow? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. You can push manually later with: git push origin master"
    echo "To undo the commit: git reset --soft HEAD~1"
    exit 0
fi

git push origin master

echo ""
echo "✅ Pushed to master!"
echo ""
echo "========================================="
echo "🚀 Workflow Started!"
echo "========================================="
echo ""
echo "What happens next:"
echo ""
echo "1️⃣  Job 1: scan-jars-and-create-dockerfile-pr"
echo "   - Detects the new JAR manifest"
echo "   - Creates a PR to update the Dockerfile"
echo "   - Check CircleCI for progress"
echo ""
echo "2️⃣  Job 2: build-and-push-image"
echo "   - Builds Docker image (current Dockerfile)"
echo "   - Pushes to ECR"
echo ""
echo "3️⃣  Job 3: create-task-definition-pr"
echo "   - Creates PR to update ECS task definition"
echo "   - Wait for Job 2 to complete first"
echo ""
echo "========================================="
echo "📊 Monitor Progress:"
echo "========================================="
echo ""
echo "CircleCI:"
echo "  https://app.circleci.com/pipelines/github/${CIRCLE_PROJECT_USERNAME:-<org>}/${CIRCLE_PROJECT_REPONAME:-<repo>}"
echo ""
echo "GitHub PRs:"
echo "  gh pr list"
echo ""
echo "Expected PRs:"
echo "  1. [Auto] Add JAR(s): $JAR_NAME"
echo "  2. [Auto] Update NiFi Docker image to <commit-sha>"
echo ""
echo "========================================="
echo "📖 Next Steps:"
echo "========================================="
echo ""
echo "1. Wait for Job 1 to complete (~2-3 minutes)"
echo "2. Review the Dockerfile PR"
echo "3. Merge the Dockerfile PR"
echo "4. Wait for new build to complete (~5-7 minutes)"
echo "5. Review and merge the task definition PR"
echo ""
echo "For detailed instructions, see:"
echo "  docs/WORKFLOW_TEST_GUIDE.md"
echo ""
echo "To cleanup after testing:"
echo "  git rm $JAR_FILE"
echo "  git commit -m 'test: Cleanup test JAR manifest'"
echo "  git push origin master"
echo ""
