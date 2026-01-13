resource "aws_efs_file_system" "nifi_efs" {
  creation_token = "nifi-flow-config"
  encrypted      = true

  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = {
    Name = "nifi-efs"
  }
}

resource "aws_efs_mount_target" "nifi" {
  count = length(var.private_subnet_ids)

  file_system_id  = aws_efs_file_system.nifi_efs.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "nifi_access_point" {
  file_system_id = aws_efs_file_system.nifi_efs.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/nifi-flow"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "nifi-access-point"
  }
}

resource "aws_security_group" "efs" {
  name        = "nifi-efs-sg"
  description = "Security group for NiFi EFS"
  vpc_id      = var.vpc_id

  ingress {
    description     = "NFS from ECS"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.nifi_ecs.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "nifi-efs-sg"
  }
}
