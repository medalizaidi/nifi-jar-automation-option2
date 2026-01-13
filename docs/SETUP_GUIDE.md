# CircleCI Pipeline Setup Guide

This guide explains how to set up the automated JAR management pipeline for NiFi.

## Overview

This pipeline automates the process of:
1. Adding new JARs to the NiFi Docker image
2. Building and pushing the updated image to ECR
3. Updating the ECS task definition

## Prerequisites

- CircleCI account connected to your GitHub repository
- AWS account with ECR and ECS configured
- GitHub personal access token with repo permissions

## Setup Steps

### 1. Configure CircleCI Contexts

Create two contexts in CircleCI (Organization Settings → Contexts):

#### `github-context`
| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope |

#### `aws-context`
| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_ACCOUNT_ID` | AWS account ID (e.g., `478874601698`) |
| `AWS_REGION` | AWS region (e.g., `ap-northeast-1`) |

### 2. Configure Path Filtering (Optional)

To trigger workflows only when specific files change, add path filtering:

```yaml
# In .circleci/config.yml
setup: true

workflows:
  setup-workflow:
    jobs:
      - path-filtering/filter:
          mapping: |
            workload/.*/custom_nifi/jars/.* jar-update true
            workload/.*/custom_nifi/Dockerfile docker-build true
```

### 3. Folder Structure

Ensure your repository has this structure:

```
workload/
└── mfx-aggre-data-platform/
    ├── custom_nifi/
    │   ├── Dockerfile
    │   └── jars/
    │       ├── README.md
    │       └── *.json (JAR manifests)
    ├── ecs_task_definition.tf
    └── ... (other terraform files)
scripts/
├── scan_jars_and_create_pr.py
└── update_task_definition.py
.circleci/
└── config.yml
```

### 4. Environment Variables

Set these in your CircleCI project settings or contexts:

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT for creating PRs |
| `AWS_ACCESS_KEY_ID` | Yes | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS credentials |
| `AWS_ACCOUNT_ID` | Yes | Your AWS account ID |
| `AWS_REGION` | Yes | AWS region for ECR |
| `DOCKERFILE_PATH` | No | Custom Dockerfile path |
| `JARS_FOLDER` | No | Custom JARs folder path |
| `TASK_DEF_PATH` | No | Custom task definition path |

## Workflow Details

### Workflow 1: JAR Update Detection

**Trigger:** Merge to `master` branch with changes in `jars/` folder

```
┌─────────────┐
│ scan-and-   │
│ create-pr   │
└─────────────┘
      │
      ▼
┌─────────────┐
│ Compare     │
│ JARs with   │
│ Dockerfile  │
└─────────────┘
      │
      ▼
┌─────────────┐
│ Create PR   │
│ to update   │
│ Dockerfile  │
└─────────────┘
```

### Workflow 2: Docker Build

**Trigger:** Merge to `master` with Dockerfile changes

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ build-and-  │────▶│ update-task │────▶│ Create PR   │
│ push-image  │     │ -definition │     │ for TF      │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Workflow 3: Terraform Deploy

**Trigger:** Manual approval

```
┌─────────────┐     ┌─────────────┐
│ hold-for-   │────▶│ apply-      │
│ approval    │     │ terraform   │
└─────────────┘     └─────────────┘
```

## Testing the Pipeline

### 1. Test JAR Detection Locally

```bash
# Set environment variables
export DOCKERFILE_PATH="workload/mfx-aggre-data-platform/custom_nifi/Dockerfile"
export JARS_FOLDER="workload/mfx-aggre-data-platform/custom_nifi/jars"

# Run the scan script (without GitHub PR creation)
python scripts/scan_jars_and_create_pr.py
```

### 2. Verify CircleCI Config

```bash
circleci config validate .circleci/config.yml
```

### 3. Test Docker Build Locally

```bash
cd workload/mfx-aggre-data-platform/custom_nifi
docker build -t nifi-test:local .
```

## Troubleshooting

### Pipeline not triggering

1. Check branch filters in `config.yml`
2. Verify file paths match the expected patterns
3. Check CircleCI project settings for branch restrictions

### PR creation fails

1. Verify `GITHUB_TOKEN` has correct permissions
2. Check that the target branch exists
3. Review CircleCI logs for detailed error messages

### Docker build fails

1. Verify JAR URLs are accessible
2. Check for syntax errors in Dockerfile
3. Ensure base image `apache/nifi:latest` is available

### Task definition update fails

1. Verify the regex pattern matches your task definition format
2. Check that the image URL format is correct
3. Review the generated task definition content

## Security Considerations

1. **GitHub Token:** Use a token with minimal required permissions
2. **AWS Credentials:** Consider using OIDC instead of static credentials
3. **JAR Sources:** Only allow JARs from trusted sources
4. **PR Reviews:** Always require at least one approval for automated PRs

## Maintenance

- Regularly update base images and dependencies
- Monitor for security advisories on included JARs
- Review and clean up unused JAR manifests
- Update CircleCI orbs periodically
