resource "aws_ecs_service" "nifi" {
  name            = "nifi-service"
  cluster         = aws_ecs_cluster.nifi.id
  task_definition = aws_ecs_task_definition.nifi.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.nifi_ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nifi.arn
    container_name   = "nifi"
    container_port   = 8443
  }

  enable_execute_command = true

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = {
    Name = "nifi-service"
  }
}
