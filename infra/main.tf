terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file("../credentials.json")
}

# Enable required APIs
resource "google_project_service" "run" {
  service = "run.googleapis.com"
}

resource "google_project_service" "generativelanguage" {
  service = "generativelanguage.googleapis.com"
}

resource "google_project_service" "texttospeech" {
  service = "texttospeech.googleapis.com"
}

# Cloud Run service for backend
resource "google_cloud_run_v2_service" "backend" {
  name     = "legacybridge-backend"
  location = var.region

  template {
    containers {
      image = "gcr.io/${var.project_id}/legacybridge-backend:latest"

      env {
        name  = "GOOGLE_API_KEY"
        value = var.google_api_key
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [google_project_service.run]
}

# Allow public access to Cloud Run
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}