# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-db-subnet-group"
    }
  )
}

# RDS Parameter Group for PostgreSQL 14
resource "aws_db_parameter_group" "main" {
  name   = "${local.name_prefix}-postgres14-params"
  family = "postgres14"

  # pgvector 최적화
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_statement"
    value = "mod" # DML/DDL 로그
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # 1초 이상 쿼리만 로그
  }

  parameter {
    name  = "max_connections"
    value = "100"
  }

  tags = local.common_tags
}

# RDS PostgreSQL Instance (Multi-AZ)
resource "aws_db_instance" "main" {
  identifier = "${local.name_prefix}-db"

  # Engine
  engine         = "postgres"
  engine_version = "14.10"
  instance_class = var.db_instance_class

  # Storage
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  iops                  = 3000 # gp3 기본값

  # Database
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # High Availability
  multi_az               = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.main.name

  # Backup
  backup_retention_period = var.db_backup_retention_period
  backup_window           = "18:00-19:00"      # UTC (한국 03:00-04:00)
  maintenance_window      = "mon:19:00-mon:20:00"  # UTC (한국 월 04:00-05:00), 형식: ddd:hh24:mi-ddd:hh24:mi
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # Monitoring
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60 # Enhanced Monitoring (1분 간격)
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # Protection
  deletion_protection   = true
  copy_tags_to_snapshot = true

  # Auto Minor Version Upgrade
  auto_minor_version_upgrade = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name_prefix}-db"
    }
  )

  lifecycle {
    ignore_changes = [
      final_snapshot_identifier # 매번 timestamp 변경 무시
    ]
  }
}

# IAM Role for RDS Enhanced Monitoring
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# CloudWatch Alarm: RDS CPU
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300 # 5분
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU exceeds 80%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

# CloudWatch Alarm: RDS Storage
resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${local.name_prefix}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 10737418240 # 10 GB in bytes
  alarm_description   = "RDS free storage less than 10GB"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

# CloudWatch Alarm: RDS Connections
resource "aws_cloudwatch_metric_alarm" "rds_connections_high" {
  alarm_name          = "${local.name_prefix}-rds-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS connections exceed 80"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}
