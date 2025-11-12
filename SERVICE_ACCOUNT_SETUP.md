# Service Account Setup for Cloud Run

## Quick Answer: Where to Put Service Account Details

**For Cloud Run, you DON'T need to put service account key files anywhere!** 

Instead, use the **Cloud Run Service Account** approach (recommended):

## Recommended Approach: Cloud Run Service Account

### Step 1: Create Service Account

```bash
# Replace PROJECT_ID with your actual project ID
PROJECT_ID="your-project-id"

# Create the service account
gcloud iam service-accounts create quality-alerts-sa \
  --display-name="Quality Alerts Service Account" \
  --project=$PROJECT_ID
```

### Step 2: Grant BigQuery Permissions

```bash
# Grant BigQuery User role (to run queries)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.user"

# Grant BigQuery Data Viewer role (to read data)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"
```

### Step 3: Deploy with Service Account

```bash
# Deploy using the deploy script
./deploy.sh quality-alerts us-central1 $PROJECT_ID quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com

# OR deploy manually
gcloud run deploy quality-alerts \
  --service-account=quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --region=us-central1 \
  # ... other flags
```

**That's it!** No key files needed. Cloud Run automatically uses the service account's credentials.

## Alternative: Using Service Account Key File

If you must use a key file (not recommended for Cloud Run):

### Step 1: Create and Download Key

```bash
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### Step 2: Store in Secret Manager

```bash
# Create secret
gcloud secrets create service-account-key \
  --data-file=service-account-key.json \
  --project=$PROJECT_ID

# Deploy with secret
gcloud run deploy quality-alerts \
  --update-secrets=GOOGLE_APPLICATION_CREDENTIALS=/tmp/sa-key.json=service-account-key:latest \
  --region=us-central1
```

### Step 3: Update Application (if needed)

The application will automatically use `GOOGLE_APPLICATION_CREDENTIALS` if set, otherwise it uses the Cloud Run service account.

## Summary

| Approach | Where to Put Details | Security | Ease of Use |
|----------|---------------------|----------|-------------|
| **Cloud Run Service Account** (Recommended) | Pass email to `--service-account` flag | ✅ Most Secure | ✅ Easiest |
| Secret Manager | Store key in Secret Manager, mount as secret | ✅ Secure | ⚠️ Moderate |
| Environment Variable | Set `GOOGLE_APPLICATION_CREDENTIALS` env var | ⚠️ Less Secure | ⚠️ Complex |

## Verification

After deployment, test BigQuery access:

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe quality-alerts --region=us-central1 --format='value(status.url)')

# Test the endpoint (this will trigger a BigQuery query)
curl ${SERVICE_URL}/api/trigger-scheduled-alert?model_id=model10
```

Check Cloud Run logs to verify BigQuery access:

```bash
gcloud run services logs read quality-alerts --region=us-central1 --limit=50
```

## Troubleshooting

### "Permission denied" errors

1. Verify service account has correct roles:
   ```bash
   gcloud projects get-iam-policy $PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com"
   ```

2. Ensure service account is attached to Cloud Run service:
   ```bash
   gcloud run services describe quality-alerts --region=us-central1 \
     --format="value(spec.template.spec.serviceAccountName)"
   ```

### "Service account not found"

- Verify the service account exists:
  ```bash
  gcloud iam service-accounts describe quality-alerts-sa@${PROJECT_ID}.iam.gserviceaccount.com
  ```

- Check the email format is correct (must include `@PROJECT_ID.iam.gserviceaccount.com`)

## Additional Resources

- [Cloud Run Service Accounts](https://cloud.google.com/run/docs/securing/service-identity)
- [BigQuery IAM Roles](https://cloud.google.com/bigquery/docs/access-control)
- Full deployment guide: See `CLOUD_RUN_DEPLOYMENT.md`

