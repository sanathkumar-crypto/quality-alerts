# Cloud Run Deployment Guide

This guide explains how to deploy the Quality Alerts application to Google Cloud Run and set up automated alerts using Cloud Scheduler.

## Prerequisites

1. **Google Cloud Project**: You need a GCP project with billing enabled
2. **gcloud CLI**: Install and configure the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
3. **Docker**: Install [Docker](https://docs.docker.com/get-docker/) for local builds
4. **Authentication**: Authenticate with GCP:
   ```bash
   gcloud auth login
   gcloud auth configure-docker
   ```

## Quick Start

### 1. Set Up Environment Variables

The deployment script will read environment variables from your `.env` file. Make sure it contains:

```bash
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/...
GOOGLE_CHAT_WEBHOOK_URLS=https://chat.googleapis.com/v1/spaces/... (optional)
```

**Note**: The `.env` file is excluded from the Docker image for security. Environment variables will be set directly in Cloud Run.

### 2. Deploy to Cloud Run

Run the deployment script:

```bash
./deploy.sh [SERVICE_NAME] [REGION] [PROJECT_ID]
```

Example:
```bash
./deploy.sh quality-alerts us-central1 my-gcp-project
```

The script will:
- Build the Docker image
- Push it to Google Container Registry or Artifact Registry
- Deploy to Cloud Run
- Set environment variables from your `.env` file
- Output the service URL

### 3. Set Up Cloud Scheduler for Automated Alerts

After deployment, set up Cloud Scheduler to trigger alerts every Monday at 9am:

```bash
# Get your service URL first
SERVICE_URL=$(gcloud run services describe quality-alerts --region=us-central1 --format='value(status.url)')

# Create the scheduler job
gcloud scheduler jobs create http monday-9am-alerts \
  --location=us-central1 \
  --schedule="0 9 * * 1" \
  --uri="${SERVICE_URL}/api/trigger-scheduled-alert?model_id=model10" \
  --http-method=GET \
  --time-zone="America/New_York" \
  --description="Trigger quality alerts every Monday at 9am"
```

**Important**: Cloud Scheduler needs permission to invoke your Cloud Run service. If your service requires authentication, you'll need to:

1. Create a service account for Cloud Scheduler:
   ```bash
   gcloud iam service-accounts create cloud-scheduler-sa \
     --display-name="Cloud Scheduler Service Account"
   ```

2. Grant it permission to invoke Cloud Run:
   ```bash
   gcloud run services add-iam-policy-binding quality-alerts \
     --region=us-central1 \
     --member="serviceAccount:cloud-scheduler-sa@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.invoker"
   ```

3. Update the scheduler job to use the service account:
   ```bash
   gcloud scheduler jobs update http monday-9am-alerts \
     --location=us-central1 \
     --oidc-service-account-email=cloud-scheduler-sa@PROJECT_ID.iam.gserviceaccount.com
   ```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Build and Push Docker Image

```bash
# Set variables
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="quality-alerts"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/quality-alerts/${SERVICE_NAME}"

# Build
docker build -t ${IMAGE_NAME}:latest .

# Push
gcloud auth configure-docker ${REGION}-docker.pkg.dev
docker push ${IMAGE_NAME}:latest
```

### 2. Deploy to Cloud Run

```bash
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars "FLASK_ENV=production,GOOGLE_CHAT_WEBHOOK_URL=your-webhook-url"
```

### 3. Configure Service Account for BigQuery Access

**Option A: Use Cloud Run Service Account (Recommended)**

This is the recommended approach - no key file needed. Cloud Run will use the service account's credentials automatically.

1. **Create or use an existing service account:**
   ```bash
   # Create a service account (if you don't have one)
   gcloud iam service-accounts create quality-alerts-sa \
     --display-name="Quality Alerts Service Account"
   
   # Grant BigQuery access
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:quality-alerts-sa@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.user"
   
   # Grant BigQuery Data Viewer role (to read data)
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:quality-alerts-sa@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.dataViewer"
   ```

2. **Deploy with the service account:**
   ```bash
   gcloud run deploy quality-alerts \
     --service-account=quality-alerts-sa@PROJECT_ID.iam.gserviceaccount.com \
     --region=us-central1 \
     # ... other flags
   ```

**Option B: Use Service Account Key File (Alternative)**

If you need to use a specific service account key file:

1. **Create and download the key:**
   ```bash
   # Create key file
   gcloud iam service-accounts keys create service-account-key.json \
     --iam-account=quality-alerts-sa@PROJECT_ID.iam.gserviceaccount.com
   ```

2. **Store in Secret Manager (Recommended):**
   ```bash
   # Create secret
   gcloud secrets create service-account-key \
     --data-file=service-account-key.json
   
   # Deploy with secret mounted
   gcloud run deploy quality-alerts \
     --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=service-account-key:latest \
     --region=us-central1 \
     # ... other flags
   ```

3. **Or set as environment variable (Less Secure):**
   ```bash
   # Base64 encode the key file
   KEY_BASE64=$(base64 -i service-account-key.json)
   
   # Deploy with environment variable
   gcloud run deploy quality-alerts \
     --set-env-vars "GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json" \
     --update-secrets=/tmp/sa-key.json=service-account-key:latest \
     --region=us-central1
   ```

**Note**: The application uses Application Default Credentials (ADC), which means:
- If `GOOGLE_APPLICATION_CREDENTIALS` is set, it will use that file
- Otherwise, it will use the Cloud Run service account credentials automatically
- **Option A is recommended** as it's more secure and easier to manage

### 4. Set Environment Variables

You can set environment variables during deployment or update them later:

```bash
# During deployment (add to --set-env-vars)
--set-env-vars "FLASK_ENV=production,GOOGLE_CHAT_WEBHOOK_URL=url1,GOOGLE_CHAT_WEBHOOK_URLS=url2,url3"

# Or update existing service
gcloud run services update quality-alerts \
  --region=us-central1 \
  --update-env-vars "GOOGLE_CHAT_WEBHOOK_URL=your-url"
```

## Using Cloud Build (CI/CD)

For automated deployments from Git:

### 1. Connect Repository

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
2. Connect your GitHub/GitLab/Bitbucket repository
3. Create a trigger that builds on push to main branch

### 2. Configure Build

The `cloudbuild.yaml` file is already configured. You may need to:

1. Create an Artifact Registry repository:
   ```bash
   gcloud artifacts repositories create quality-alerts \
     --repository-format=docker \
     --location=us-central1
   ```

2. Update substitution variables in the trigger:
   - `_SERVICE_NAME`: quality-alerts
   - `_REGION`: us-central1
   - `_REPO_NAME`: quality-alerts

3. Set environment variables as secrets in Secret Manager (recommended) or as substitution variables.

## Testing

### Test the Service

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe quality-alerts --region=us-central1 --format='value(status.url)')

# Test health endpoint
curl ${SERVICE_URL}/

# Test scheduled alert endpoint
curl ${SERVICE_URL}/api/trigger-scheduled-alert?model_id=model10
```

### Test Cloud Scheduler Job

```bash
# Run the job immediately (for testing)
gcloud scheduler jobs run monday-9am-alerts --location=us-central1

# Check job status
gcloud scheduler jobs describe monday-9am-alerts --location=us-central1
```

## Monitoring and Logs

### View Cloud Run Logs

```bash
gcloud run services logs read quality-alerts --region=us-central1 --limit=50
```

Or in the console: [Cloud Run Logs](https://console.cloud.google.com/run)

### View Cloud Scheduler Execution History

```bash
gcloud scheduler jobs describe monday-9am-alerts --location=us-central1
```

Or in the console: [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)

## Troubleshooting

### Service Won't Start

1. Check logs: `gcloud run services logs read quality-alerts --region=us-central1`
2. Verify environment variables are set correctly
3. Check that BigQuery credentials are configured (service account or default credentials)

### Alerts Not Sending

1. Verify webhook URLs are set in Cloud Run environment variables
2. Test the endpoint manually: `curl ${SERVICE_URL}/api/trigger-scheduled-alert?model_id=model10`
3. Check Cloud Run logs for errors
4. Verify Cloud Scheduler job is running and has proper permissions

### Cloud Scheduler Not Triggering

1. Check job status: `gcloud scheduler jobs describe monday-9am-alerts --location=us-central1`
2. Verify the service URL is correct
3. Check IAM permissions for the scheduler service account
4. Test the job manually: `gcloud scheduler jobs run monday-9am-alerts --location=us-central1`

### Database Issues

**Important**: SQLite databases are ephemeral in Cloud Run. The application primarily uses BigQuery as the data source, so this should not be an issue. However, if you need persistent storage:

1. Use Cloud SQL for PostgreSQL/MySQL
2. Use Cloud Storage for SQLite file (with limitations)
3. Keep using BigQuery as the primary data source (recommended)

## Cost Optimization

- **Min instances**: Set to 0 to allow scaling to zero (saves money when not in use)
- **Max instances**: Limit based on expected load
- **Memory/CPU**: Adjust based on actual usage (start with 2Gi/2 CPU)
- **Timeout**: Set appropriate timeout (300s default)

## Security Best Practices

1. **Environment Variables**: Use Secret Manager for sensitive values:
   ```bash
   gcloud secrets create webhook-url --data-file=webhook-url.txt
   gcloud run services update quality-alerts \
     --update-secrets=GOOGLE_CHAT_WEBHOOK_URL=webhook-url:latest
   ```

2. **Authentication**: Consider requiring authentication for the service:
   ```bash
   gcloud run services update quality-alerts \
     --region=us-central1 \
     --no-allow-unauthenticated
   ```

3. **IAM**: Use least privilege principle for service accounts

## Updating the Service

### Update Code and Redeploy

```bash
# Make your changes, then:
./deploy.sh quality-alerts us-central1 PROJECT_ID
```

### Update Environment Variables

```bash
gcloud run services update quality-alerts \
  --region=us-central1 \
  --update-env-vars "GOOGLE_CHAT_WEBHOOK_URL=new-url"
```

### Rollback to Previous Revision

```bash
# List revisions
gcloud run revisions list --service=quality-alerts --region=us-central1

# Rollback to specific revision
gcloud run services update-traffic quality-alerts \
  --region=us-central1 \
  --to-revisions=REVISION_NAME=100
```

## Architecture

```
Cloud Scheduler (Every Monday 9am)
    ↓
Cloud Run Service (/api/trigger-scheduled-alert)
    ↓
Google Chat Webhooks (Send alerts)
    ↑
BigQuery (Data source)
```

## Support

For issues or questions:
1. Check Cloud Run logs
2. Check Cloud Scheduler execution history
3. Review this documentation
4. Check the main README.md for application-specific issues

