# Alternative Deployment Methods

Since Cloud Build requires special permissions, here are alternative ways to deploy:

## Method 1: Source-Based Deployment (Recommended)

Cloud Run can build directly from your source code without needing Cloud Build permissions:

```bash
./deploy-source.sh quality-alerts us-central1 prod-tech-project1-bv479-zo027 drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com
```

**Advantages:**
- ✅ No Cloud Build permissions needed
- ✅ No Docker required locally
- ✅ Cloud Run handles the build automatically
- ✅ Works with your current setup

**How it works:**
- Cloud Run uses Cloud Build internally (but you don't need direct access)
- Builds from your source code automatically
- Deploys the container when done

## Method 2: Use GitHub with Cloud Build Triggers

If your code is in GitHub (which it is), you can set up Cloud Build to trigger from GitHub:

1. **Connect GitHub repository:**
   - Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers)
   - Click "Connect Repository"
   - Select GitHub and authorize
   - Choose your repository: `sanathkumar-crypto/quality-alerts`

2. **Create a trigger:**
   - Click "Create Trigger"
   - Source: Your GitHub repo
   - Configuration: Cloud Build configuration file
   - Location: `cloudbuild.yaml`
   - Substitution variables:
     - `_SERVICE_NAME`: `quality-alerts`
     - `_REGION`: `us-central1`
     - `_REPO_NAME`: `quality-alerts`

3. **Push to trigger deployment:**
   ```bash
   git push origin main
   ```

**Advantages:**
- ✅ Automatic deployments on git push
- ✅ No local Docker needed
- ✅ Uses Cloud Build with proper permissions

## Method 3: Build Docker Image Elsewhere

If you have access to another machine/environment with Docker and network access:

1. **Build on that machine:**
   ```bash
   docker build -t gcr.io/prod-tech-project1-bv479-zo027/quality-alerts:latest .
   docker push gcr.io/prod-tech-project1-bv479-zo027/quality-alerts:latest
   ```

2. **Deploy from here:**
   ```bash
   # Just deploy the already-built image
   gcloud run deploy quality-alerts \
     --image=gcr.io/prod-tech-project1-bv479-zo027/quality-alerts:latest \
     --region=us-central1 \
     --service-account=drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com \
     --set-env-vars="FLASK_ENV=production" \
     # ... other flags
   ```

## Method 4: Use Cloud Shell

Google Cloud Shell has Docker and network access pre-configured:

1. **Open Cloud Shell:**
   - Go to [Cloud Shell](https://shell.cloud.google.com/)
   - Or run: `gcloud cloud-shell ssh`

2. **Clone and deploy:**
   ```bash
   git clone https://github.com/sanathkumar-crypto/quality-alerts.git
   cd quality-alerts
   ./deploy.sh quality-alerts us-central1 prod-tech-project1-bv479-zo027 drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com
   ```

## Recommended: Try Method 1 First

The source-based deployment (`deploy-source.sh`) is the easiest and should work with your current permissions:

```bash
./deploy-source.sh quality-alerts us-central1 prod-tech-project1-bv479-zo027 drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com
```

This will:
1. Upload your source code to Cloud Run
2. Cloud Run builds the container automatically (using Cloud Build internally)
3. Deploys the service
4. Sets environment variables from your `.env` file
5. Configures the service account

**Note:** The first deployment may take 5-10 minutes as it builds the container.

