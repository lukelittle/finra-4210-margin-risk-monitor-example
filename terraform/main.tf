terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "margin-risk-monitor"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "margin-risk-monitor"
}

# VPC for MSK
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"
  
  tags = {
    Name = "${var.project_name}-private-a"
  }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"
  
  tags = {
    Name = "${var.project_name}-private-b"
  }
}

resource "aws_subnet" "private_c" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "${var.aws_region}c"
  
  tags = {
    Name = "${var.project_name}-private-c"
  }
}

# Security group for MSK
resource "aws_security_group" "msk" {
  name        = "${var.project_name}-msk-sg"
  description = "Security group for MSK cluster"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }
  
  ingress {
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.project_name}-msk-sg"
  }
}

# MSK Serverless Cluster
resource "aws_msk_serverless_cluster" "main" {
  cluster_name = "${var.project_name}-cluster"
  
  vpc_config {
    subnet_ids         = [
      aws_subnet.private_a.id,
      aws_subnet.private_b.id,
      aws_subnet.private_c.id
    ]
    security_group_ids = [aws_security_group.msk.id]
  }
  
  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }
}

# S3 bucket for Spark artifacts and audit trail
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  
  rule {
    id     = "audit-retention"
    status = "Enabled"
    
    filter {
      prefix = "audit/"
    }
    
    expiration {
      days = 90
    }
  }
}

# DynamoDB table for account state
resource "aws_dynamodb_table" "account_state" {
  name           = "${var.project_name}-account-state"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "account_id"
  range_key      = "timestamp"
  
  attribute {
    name = "account_id"
    type = "S"
  }
  
  attribute {
    name = "timestamp"
    type = "N"
  }
  
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
  
  tags = {
    Name = "${var.project_name}-account-state"
  }
}

# IAM role for EMR Serverless
resource "aws_iam_role" "emr_serverless" {
  name = "${var.project_name}-emr-serverless-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "emr-serverless.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "emr_serverless" {
  name = "${var.project_name}-emr-serverless-policy"
  role = aws_iam_role.emr_serverless.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:AlterCluster",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData"
        ]
        Resource = aws_msk_serverless_cluster.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:CreateTopic",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData"
        ]
        Resource = "${aws_msk_serverless_cluster.main.arn}/*"
      }
    ]
  })
}

# EMR Serverless Application
resource "aws_emrserverless_application" "spark" {
  name          = "${var.project_name}-spark-app"
  release_label = "emr-7.0.0"
  type          = "Spark"
  
  # Maximum capacity (scales up to this)
  maximum_capacity {
    cpu    = "4 vCPU"
    memory = "16 GB"
  }
  
  # Pre-initialized capacity (keeps workers warm)
  # This is realistic for production systems that need low latency
  # Trade-off: Pay for idle capacity vs. fast startup
  initial_capacity {
    initial_capacity_type = "Driver"
    
    initial_capacity_config {
      worker_count = 1
      
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }
  
  initial_capacity {
    initial_capacity_type = "Executor"
    
    initial_capacity_config {
      worker_count = 2
      
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }
  
  auto_start_configuration {
    enabled = true
  }
  
  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 15
  }
  
  tags = {
    Purpose = "Real-time margin risk monitoring"
    Pattern = "Pre-initialized workers for low latency"
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_enforcement" {
  name = "${var.project_name}-lambda-enforcement-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_enforcement.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_enforcement" {
  name = "${var.project_name}-lambda-enforcement-policy"
  role = aws_iam_role.lambda_enforcement.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster",
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData"
        ]
        Resource = [
          aws_msk_serverless_cluster.main.arn,
          "${aws_msk_serverless_cluster.main.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.account_state.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.artifacts.arn}/audit/*"
      }
    ]
  })
}

# Lambda function (placeholder - actual code deployed separately)
resource "aws_lambda_function" "enforcement" {
  filename      = "lambda_placeholder.zip"
  function_name = "${var.project_name}-enforcement"
  role          = aws_iam_role.lambda_enforcement.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 512
  
  environment {
    variables = {
      KAFKA_BROKERS    = aws_msk_serverless_cluster.main.bootstrap_brokers_sasl_iam
      DYNAMODB_TABLE   = aws_dynamodb_table.account_state.name
      S3_AUDIT_BUCKET  = aws_s3_bucket.artifacts.id
    }
  }
  
  vpc_config {
    subnet_ids         = [
      aws_subnet.private_a.id,
      aws_subnet.private_b.id
    ]
    security_group_ids = [aws_security_group.msk.id]
  }
}

# Data source
data "aws_caller_identity" "current" {}

# Outputs
output "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  value       = aws_msk_serverless_cluster.main.bootstrap_brokers_sasl_iam
}

output "s3_bucket" {
  description = "S3 bucket for artifacts"
  value       = aws_s3_bucket.artifacts.id
}

output "dynamodb_table" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.account_state.name
}

output "emr_application_id" {
  description = "EMR Serverless application ID"
  value       = aws_emrserverless_application.spark.id
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.enforcement.function_name
}
