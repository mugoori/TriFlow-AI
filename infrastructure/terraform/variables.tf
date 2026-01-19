variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-northeast-2"
}

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "triflow-ai"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability Zones"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

# RDS Configuration
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  description = "RDS storage size in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "RDS max storage size for auto-scaling"
  type        = number
  default     = 200
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "triflow"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "triflow_admin"
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_backup_retention_period" {
  description = "Days to retain backups"
  type        = number
  default     = 7
}

# ECS Configuration
variable "ecs_task_cpu" {
  description = "ECS task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 1024 # 1 vCPU
}

variable "ecs_task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 2048 # 2 GB
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_min_count" {
  description = "Minimum number of ECS tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "ecs_max_count" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
  default     = 5
}

# ElastiCache Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.small"
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters (Primary + Replicas)"
  type        = number
  default     = 2
}

variable "redis_auth_token" {
  description = "Redis authentication token (password)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_snapshot_retention_limit" {
  description = "Number of days to retain Redis snapshots"
  type        = number
  default     = 5
}

# S3 Configuration
variable "s3_bucket_name" {
  description = "S3 bucket name"
  type        = string
  default     = "triflow-ai-prod"
}

variable "s3_lifecycle_glacier_days" {
  description = "Days before transitioning to Glacier"
  type        = number
  default     = 90
}

# ALB Configuration
variable "alb_certificate_arn" {
  description = "ACM certificate ARN for HTTPS (optional, will create if not provided)"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain name for Route 53 (optional)"
  type        = string
  default     = ""
}

# CloudWatch Configuration
variable "cloudwatch_log_retention_days" {
  description = "CloudWatch Logs retention in days"
  type        = number
  default     = 15
}

# Slack Integration
variable "slack_webhook_url" {
  description = "Slack webhook URL for CloudWatch alarms"
  type        = string
  sensitive   = true
  default     = ""
}

# Tags
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
