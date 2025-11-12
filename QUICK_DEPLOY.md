# Quick Deployment Guide

## You Have a Service Account JSON File - Here's What to Do

### Option 1: Use Service Account Email (Recommended - No JSON Needed)

From your JSON file, the service account email is:
```
drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com
```

**You don't need to insert the JSON file anywhere!** Just use the email:

```bash
./deploy.sh quality-alerts us-central1 prod-tech-project1-bv479-zo027 drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com
```

Cloud Run will automatically use the service account's credentials - no JSON file needed in the deployment.

### Option 2: If You Must Use the JSON File

If you need to use the JSON file directly (not recommended for Cloud Run), you would need to:

1. **Store in Secret Manager** (requires permissions you may not have)
2. **Or use it locally** for development/testing only

## Where the JSON File Goes

| Location | Purpose | For Cloud Run? |
|----------|---------|----------------|
| **Nowhere in code** ✅ | Production deployment | ✅ Use service account email instead |
| Secret Manager | If you have permissions | ⚠️ Alternative option |
| Local machine | Development/testing | ❌ Not for production |
| Git repository | ❌ **NEVER** | ❌ Insecure |

## Your Current Setup

- ✅ JSON file: `drsanathservice-account-key.json`
- ✅ Service account email: `drsanath-service-account@prod-tech-project1-bv479-zo027.iam.gserviceaccount.com`
- ✅ Project: `prod-tech-project1-bv479-zo027`

**Just deploy with the email - no JSON insertion needed!**

