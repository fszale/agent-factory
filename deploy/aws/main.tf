# agent-factory — AWS deploy module (thin).
# Maps the cloud-agnostic roles (container host, scheduler, queue, secrets, blob)
# to AWS services. Same Dockerfile and app code as GCP; only this module differs.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "image" {
  type        = string
  description = "Container image for the factory (built from the repo Dockerfile)."
}

provider "aws" { region = var.region }

# Container host -> ECS Fargate (always-on service).
resource "aws_ecs_cluster" "factory" {
  name = "agent-factory"
}

# Heartbeat -> EventBridge Scheduler (Scheduler interface).
resource "aws_scheduler_schedule" "heartbeat" {
  name                         = "agent-factory-heartbeat"
  schedule_expression          = "rate(1 minute)"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_ecs_cluster.factory.arn
    role_arn = "REPLACE_WITH_EXECUTION_ROLE_ARN"
  }
}

# Job queue -> SQS (Queue interface).
resource "aws_sqs_queue" "tasks" {
  name = "agent-factory-tasks"
}

# Object store -> S3 (Blob interface). Secrets -> Secrets Manager (SecretStore interface).
resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "agent-factory-artifacts-"
}

output "cluster_arn" { value = aws_ecs_cluster.factory.arn }
