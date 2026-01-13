resource "aws_ecs_task_definition" "nifi" {
  family                   = "nifi-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 12288
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      "name" : "nifi",
      "image" : "478874601698.dkr.ecr.ap-northeast-1.amazonaws.com/apache-nifi-with-custom-jars-repo:latest",
      "essential" : true,

      "cpu" : 2048,
      "memory" : 12288,
      "memoryReservation" : 8192,
      "linuxParameters" : {
        "initProcessEnabled" : true
      },
      "user" : "1000", # Explicitly run as UID 1000 (standard for non-root NiFi user)

      "environment" : [
        { "name" : "NIFI_WEB_HTTP_HOST", "value" : "" },
        { "name" : "NIFI_JVM_HEAP_MAX", "value" : "8g" },
        { "name" : "NIFI_CLUSTER_IS_NODE", "value" : "false" },
        {
          "name" : "NIFI_WEB_PROXY_HOST",
          "value" : "data.ingestion-ui.x.test.mfw.work:443,data.ingestion-ui.x.test.mfw.work,k8s-stgmfxag-mfxaggre-b743a3-1234567890.ap-northeast-1.elb.amazonaws.com"
        },
        { "name" : "NIFI_WEB_PROXY_CONTEXT_PATH", "value" : "/nifi" },
        { "name" : "NIFI_JVM_HEAP_INIT", "value" : "8g" },
        { "name" : "SINGLE_USER_CREDENTIALS_PASSWORD", "value" : "adminPassword123" },
        { "name" : "NIFI_WEB_HTTP_PORT", "value" : "" },
        { "name" : "SINGLE_USER_CREDENTIALS_USERNAME", "value" : "admin" },
        {
          "name" : "NIFI_WEB_HTTPS_HOST",
          "value" : ""
        },
        { "name" : "NIFI_WEB_HTTPS_PORT", "value" : "8443" },
        { "name" : "NIFI_SENSITIVE_PROPS_KEY", "value" : "my-random-string-at-least-12-chars" }
      ],

      "portMappings" : [
        {
          "containerPort" : 8443,
          "hostPort" : 8443,
          "protocol" : "tcp"
        }
      ],

      "mountPoints" : [
        {
          "sourceVolume" : "nifi-flow-config",
          "containerPath" : "/opt/nifi/nifi-current/flow_config",
          "readOnly" : false
        }
      ],

      "logConfiguration" : {
        "logDriver" : "awslogs",
        "options" : {
          "awslogs-group" : "/ecs/nifi",
          "awslogs-region" : "ap-northeast-1",
          "awslogs-stream-prefix" : "nifi"
        }
      },

      "healthCheck" : {
        "command" : ["CMD-SHELL", "curl -f https://localhost:8443/nifi/ -k || exit 1"],
        "interval" : 30,
        "timeout" : 5,
        "retries" : 3,
        "startPeriod" : 120
      }
    }
  ])

  volume {
    name = "nifi-flow-config"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.nifi_efs.id
      root_directory     = "/nifi-flow"
      transit_encryption = "ENABLED"

      authorization_config {
        access_point_id = aws_efs_access_point.nifi_access_point.id
        iam             = "ENABLED"
      }
    }
  }

  tags = {
    Name        = "nifi-task-definition"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
