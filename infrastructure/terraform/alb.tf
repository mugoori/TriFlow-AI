# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = true  # 실수로 삭제 방지
  enable_http2               = true
  enable_cross_zone_load_balancing = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-alb"
    }
  )
}

# Target Group for ECS Tasks
resource "aws_lb_target_group" "ecs" {
  name        = "${local.name_prefix}-ecs-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"  # Fargate는 IP 타입

  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    port                = 8000
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30  # 종료 전 연결 대기 시간

  stickiness {
    enabled         = true
    type            = "lb_cookie"
    cookie_duration = 3600  # 1시간
    cookie_name     = "TRIFLOW_LB_COOKIE"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-ecs-tg"
    }
  )
}

# ALB Listener: HTTP → HTTPS Redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }

  tags = local.common_tags
}

# ALB Listener: HTTPS → ECS Target Group
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.alb_certificate_arn != "" ? var.alb_certificate_arn : aws_acm_certificate.main[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ecs.arn
  }

  tags = local.common_tags

  depends_on = [aws_acm_certificate_validation.main]
}

# ACM Certificate (도메인 있을 경우에만 생성)
resource "aws_acm_certificate" "main" {
  count = var.domain_name != "" ? 1 : 0

  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"  # 와일드카드
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-cert"
    }
  )
}

# ACM Certificate Validation (Route 53 사용 시)
resource "aws_acm_certificate_validation" "main" {
  count = var.domain_name != "" ? 1 : 0

  certificate_arn = aws_acm_certificate.main[0].arn

  depends_on = [aws_acm_certificate.main]
}

# CloudWatch Alarm: ALB 5xx Errors
resource "aws_cloudwatch_metric_alarm" "alb_5xx_high" {
  alarm_name          = "${local.name_prefix}-alb-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60  # 1분
  statistic           = "Sum"
  threshold           = 10  # 1분에 10개 이상
  alarm_description   = "ALB 5xx errors exceed 10 per minute"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.ecs.arn_suffix
  }

  tags = local.common_tags
}

# CloudWatch Alarm: ALB Latency High
resource "aws_cloudwatch_metric_alarm" "alb_latency_high" {
  alarm_name          = "${local.name_prefix}-alb-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300  # 5분
  extended_statistic  = "p95"
  threshold           = 2.0  # 2초
  alarm_description   = "ALB P95 latency exceeds 2 seconds"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}

# CloudWatch Alarm: Unhealthy Targets
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  alarm_name          = "${local.name_prefix}-alb-unhealthy-hosts"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 1  # 최소 1개 이상 healthy
  alarm_description   = "No healthy targets available"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    TargetGroup  = aws_lb_target_group.ecs.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = local.common_tags
}
