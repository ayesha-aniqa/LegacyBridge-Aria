# Hosting LegacyBridge Backend on Google Cloud

This guide explains how to host the **LegacyBridge Backend** on **Google Cloud Run**. This setup provides a scalable, serverless environment that integrates seamlessly with Gemini 2.0 Flash and other Google Cloud services.

---

## 🏗️ Deployment Architecture

As shown in the [Architecture Diagram](../docs/assets/architecture.svg), the backend acts as a bridge between the local client and Google's AI models.

*   **Platform**: Google Cloud Run (Serverless Containers)
*   **Model**: Gemini 2.0 Flash (via Vertex AI)
*   **Optimization**: Built-in pHash deduplication and LRU caching to minimize latency and costs.

---

## 🛠️ Option 1: Quick Deployment (gcloud CLI)

This is the fastest way to get your backend online for the hackathon.

### 1. Prerequisites
*   Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install).
*   Create a project on the [Google Cloud Console](https://console.cloud.google.com/).
*   Enable the required APIs:
    ```bash
    gcloud services enable run.googleapis.com \
                           containerregistry.googleapis.com \
                           aiplatform.googleapis.com
    ```

### 2. Build and Push the Container
Run these commands from the `server/` directory:
```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Build the image using Cloud Build (no local Docker required)
gcloud builds submit --tag gcr.io/$PROJECT_ID/legacybridge-backend .
```

### 3. Deploy to Cloud Run
```bash
gcloud run deploy legacybridge-backend \
  --image gcr.io/$PROJECT_ID/legacybridge-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1"
```

---

## 🤖 Option 2: Infrastructure as Code (Terraform)

For a production-grade setup (and bonus points!), use the provided Terraform scripts in the `infra/` directory.

### 1. Configuration
Update `infra/variables.tf` with your project details:
```hcl
variable "project_id" {
  default = "your-project-id"
}

variable "region" {
  default = "us-central1"
}
```

### 2. Deployment
```bash
cd infra
terraform init
terraform apply
```

---

## 🔐 Permissions & Authentication

The backend uses **Vertex AI** to communicate with Gemini. Ensure the Cloud Run service account has the necessary permissions:

1.  Go to **IAM & Admin** > **IAM** in the Cloud Console.
2.  Find the service account used by Cloud Run (usually `PROJECT_NUMBER-compute@developer.gserviceaccount.com`).
3.  Add the role: **Vertex AI User**.

---

## 🔗 Connecting the Client

Once deployed, Google Cloud Run will provide a URL (e.g., `https://legacybridge-backend-xyz.a.run.app`). 

Update your local `.env` file in the `client/` directory:
```env
BACKEND_URL=https://legacybridge-backend-xyz.a.run.app
```

---

## 🚀 Scaling & Costs
*   **Concurrency**: Cloud Run can handle multiple users per instance.
*   **Scale to Zero**: When not in use, Cloud Run scales down to 0 instances, meaning you only pay for the exact milliseconds the backend is processing a request.
*   **Free Tier**: Google Cloud offers a generous free tier for Cloud Run and Vertex AI.
