#!/bin/bash
# NiFi ECS User Data Script
# This script is used when running NiFi on EC2-backed ECS

set -ex

# Configure ECS agent
echo "ECS_CLUSTER=${cluster_name}" >> /etc/ecs/ecs.config
echo "ECS_ENABLE_TASK_IAM_ROLE=true" >> /etc/ecs/ecs.config
echo "ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true" >> /etc/ecs/ecs.config

# Install additional packages
yum install -y amazon-efs-utils nfs-utils

# Start ECS agent
systemctl enable --now ecs

# CloudWatch agent for additional metrics
yum install -y amazon-cloudwatch-agent

echo "User data script completed successfully"
