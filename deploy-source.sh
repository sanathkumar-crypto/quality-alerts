#!/bin/bash
# Alternative deployment script using Cloud Run source-based deployment
# This builds directly from source code without needing Docker or Cloud Build permissions
# Usage: ./deploy-source.sh [SERVICE_NAME] [REGION] [PROJECT_ID] [SERVICE_ACCOUNT_EMAIL]

set -e

# Configuration
SERVICE_NAME="${1:-quality-alerts}"
REGION="${2:-us-central1}"
PROJECT_ID="${3:-$(gcloud config get-value project 2>/dev/null || echo '')}"
SERVICE_ACCOUNT="${4:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set.${NC}"
    echo "Usage: ./deploy-source.sh [SERVICE_NAME] [REGION] [PROJECT_ID] [SERVICE_ACCOUNT_EMAIL]"
    exit 1
fi

echo -e "${GREEN}Deploying to Cloud Run using source-based deployment...${NC}"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Project ID: $PROJECT_ID"
if [ -n "$SERVICE_ACCOUNT" ]; then
    echo "Service Account: $SERVICE_ACCOUNT"
fi
echo ""

# Set the project
gcloud config set project "$PROJECT_ID"

# Read environment variables from .env file if it exists
ENV_VARS=""
if [ -f .env ]; then
    echo -e "${GREEN}Reading environment variables from .env file...${NC}"
    while IFS='=' read -r key value || [ -n "$key" ]; do
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        if [ -n "$ENV_VARS" ]; then
            ENV_VARS="$ENV_VARS,"
        fi
        ENV_VARS="${ENV_VARS}${key}=${value}"
    done < .env
else
    echo -e "${YELLOW}Warning: .env file not found.${NC}"
fi

# Build deployment command
DEPLOY_CMD="gcloud run deploy \"$SERVICE_NAME\" \
    --source . \
    --platform managed \
    --region \"$REGION\" \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars \"FLASK_ENV=production${ENV_VARS:+,$ENV_VARS}\""

# Add service account if provided
if [ -n "$SERVICE_ACCOUNT" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --service-account=$SERVICE_ACCOUNT"
fi

echo -e "${YELLOW}Deploying from source (this will build the container automatically)...${NC}"
echo "This may take several minutes..."
echo ""

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
echo "3. Set up Cloud Scheduler (see CLOUD_RUN_DEPLOYMENT.md)"

