# SNS Topic for CloudWatch Alarms
resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"

  tags = local.common_tags
}

# SNS Topic Subscription: Email (예시)
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tech-lead@company.com" # TODO: 실제 이메일로 변경

  # 주의: Email subscription은 수동 승인 필요
}

# SNS Topic Subscription: Slack (Lambda Function 필요, 선택사항)
# resource "aws_sns_topic_subscription" "slack" {
#   count = var.slack_webhook_url != "" ? 1 : 0
#
#   topic_arn = aws_sns_topic.alarms.arn
#   protocol  = "lambda"
#   endpoint  = aws_lambda_function.slack_notifier[0].arn
# }

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average", label = "ECS CPU" }],
            [".", "MemoryUtilization", { stat = "Average", label = "ECS Memory" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Performance"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", { stat = "Average", label = "RDS CPU" }],
            [".", "DatabaseConnections", { stat = "Average", label = "DB Connections" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "RDS Performance"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Requests" }],
            [".", "TargetResponseTime", { stat = "p95", label = "P95 Latency" }]
          ]
          period = 60
          stat   = "Average"
          region = var.aws_region
          title  = "ALB Metrics"
        }
      }
    ]
  })
}

# CloudWatch Log Metric Filter: 5xx Errors
resource "aws_cloudwatch_log_metric_filter" "api_5xx_errors" {
  name           = "${local.name_prefix}-api-5xx-errors"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  pattern        = "[time, request_id, level=ERROR, ...]"

  metric_transformation {
    name      = "API5xxErrors"
    namespace = "TriFlow/${title(var.environment)}"
    value     = "1"
    unit      = "Count"
  }
}

# CloudWatch Alarm: Application 5xx Errors
resource "aws_cloudwatch_metric_alarm" "app_5xx_errors" {
  alarm_name          = "${local.name_prefix}-app-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "API5xxErrors"
  namespace           = "TriFlow/${title(var.environment)}"
  period              = 60
  statistic           = "Sum"
  threshold           = 5 # 1분에 5개 이상
  alarm_description   = "Application 5xx errors exceed 5 per minute"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"

  tags = local.common_tags
}

# CloudWatch Billing Alarm (비용 초과)
resource "aws_cloudwatch_metric_alarm" "billing_high" {
  alarm_name          = "${local.name_prefix}-billing-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 21600 # 6시간
  statistic           = "Maximum"
  threshold           = 500 # $500 (₩650,000)
  alarm_description   = "AWS billing exceeds $500"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    Currency = "USD"
  }

  tags = local.common_tags
}
