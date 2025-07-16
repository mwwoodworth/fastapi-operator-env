# FastAPI Backend Deployment Guide

## Prerequisites

- Google Cloud SDK (`gcloud`) installed
- Docker installed
- GitHub repository access
- GCP Project with billing enabled

## Initial Setup

### 1. Google Cloud Project Setup

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Set default project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable compute.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create brainops \
    --repository-format=docker \
    --location=$REGION \
    --description="BrainOps container images"

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### 2. Service Account Setup

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create fastapi-backend \
    --display-name="FastAPI Backend Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Create service account for GitHub Actions
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions Deploy"

# Grant permissions to GitHub Actions service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-actions@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"

# Create and download service account key for GitHub Actions
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@${PROJECT_ID}.iam.gserviceaccount.com
```

### 3. Secret Manager Setup

```bash
# Create secrets in Secret Manager
echo -n "postgresql+asyncpg://user:pass@host:5432/dbname" | \
    gcloud secrets create database-url --data-file=-

echo -n "redis://redis-host:6379" | \
    gcloud secrets create redis-url --data-file=-

echo -n "your-openai-key" | \
    gcloud secrets create openai-api-key --data-file=-

echo -n "your-anthropic-key" | \
    gcloud secrets create anthropic-api-key --data-file=-

echo -n "your-google-ai-key" | \
    gcloud secrets create google-ai-api-key --data-file=-

echo -n "your-stripe-key" | \
    gcloud secrets create stripe-api-key --data-file=-

echo -n "your-stripe-webhook-secret" | \
    gcloud secrets create stripe-webhook-secret --data-file=-

echo -n "your-slack-token" | \
    gcloud secrets create slack-bot-token --data-file=-

echo -n "your-notion-key" | \
    gcloud secrets create notion-api-key --data-file=-

echo -n "your-clickup-key" | \
    gcloud secrets create clickup-api-key --data-file=-

echo -n "your-supabase-url" | \
    gcloud secrets create supabase-url --data-file=-

echo -n "your-supabase-key" | \
    gcloud secrets create supabase-key --data-file=-

echo -n "your-sentry-dsn" | \
    gcloud secrets create sentry-dsn --data-file=-
```

### 4. GitHub Repository Setup

1. Go to your GitHub repository settings
2. Navigate to Secrets and variables > Actions
3. Add the following secrets:
   - `GCP_PROJECT_ID`: Your Google Cloud Project ID
   - `GCP_SA_KEY`: Contents of `github-actions-key.json`
   - `SLACK_WEBHOOK_URL`: (Optional) Slack webhook for notifications

## Local Development

### Using Docker Compose

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your local values
nano .env

# Start all services
docker-compose up -d

# Run database migrations
docker-compose --profile migrate up migrate

# View logs
docker-compose logs -f backend

# Stop all services
docker-compose down

# With volumes cleanup
docker-compose down -v
```

### Direct Docker Commands

```bash
# Build the image
docker build -f Dockerfile.production -t fastapi-backend:latest .

# Run locally
docker run -p 8000:8000 --env-file .env fastapi-backend:latest

# Run with custom environment
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://localhost:5432/mydb" \
  -e REDIS_URL="redis://localhost:6379" \
  fastapi-backend:latest
```

## Production Deployment

### Manual Deployment

```bash
# Build and tag image
docker build -f Dockerfile.production -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/brainops/fastapi-backend:latest .

# Push to Artifact Registry
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/brainops/fastapi-backend:latest

# Deploy to Cloud Run (using cloudrun.yaml)
gcloud run services replace cloudrun.yaml --region=$REGION

# Or deploy with CLI
gcloud run deploy fastapi-backend \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/brainops/fastapi-backend:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 100 \
  --cpu 2 \
  --memory 2Gi \
  --service-account fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com
```

### Automated Deployment

Push to the `main` branch will automatically trigger the GitHub Actions workflow.

```bash
git add .
git commit -m "Deploy to production"
git push origin main
```

## Monitoring & Management

### View Service Status

```bash
# List all Cloud Run services
gcloud run services list --region=$REGION

# Describe specific service
gcloud run services describe fastapi-backend --region=$REGION

# View service logs
gcloud run services logs read fastapi-backend --region=$REGION --limit=50

# Stream logs
gcloud alpha run services logs tail fastapi-backend --region=$REGION
```

### Update Service

```bash
# Update environment variable
gcloud run services update fastapi-backend \
  --update-env-vars LOG_LEVEL=DEBUG \
  --region=$REGION

# Update resource allocation
gcloud run services update fastapi-backend \
  --cpu 4 \
  --memory 4Gi \
  --region=$REGION

# Update scaling
gcloud run services update fastapi-backend \
  --min-instances 2 \
  --max-instances 200 \
  --region=$REGION
```

### Rollback Deployment

```bash
# List revisions
gcloud run revisions list --service fastapi-backend --region=$REGION

# Route traffic to specific revision
gcloud run services update-traffic fastapi-backend \
  --to-revisions=fastapi-backend-00002-abc=100 \
  --region=$REGION
```

## Database Management

### Cloud SQL Setup (Production)

```bash
# Create Cloud SQL instance
gcloud sql instances create brainops-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region=$REGION \
  --network=default

# Create database
gcloud sql databases create brainops \
  --instance=brainops-postgres

# Create user
gcloud sql users create appuser \
  --instance=brainops-postgres \
  --password=secure-password

# Get connection name
gcloud sql instances describe brainops-postgres --format="value(connectionName)"

# Update DATABASE_URL secret with Cloud SQL connection
echo -n "postgresql+asyncpg://appuser:secure-password@/brainops?host=/cloudsql/PROJECT_ID:REGION:brainops-postgres" | \
  gcloud secrets versions add database-url --data-file=-
```

### Run Migrations

```bash
# Local migrations
docker-compose --profile migrate up migrate

# Production migrations (via Cloud Run Job)
gcloud run jobs create migrate-db \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/brainops/fastapi-backend:latest \
  --region $REGION \
  --command alembic \
  --args upgrade,head \
  --set-secrets DATABASE_URL=database-url:latest \
  --service-account fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com

# Execute migration job
gcloud run jobs execute migrate-db --region=$REGION
```

## Custom Domain Setup

```bash
# Add custom domain mapping
gcloud run domain-mappings create \
  --service fastapi-backend \
  --domain api.brainops.com \
  --region=$REGION

# Verify domain (follow instructions)
gcloud run domain-mappings describe \
  --domain api.brainops.com \
  --region=$REGION
```

## Cost Optimization

```bash
# Set concurrency for better resource utilization
gcloud run services update fastapi-backend \
  --concurrency 1000 \
  --region=$REGION

# Enable CPU allocation only during requests
gcloud run services update fastapi-backend \
  --cpu-throttling \
  --region=$REGION

# Set appropriate timeouts
gcloud run services update fastapi-backend \
  --timeout 60 \
  --region=$REGION
```