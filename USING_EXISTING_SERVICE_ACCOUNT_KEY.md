# Using Your Existing Service Account JSON Key File

If you already have a service account JSON key file, here's how to use it with Cloud Run:

## Step 1: Upload Key to Secret Manager

**DO NOT put the JSON file in your codebase!** Instead, store it securely in Google Cloud Secret Manager.

Run the setup script:

```bash
./setup-service-account-secret.sh [PATH_TO_YOUR_KEY_FILE] [PROJECT_ID] [SECRET_NAME]
```

**Example:**
```bash
# If your key file is in Downloads folder
./setup-service-account-secret.sh ~/Downloads/my-service-account.json my-project-id service-account-key

# Or if it's in the current directory
./setup-service-account-secret.sh ./service-account-key.json my-project-id
```

This script will:
- ✅ Upload your key to Secret Manager
- ✅ Grant Cloud Run access to read the secret
- ✅ Keep your key secure (not in code)

## Step 2: Deploy with the Secret

After uploading, deploy your service using the secret name:

```bash
./deploy.sh quality-alerts us-central1 my-project-id service-account-key
```

The deploy script will automatically:
- Mount the secret as `/tmp/sa-key.json` in the container
- Set `GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json` environment variable
- Your app will automatically use this for BigQuery authentication

## Alternative: Manual Deployment

If you prefer to deploy manually:

```bash
# Build and push image first (see deploy.sh for details)
# Then deploy with secret:

gcloud run deploy quality-alerts \
  --image=YOUR_IMAGE_URL \
  --region=us-central1 \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json=service-account-key:latest \
  --set-env-vars="FLASK_ENV=production" \
  # ... other flags
```

## Where the Key File Goes

| Location | Purpose | Security |
|----------|---------|----------|
| **Secret Manager** ✅ | Production use | ✅ Secure |
| Your local machine | Upload to Secret Manager | ⚠️ Keep private |
| Git repository | ❌ **NEVER** | ❌ Insecure |
| Docker image | ❌ **NEVER** | ❌ Insecure |

## Verify It's Working

After deployment, test BigQuery access:

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe quality-alerts --region=us-central1 --format='value(status.url)')

# Test the endpoint (this queries BigQuery)
curl ${SERVICE_URL}/api/trigger-scheduled-alert?model_id=model10
```

Check logs to verify:
```bash
gcloud run services logs read quality-alerts --region=us-central1 --limit=50
```

You should see successful BigQuery queries, not authentication errors.

## Security Best Practices

1. ✅ **Upload to Secret Manager** - Never commit keys to git
2. ✅ **Use .gitignore** - Ensure `.gitignore` includes `*.json` files
3. ✅ **Rotate keys regularly** - Update secrets in Secret Manager periodically
4. ✅ **Limit access** - Only grant secret access to necessary services
5. ✅ **Delete local copies** - After uploading, securely delete local key files (or keep encrypted backups)

## Troubleshooting

### "Secret not found" error
- Verify the secret exists: `gcloud secrets list`
- Check the secret name matches what you used in deploy

### "Permission denied" accessing secret
- Ensure Cloud Run service account has `secretmanager.secretAccessor` role
- The setup script should handle this automatically

### BigQuery authentication errors
- Verify the key file has correct BigQuery permissions
- Check the service account has `roles/bigquery.user` and `roles/bigquery.dataViewer`

## Quick Reference

```bash
# 1. Upload key
./setup-service-account-secret.sh /path/to/key.json PROJECT_ID

# 2. Deploy with secret
./deploy.sh quality-alerts us-central1 PROJECT_ID service-account-key

# 3. Test
curl $(gcloud run services describe quality-alerts --region=us-central1 --format='value(status.url)')/api/trigger-scheduled-alert?model_id=model10
```

That's it! Your service account key is now securely stored and used by Cloud Run.

