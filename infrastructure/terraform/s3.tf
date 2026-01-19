# S3 Bucket
resource "aws_s3_bucket" "main" {
  bucket = var.s3_bucket_name

  tags = merge(
    local.common_tags,
    {
      Name = var.s3_bucket_name
    }
  )
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"  # SSE-S3 (무료)
    }
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Lifecycle Rules
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  # Rule 1: Workflow results → Glacier after 90 days
  rule {
    id     = "archive-workflows"
    status = "Enabled"

    filter {
      prefix = "tenants/*/workflows/"
    }

    transition {
      days          = var.s3_lifecycle_glacier_days
      storage_class = "GLACIER"
    }
  }

  # Rule 2: Exports → Glacier after 90 days
  rule {
    id     = "archive-exports"
    status = "Enabled"

    filter {
      prefix = "tenants/*/exports/"
    }

    transition {
      days          = var.s3_lifecycle_glacier_days
      storage_class = "GLACIER"
    }
  }

  # Rule 3: Logs → Delete after 365 days
  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    filter {
      prefix = "tenants/*/logs/"
    }

    expiration {
      days = 365
    }
  }

  # Rule 4: Abort incomplete multipart uploads
  rule {
    id     = "abort-multipart-uploads"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# S3 Bucket Policy (IAM Role 기반 접근)
resource "aws_s3_bucket_policy" "main" {
  bucket = aws_s3_bucket.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSTaskAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task.arn
        }
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "${aws_s3_bucket.main.arn}",
          "${aws_s3_bucket.main.arn}/*"
        ]
      },
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.main.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })
}
