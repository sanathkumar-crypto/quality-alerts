#!/bin/bash
# Script to set up service account key in Secret Manager for Cloud Run
# Usage: ./setup-service-account-secret.sh [PATH_TO_KEY_FILE] [PROJECT_ID] [SECRET_NAME]

set -e

# Configuration
KEY_FILE="${1:-service-account-key.json}"
PROJECT_ID="${2:-$(gcloud config get-value project 2>/dev/null || echo '')}"
SECRET_NAME="${3:-service-account-key}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo -e "${RED}Error: Service account key file not found: $KEY_FILE${NC}"
    echo "Usage: ./setup-service-account-secret.sh [PATH_TO_KEY_FILE] [PROJECT_ID] [SECRET_NAME]"
    echo ""
    echo "Example:"
    echo "  ./setup-service-account-secret.sh ~/Downloads/my-service-account.json my-project"
    exit 1
fi

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set. Please provide it as second argument or set default gcloud project.${NC}"
    echo "Usage: ./setup-service-account-secret.sh [PATH_TO_KEY_FILE] [PROJECT_ID] [SECRET_NAME]"
    exit 1
fi

echo -e "${GREEN}Setting up service account key in Secret Manager...${NC}"
echo "Key file: $KEY_FILE"
echo "Project ID: $PROJECT_ID"
echo "Secret name: $SECRET_NAME"
echo ""

# Set the project
gcloud config set project "$PROJECT_ID"

# Enable Secret Manager API if not already enabled
echo -e "${YELLOW}Enabling Secret Manager API...${NC}"
gcloud services enable secretmanager.googleapis.com --quiet

# Check if secret already exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${YELLOW}Secret '$SECRET_NAME' already exists. Updating with new version...${NC}"
    # Add new version to existing secret
    gcloud secrets versions add "$SECRET_NAME" \
        --data-file="$KEY_FILE" \
        --project="$PROJECT_ID"
    echo -e "${GREEN}✅ Secret updated successfully!${NC}"
else
    echo -e "${YELLOW}Creating new secret '$SECRET_NAME'...${NC}"
    # Create new secret
    gcloud secrets create "$SECRET_NAME" \
        --data-file="$KEY_FILE" \
        --project="$PROJECT_ID" \
        --replication-policy="automatic"
    echo -e "${GREEN}✅ Secret created successfully!${NC}"
fi

# Grant Cloud Run service account access to the secret
echo -e "${YELLOW}Granting Cloud Run access to the secret...${NC}"

# Get the default Compute Engine service account
COMPUTE_SA="${PROJECT_ID}@appspot.gserviceaccount.com"

# Grant secret accessor role
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID"

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Deploy your Cloud Run service with the secret mounted:"
echo ""
echo "   gcloud run deploy quality-alerts \\"
echo "     --image=IMAGE_URL \\"
echo "     --region=us-central1 \\"
echo "     --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json=${SECRET_NAME}:latest \\"
echo "     --set-env-vars=\"FLASK_ENV=production\" \\"
echo "     # ... other flags"
echo ""
echo "2. Or use the deploy script with secret:"
echo "   ./deploy-with-secret.sh quality-alerts us-central1 $PROJECT_ID $SECRET_NAME"
echo ""
echo -e "${YELLOW}Note:${NC} The secret is now stored securely in Secret Manager."
echo "You can safely delete the local key file if you want (but keep a backup!)."

