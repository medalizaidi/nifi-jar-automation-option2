#!/bin/bash
# Script to detect which files changed in the current commit
# Returns exit code 0 if relevant files changed, 1 otherwise

set -e

CHANGE_TYPE=$1  # "jars", "dockerfile", or "taskdef"

if [ -z "$CHANGE_TYPE" ]; then
    echo "Usage: $0 <jars|dockerfile|taskdef>"
    exit 1
fi

# Get the list of changed files
# For CircleCI, compare current commit with previous commit
if [ -n "$CIRCLE_COMPARE_URL" ]; then
    # Extract commit range from CIRCLE_COMPARE_URL
    COMMIT_RANGE=$(echo $CIRCLE_COMPARE_URL | sed 's|.*compare/||')
    echo "Checking changes in commit range: $COMMIT_RANGE"
    CHANGED_FILES=$(git diff --name-only $COMMIT_RANGE 2>/dev/null || git diff --name-only HEAD~1 HEAD)
else
    # Fallback: compare with previous commit
    echo "Checking changes in HEAD~1..HEAD"
    CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
fi

echo "Changed files:"
echo "$CHANGED_FILES"
echo ""

case "$CHANGE_TYPE" in
    jars)
        # Check if any JAR manifest files changed
        if echo "$CHANGED_FILES" | grep -q "workload/.*\/jars\/.*\.json"; then
            echo "✓ JAR manifest files changed - proceeding with scan"
            exit 0
        else
            echo "✗ No JAR manifest changes detected - skipping scan"
            exit 1
        fi
        ;;

    dockerfile)
        # Check if Dockerfile changed
        if echo "$CHANGED_FILES" | grep -q "workload/.*\/Dockerfile"; then
            echo "✓ Dockerfile changed - proceeding with build"
            exit 0
        else
            echo "✗ No Dockerfile changes detected - skipping build"
            exit 1
        fi
        ;;

    taskdef)
        # This job should always run after build completes (handled by requires)
        echo "✓ Task definition update job triggered by build completion"
        exit 0
        ;;

    *)
        echo "Unknown change type: $CHANGE_TYPE"
        exit 1
        ;;
esac
