# agent-factory — GCP deploy module (thin).
# Maps the cloud-agnostic roles (container host, scheduler, queue, secrets, blob)
# to GCP services. One Dockerfile, swapped behind the same interfaces in app code.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "image" {
  type        = string
  description = "Container image for the factory (built from the repo Dockerfile)."
}

# Container host -> Cloud Run (always-on, scale-to-zero off for heartbeat workloads).
resource "google_cloud_run_v2_service" "factory" {
  name     = "agent-factory"
  location = var.region
  template {
    scaling { min_instance_count = 1 }
    containers {
      image = var.image
      ports { container_port = 8080 }
    }
  }
}

# Heartbeat -> Cloud Scheduler (Scheduler interface).
resource "google_cloud_scheduler_job" "heartbeat" {
  name     = "agent-factory-heartbeat"
  schedule = "* * * * *"
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.factory.uri}/internal/heartbeat"
  }
}

# Job queue -> Cloud Tasks (Queue interface).
resource "google_cloud_tasks_queue" "tasks" {
  name     = "agent-factory-tasks"
  location = var.region
}

# Object store -> GCS (Blob interface). Secrets -> Secret Manager (SecretStore interface).
resource "google_storage_bucket" "artifacts" {
  name     = "${var.project_id}-agent-factory-artifacts"
  location = var.region
}

output "service_uri" { value = google_cloud_run_v2_service.factory.uri }
