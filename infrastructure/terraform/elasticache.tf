# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis-subnet-group"
    }
  )
}

# ElastiCache Parameter Group (Redis 7.x)
resource "aws_elasticache_parameter_group" "main" {
  name   = "${local.name_prefix}-redis7-params"
  family = "redis7"

  # 세션 타임아웃
  parameter {
    name  = "timeout"
    value = "300" # 5분
  }

  # 최대 메모리 정책 (LRU)
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = local.common_tags
}

# Security Group for ElastiCache
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.main.id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis-sg"
    }
  )
}

# Security Group Rule: ECS → Redis
resource "aws_security_group_rule" "ecs_to_redis" {
  type                     = "egress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs.id
  source_security_group_id = aws_security_group.redis.id
  description              = "To ElastiCache Redis"
}

# Security Group Rule: Redis ← ECS
resource "aws_security_group_rule" "redis_from_ecs" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.redis.id
  source_security_group_id = aws_security_group.ecs.id
  description              = "Redis from ECS"
}

# ElastiCache Replication Group (Primary + Replica)
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "TriFlow AI Redis cluster for session storage and caching"

  # Engine
  engine               = "redis"
  engine_version       = "7.0"
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  # Node configuration
  node_type          = var.redis_node_type
  num_cache_clusters = var.redis_num_cache_clusters

  # Network
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  # High Availability
  automatic_failover_enabled = true
  multi_az_enabled           = true

  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token != "" ? var.redis_auth_token : null

  # Backup
  snapshot_retention_limit = 5                     # 5일 보관
  snapshot_window          = "17:00-18:00"         # UTC (한국 02:00-03:00)
  maintenance_window       = "sun:18:00-sun:19:00" # UTC (한국 일 03:00-04:00)

  # Auto minor version upgrade
  auto_minor_version_upgrade = true

  # 로그
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-redis"
    }
  )
}

# CloudWatch Log Group for ElastiCache
resource "aws_cloudwatch_log_group" "redis" {
  name              = "/aws/elasticache/${local.name_prefix}-redis"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = local.common_tags
}

# CloudWatch Alarm: Redis CPU High
resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "${local.name_prefix}-redis-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300 # 5분
  statistic           = "Average"
  threshold           = 75
  alarm_description   = "Redis CPU exceeds 75%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = local.common_tags
}

# CloudWatch Alarm: Redis Memory High
resource "aws_cloudwatch_metric_alarm" "redis_memory_high" {
  alarm_name          = "${local.name_prefix}-redis-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "Redis memory usage exceeds 90%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = local.common_tags
}

# CloudWatch Alarm: Redis Evictions
resource "aws_cloudwatch_metric_alarm" "redis_evictions" {
  alarm_name          = "${local.name_prefix}-redis-evictions"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Evictions"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "Redis evictions exceed 100 per 5 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.main.id
  }

  tags = local.common_tags
}
