#!/bin/bash
# Deployment script for Google Cloud Run
# Usage: ./deploy.sh [SERVICE_NAME] [REGION] [PROJECT_ID]

set -e  # Exit on error

# Configuration
SERVICE_NAME="${1:-quality-alerts}"
REGION="${2:-us-central1}"
PROJECT_ID="${3:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set. Please provide it as third argument or set default gcloud project.${NC}"
    echo "Usage: ./deploy.sh [SERVICE_NAME] [REGION] [PROJECT_ID] [SERVICE_ACCOUNT_EMAIL_OR_SECRET_NAME]"
    echo ""
    echo "Examples:"
    echo "  # Deploy without service account (uses default)"
    echo "  ./deploy.sh quality-alerts us-central1 my-project"
    echo ""
    echo "  # Deploy with service account email (recommended)"
    echo "  ./deploy.sh quality-alerts us-central1 my-project quality-alerts-sa@my-project.iam.gserviceaccount.com"
    echo ""
    echo "  # Deploy with service account key from Secret Manager"
    echo "  ./deploy.sh quality-alerts us-central1 my-project service-account-key"
    echo "  (First upload key: ./setup-service-account-secret.sh path/to/key.json my-project)"
    exit 1
fi

echo -e "${GREEN}Deploying to Cloud Run...${NC}"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Project ID: $PROJECT_ID"
if [ -n "$4" ]; then
    if [[ "$4" == *"@"* ]]; then
        echo "Service Account: $4 (service account email)"
    else
        echo "Service Account: $4 (Secret Manager secret name)"
    fi
else
    echo "Service Account: (using default Compute Engine service account)"
    echo -e "${YELLOW}Note: For BigQuery access, consider using a service account${NC}"
fi
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install it first.${NC}"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting gcloud project to $PROJECT_ID...${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs (skip if permission denied - APIs might already be enabled)
echo -e "${YELLOW}Checking/enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com --quiet 2>/dev/null || echo "Cloud Build API may already be enabled or permission denied"
gcloud services enable run.googleapis.com --quiet 2>/dev/null || echo "Cloud Run API may already be enabled or permission denied"
gcloud services enable cloudscheduler.googleapis.com --quiet 2>/dev/null || echo "Cloud Scheduler API may already be enabled or permission denied"

# Determine image registry (use Artifact Registry if available, otherwise GCR)
IMAGE_REGISTRY="gcr.io"
ARTIFACT_REGISTRY="${REGION}-docker.pkg.dev"

# Try to use Artifact Registry, fallback to GCR
if gcloud artifacts repositories describe quality-alerts --location="$REGION" &>/dev/null; then
    IMAGE_REGISTRY="$ARTIFACT_REGISTRY"
    IMAGE_NAME="${IMAGE_REGISTRY}/${PROJECT_ID}/quality-alerts/${SERVICE_NAME}"
    echo -e "${GREEN}Using Artifact Registry: $IMAGE_NAME${NC}"
else
    IMAGE_NAME="${IMAGE_REGISTRY}/${PROJECT_ID}/${SERVICE_NAME}"
    echo -e "${YELLOW}Using Container Registry: $IMAGE_NAME${NC}"
    echo -e "${YELLOW}Note: Consider using Artifact Registry for better performance${NC}"
fi

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"

# Try local Docker build first, fallback to Cloud Build if it fails
if docker build -t "$IMAGE_NAME:latest" . 2>/dev/null; then
    echo -e "${GREEN}Local Docker build successful${NC}"
    # Configure Docker to use gcloud as credential helper
    echo -e "${YELLOW}Configuring Docker authentication...${NC}"
    gcloud auth configure-docker "$IMAGE_REGISTRY" --quiet
    
    # Push the image
    echo -e "${YELLOW}Pushing image to registry...${NC}"
    docker push "$IMAGE_NAME:latest"
else
    echo -e "${YELLOW}Local Docker build failed (likely network issue). Using Cloud Build instead...${NC}"
    echo -e "${YELLOW}Submitting build to Cloud Build...${NC}"
    
    # Use Cloud Build to build and push the image
    gcloud builds submit --tag "$IMAGE_NAME:latest" \
        --project="$PROJECT_ID" \
        --quiet
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Cloud Build also failed. Please check your network connection and try again.${NC}"
        exit 1
    fi
fi

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

# Read environment variables from .env file if it exists
ENV_VARS=""
if [ -f .env ]; then
    echo -e "${GREEN}Reading environment variables from .env file...${NC}"
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        
        # Remove quotes from value if present
        value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        
        if [ -n "$ENV_VARS" ]; then
            ENV_VARS="$ENV_VARS,"
        fi
        ENV_VARS="${ENV_VARS}${key}=${value}"
    done < .env
else
    echo -e "${YELLOW}Warning: .env file not found. You'll need to set environment variables manually.${NC}"
fi

# Check if service account is provided as 4th argument (can be email or secret name)
SERVICE_ACCOUNT_ARG=""
SECRET_ARG=""
if [ -n "$4" ]; then
    # Check if it's a secret name (starts with lowercase, no @) or service account email
    if [[ "$4" == *"@"* ]]; then
        # It's a service account email
        SERVICE_ACCOUNT_ARG="--service-account=$4"
        echo -e "${GREEN}Using service account: $4${NC}"
    else
        # It's a secret name - mount it as GOOGLE_APPLICATION_CREDENTIALS
        SECRET_NAME="$4"
        SECRET_ARG="--update-secrets=GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json=${SECRET_NAME}:latest"
        echo -e "${GREEN}Using service account key from Secret Manager: ${SECRET_NAME}${NC}"
        echo -e "${YELLOW}Note: Make sure you've uploaded the key using: ./setup-service-account-secret.sh${NC}"
    fi
fi

# Deploy with environment variables
DEPLOY_CMD="gcloud run deploy \"$SERVICE_NAME\" \
    --image \"$IMAGE_NAME:latest\" \
    --platform managed \
    --region \"$REGION\" \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars \"FLASK_ENV=production${ENV_VARS:+,$ENV_VARS}\""

# Add service account or secret if provided
if [ -n "$SERVICE_ACCOUNT_ARG" ]; then
    DEPLOY_CMD="$DEPLOY_CMD $SERVICE_ACCOUNT_ARG"
fi

if [ -n "$SECRET_ARG" ]; then
    DEPLOY_CMD="$DEPLOY_CMD $SECRET_ARG"
fi

DEPLOY_CMD="$DEPLOY_CMD --quiet"

eval $DEPLOY_CMD

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format='value(status.url)')

echo ""
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the service: curl $SERVICE_URL"
echo "2. Test the scheduled alert endpoint: curl $SERVICE_URL/api/trigger-scheduled-alert?model_id=model10"
echo "3. Set up Cloud Scheduler to call: $SERVICE_URL/api/trigger-scheduled-alert?model_id=model10"
echo "   Schedule: 0 9 * * 1 (Every Monday at 9am)"
echo ""
echo -e "${YELLOW}To set up Cloud Scheduler, run:${NC}"
echo "gcloud scheduler jobs create http monday-9am-alerts \\"
echo "  --location=$REGION \\"
echo "  --schedule='0 9 * * 1' \\"
echo "  --uri='$SERVICE_URL/api/trigger-scheduled-alert?model_id=model10' \\"
echo "  --http-method=GET \\"
echo "  --time-zone='America/New_York'"
echo ""
echo -e "${YELLOW}Service Account Setup (if not already done):${NC}"
echo "To create a service account with BigQuery access:"
echo "  gcloud iam service-accounts create quality-alerts-sa \\"
echo "    --display-name=\"Quality Alerts Service Account\""
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:quality-alerts-sa@$PROJECT_ID.iam.gserviceaccount.com\" \\"
echo "    --role=\"roles/bigquery.user\""
echo "  gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "    --member=\"serviceAccount:quality-alerts-sa@$PROJECT_ID.iam.gserviceaccount.com\" \\"
echo "    --role=\"roles/bigquery.dataViewer\""
echo ""
echo "Then redeploy with:"
echo "  ./deploy.sh $SERVICE_NAME $REGION $PROJECT_ID quality-alerts-sa@$PROJECT_ID.iam.gserviceaccount.com"

