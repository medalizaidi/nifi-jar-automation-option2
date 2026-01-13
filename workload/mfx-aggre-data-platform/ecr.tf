resource "aws_ecr_repository" "nifi" {
  name                 = "apache-nifi-with-custom-jars-repo"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "apache-nifi-with-custom-jars-repo"
  }
}

resource "aws_ecr_lifecycle_policy" "nifi" {
  repository = aws_ecr_repository.nifi.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.nifi.repository_url
}
