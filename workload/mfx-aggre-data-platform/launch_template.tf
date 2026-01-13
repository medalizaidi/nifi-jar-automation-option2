# Launch template for EC2-backed ECS (if needed in future)
# Currently using Fargate, but keeping this for reference

resource "aws_launch_template" "nifi_ec2" {
  name_prefix   = "nifi-ecs-"
  image_id      = data.aws_ami.ecs_optimized.id
  instance_type = "m5.xlarge"

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance.name
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.nifi_ecs.id]
  }

  user_data = base64encode(templatefile("${path.module}/custom_nifi/user_data/nifi_user_data.sh", {
    cluster_name = aws_ecs_cluster.nifi.name
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "nifi-ecs-instance"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

data "aws_ami" "ecs_optimized" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
  }
}

resource "aws_iam_instance_profile" "ecs_instance" {
  name = "nifi-ecs-instance-profile"
  role = aws_iam_role.ecs_instance_role.name
}

resource "aws_iam_role" "ecs_instance_role" {
  name = "nifi-ecs-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_instance_role_policy" {
  role       = aws_iam_role.ecs_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}
