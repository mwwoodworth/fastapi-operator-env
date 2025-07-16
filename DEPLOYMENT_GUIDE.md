# BrainOps FastAPI Operator Environment - Deployment Guide

This guide provides comprehensive instructions for deploying the BrainOps FastAPI backend to Google Cloud Run and the frontend dashboard to Vercel.

## 📋 Prerequisites

1. **Tools Required:**
   - Docker
   - Google Cloud SDK (`gcloud`)
   - Node.js and npm
   - Git
   - Make (optional)

2. **Accounts Required:**
   - Google Cloud Platform account with billing enabled
   - Vercel account
   - GitHub account with repository access

3. **API Keys Required:**
   - All keys listed in `.env.master`
   - Google Cloud service account key
   - GitHub Personal Access Token

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/mwwoodworth/fastapi-operator-env.git
cd fastapi-operator-env

# 2. Copy and configure environment variables
cp .env.master .env.production
# Edit .env.production with your actual values

# 3. Deploy to Google Cloud Run
./deploy-to-gcp.sh

# 4. Deploy frontend to Vercel
./deploy-vercel-frontend.sh

# 5. Test the deployment
./test-deployment.sh https://your-cloud-run-url.a.run.app
```

## 📦 Docker Setup

### Local Development

```bash
# Build and run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run database migrations
docker-compose run backend alembic upgrade head

# Stop services
docker-compose down
```

### Production Build

```bash
# Build production image
docker build -t brainops-fastapi:latest -f Dockerfile.production .

# Run production container
docker run -p 8000:8000 --env-file .env.production brainops-fastapi:latest
```

## ☁️ Google Cloud Deployment

### Initial Setup

1. **Create GCP Project:**
```bash
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID
```

2. **Enable Required APIs:**
```bash
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

3. **Create Service Account:**
```bash
gcloud iam service-accounts create brainops-sa \
    --display-name="BrainOps Service Account"
```

### Deploy with Script

```bash
# Set environment variables
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1

# Run deployment
./deploy-to-gcp.sh
```

### Manual Deployment

```bash
# 1. Build and push image
docker build -t gcr.io/$PROJECT_ID/brainops-fastapi:latest -f Dockerfile.production .
docker push gcr.io/$PROJECT_ID/brainops-fastapi:latest

# 2. Deploy to Cloud Run
gcloud run deploy brainops-fastapi-ops \
    --image gcr.io/$PROJECT_ID/brainops-fastapi:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars-from-file .env.production
```

## 🌐 Vercel Frontend Deployment

1. **Install Vercel CLI:**
```bash
npm i -g vercel
```

2. **Deploy Frontend:**
```bash
cd ~/brainops-deploy/brainops-ai-assistant-frontend
vercel --prod
```

3. **Set Environment Variables:**
   - Go to Vercel Dashboard
   - Navigate to Project Settings > Environment Variables
   - Add all `NEXT_PUBLIC_*` variables from `.env.master`

## 🔐 Secrets Management

### Google Secret Manager

```bash
# Create secrets
echo -n "your-secret-value" | gcloud secrets create secret-name --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding secret-name \
    --member="serviceAccount:brainops-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### GitHub Secrets

Add these secrets to your GitHub repository:
- `GCP_PROJECT_ID`
- `GCP_SA_KEY` (service account JSON)
- All API keys from `.env.master`

## 🔄 CI/CD Pipeline

### GitHub Actions

The repository includes workflows for:
- **Deploy on Push:** Automatically deploys to Cloud Run on push to main
- **PR Checks:** Runs tests and linting on pull requests

### Manual Trigger

```bash
# Trigger deployment manually
gh workflow run deploy.yml
```

## 🧪 Testing

### Health Checks

```bash
# Test local deployment
curl http://localhost:8000/healthz

# Test production deployment
curl https://your-service.a.run.app/healthz
```

### Run Full Test Suite

```bash
./test-deployment.sh https://your-service.a.run.app
```

## 📊 Monitoring

### Cloud Run Logs

```bash
# View logs
gcloud run logs read --service=brainops-fastapi-ops --region=us-central1

# Stream logs
gcloud run logs tail --service=brainops-fastapi-ops --region=us-central1
```

### Metrics

- Cloud Run Console: Monitor CPU, memory, request count
- Sentry: Error tracking and performance monitoring
- Custom metrics: Available at `/metrics` endpoint

## 🔧 Troubleshooting

### Common Issues

1. **Build Failures:**
   - Check Dockerfile syntax
   - Verify all dependencies in requirements.txt
   - Ensure base image is accessible

2. **Deployment Failures:**
   - Verify GCP credentials
   - Check service account permissions
   - Validate environment variables

3. **Runtime Errors:**
   - Check Cloud Run logs
   - Verify database connectivity
   - Confirm all required secrets are set

### Debug Commands

```bash
# Check service status
gcloud run services describe brainops-fastapi-ops --region=us-central1

# List recent revisions
gcloud run revisions list --service=brainops-fastapi-ops --region=us-central1

# Rollback to previous revision
gcloud run services update-traffic brainops-fastapi-ops \
    --to-revisions=REVISION_NAME=100 --region=us-central1
```

## 🔄 Updates and Maintenance

### Update Dependencies

```bash
# Update Python packages
pip-compile requirements.in --upgrade

# Update Docker base image
docker pull python:3.11-slim
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Rolling Updates

Cloud Run automatically performs rolling updates. To control traffic:

```bash
# Gradual rollout
gcloud run services update-traffic brainops-fastapi-ops \
    --to-latest=50 --region=us-central1
```

## 📝 Environment Variables Reference

See `.env.master` for a complete list of environment variables. Key variables:

- `ENV`: Environment (development/production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key
- `STRIPE_SECRET_KEY`: Stripe secret key
- See `.env.master` for complete list

## 🔗 Useful Links

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Vercel Documentation](https://vercel.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Docker Documentation](https://docs.docker.com)

## 📞 Support

For issues or questions:
- Create an issue in the GitHub repository
- Contact the BrainOps team
- Check the troubleshooting section above