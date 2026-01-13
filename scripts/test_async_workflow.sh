#!/bin/bash
# Automated test script for the async workflow
# This script tests the change detection logic locally

set -e

echo "🧪 Testing Async Workflow Change Detection"
echo "==========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Make sure the check script is executable
chmod +x scripts/check_changed_files.sh

# Save current state
ORIGINAL_BRANCH=$(git branch --show-current)
STASH_NEEDED=false

if ! git diff-index --quiet HEAD --; then
    echo "${YELLOW}⚠ Uncommitted changes detected, stashing...${NC}"
    git stash push -m "test_async_workflow_stash"
    STASH_NEEDED=true
fi

# Create a test branch
TEST_BRANCH="test/async-workflow-$(date +%s)"
git checkout -b "$TEST_BRANCH"

cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    git checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
    git branch -D "$TEST_BRANCH" 2>/dev/null || true

    if [ "$STASH_NEEDED" = true ]; then
        echo "Restoring stashed changes..."
        git stash pop
    fi
}

trap cleanup EXIT

# Test 1: JAR manifest change detection
echo "Test 1: JAR Manifest Change Detection"
echo "--------------------------------------"

TEST_JAR="workload/mfx-aggre-data-platform/custom_nifi/jars/test-$(date +%s).json"
cat > "$TEST_JAR" <<EOF
{
  "name": "test-$(date +%s).jar",
  "url": "https://example.com/test.jar",
  "install_path": "/opt/nifi/nifi-current/lib/",
  "description": "Test JAR for workflow validation"
}
EOF

git add "$TEST_JAR"
git commit -m "test: Add test JAR manifest" --no-verify

echo "Testing JAR detection..."
if ./scripts/check_changed_files.sh jars; then
  echo -e "${GREEN}✅ PASS: JAR change detected correctly${NC}"
else
  echo -e "${RED}❌ FAIL: JAR change not detected${NC}"
  exit 1
fi

echo "Testing Dockerfile detection (should be negative)..."
if ./scripts/check_changed_files.sh dockerfile; then
  echo -e "${RED}❌ FAIL: Dockerfile change incorrectly detected${NC}"
  exit 1
else
  echo -e "${GREEN}✅ PASS: Dockerfile change correctly not detected${NC}"
fi

echo ""

# Test 2: Dockerfile change detection
echo "Test 2: Dockerfile Change Detection"
echo "------------------------------------"

echo "# Test comment $(date)" >> workload/mfx-aggre-data-platform/custom_nifi/Dockerfile
git add workload/mfx-aggre-data-platform/custom_nifi/Dockerfile
git commit -m "test: Update Dockerfile" --no-verify

echo "Testing Dockerfile detection..."
if ./scripts/check_changed_files.sh dockerfile; then
  echo -e "${GREEN}✅ PASS: Dockerfile change detected correctly${NC}"
else
  echo -e "${RED}❌ FAIL: Dockerfile change not detected${NC}"
  exit 1
fi

echo "Testing JAR detection (should be negative)..."
if ./scripts/check_changed_files.sh jars; then
  echo -e "${RED}❌ FAIL: JAR change incorrectly detected${NC}"
  exit 1
else
  echo -e "${GREEN}✅ PASS: JAR change correctly not detected${NC}"
fi

echo ""

# Test 3: Unrelated file change
echo "Test 3: Unrelated File Change Detection"
echo "----------------------------------------"

echo "# Test $(date)" >> README.md
git add README.md
git commit -m "test: Update README" --no-verify

echo "Testing JAR detection (should be negative)..."
if ./scripts/check_changed_files.sh jars; then
  echo -e "${RED}❌ FAIL: JAR change incorrectly detected${NC}"
  exit 1
else
  echo -e "${GREEN}✅ PASS: JAR change correctly not detected${NC}"
fi

echo "Testing Dockerfile detection (should be negative)..."
if ./scripts/check_changed_files.sh dockerfile; then
  echo -e "${RED}❌ FAIL: Dockerfile change incorrectly detected${NC}"
  exit 1
else
  echo -e "${GREEN}✅ PASS: Dockerfile change correctly not detected${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}🎉 All tests passed!${NC}"
echo "========================================="
echo ""
echo "The change detection script is working correctly."
echo "You can now test the full workflow in CircleCI by:"
echo "  1. Adding a JAR manifest and pushing to master"
echo "  2. Merging the resulting Dockerfile PR"
echo "  3. Observing the sequential job execution"
echo ""
echo "See docs/TESTING_ASYNC_WORKFLOW.md for detailed test scenarios."
