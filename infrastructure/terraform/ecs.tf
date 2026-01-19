# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled" # Container Insights for monitoring
  }

  tags = local.common_tags
}

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/aws/ecs/${local.name_prefix}-backend"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = local.common_tags
}

# ECS Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest" # 초기 이미지, 배포 시 업데이트됨

      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "S3_BUCKET_NAME"
          value = aws_s3_bucket.main.id
        },
        {
          name  = "RDS_ENDPOINT"
          value = aws_db_instance.main.address
        },
        {
          name  = "RDS_PORT"
          value = tostring(aws_db_instance.main.port)
        },
        {
          name  = "RDS_DATABASE"
          value = aws_db_instance.main.db_name
        },
        {
          name  = "RDS_USERNAME"
          value = var.db_username
        }
      ]

      secrets = [
        # Secrets Manager에서 가져올 경우 (선택사항)
        # {
        #   name      = "RDS_PASSWORD"
        #   valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:triflow/${var.environment}/database:password::"
        # }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = local.common_tags
}

# ECS Service
resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false # Private Subnet이므로 false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ecs.arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_maximum_percent         = 200  # Rolling update: 2배까지 증가 가능
  deployment_minimum_healthy_percent = 100  # 최소 100% 유지 (무중단 배포)

  deployment_circuit_breaker {
    enable   = true
    rollback = true  # Health check 실패 시 자동 롤백
  }

  health_check_grace_period_seconds = 60  # ALB Health check 유예 시간

  tags = local.common_tags

  depends_on = [
    aws_lb_listener.https,
    aws_iam_role_policy_attachment.ecs_task_execution
  ]
}

# ECS Auto Scaling Target
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.ecs_max_count
  min_capacity       = var.ecs_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Auto Scaling Policy: Scale Out (CPU > 70%)
resource "aws_appautoscaling_policy" "ecs_scale_out" {
  name               = "${local.name_prefix}-ecs-scale-out"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0 # CPU 70% 목표
    scale_in_cooldown  = 300  # Scale in 후 5분 대기
    scale_out_cooldown = 60   # Scale out 후 1분 대기
  }
}

# CloudWatch Alarm: ECS Memory High
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${local.name_prefix}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 180 # 3분
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "ECS memory utilization exceeds 90%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.backend.name
  }

  tags = local.common_tags
}
