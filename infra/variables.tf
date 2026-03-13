variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "legacybridge-hackathon"
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "asia-south1"
}

variable "google_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
}