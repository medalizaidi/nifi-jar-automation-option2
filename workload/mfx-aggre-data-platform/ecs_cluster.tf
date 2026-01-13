resource "aws_ecs_cluster" "nifi" {
  name = "nifi-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"

      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs_exec.name
      }
    }
  }

  tags = {
    Name = "nifi-cluster"
  }
}

resource "aws_cloudwatch_log_group" "ecs_exec" {
  name              = "/ecs/exec/nifi"
  retention_in_days = 30
}

resource "aws_ecs_cluster_capacity_providers" "nifi" {
  cluster_name = aws_ecs_cluster.nifi.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}
