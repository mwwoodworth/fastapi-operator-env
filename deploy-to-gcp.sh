#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="brainops-fastapi-ops"
REPOSITORY_NAME="brainops-backend"
IMAGE_NAME="fastapi-operator-env"

echo "Starting GCP deployment for $SERVICE_NAME..."

# 1. Authenticate with GCP
echo "Step 1: Authenticating with GCP..."
gcloud auth login
gcloud config set project $PROJECT_ID

# 2. Enable required APIs
echo "Step 2: Enabling required GCP APIs..."
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# 3. Create Artifact Registry repository if it doesn't exist
echo "Step 3: Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="BrainOps Backend Docker Images" || echo "Repository already exists"

# 4. Configure Docker for Artifact Registry
echo "Step 4: Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# 5. Build and tag the Docker image
echo "Step 5: Building Docker image..."
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest"
docker build -t $IMAGE_TAG -f Dockerfile.production .

# 6. Push image to Artifact Registry
echo "Step 6: Pushing image to Artifact Registry..."
docker push $IMAGE_TAG

# 7. Create service account if needed
echo "Step 7: Setting up service account..."
SERVICE_ACCOUNT="${SERVICE_NAME}-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create ${SERVICE_NAME}-sa \
    --display-name="BrainOps FastAPI Service Account" || echo "Service account already exists"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/cloudsql.client"

# 8. Deploy to Cloud Run
echo "Step 8: Deploying to Cloud Run..."

# Create .env.production from .env.master if it doesn't exist
if [ ! -f .env.production ]; then
    cp .env.master .env.production
    echo "Created .env.production from .env.master"
fi

# Deploy with environment variables
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_TAG \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars-from-file .env.production \
    --service-account $SERVICE_ACCOUNT \
    --port 8000 \
    --min-instances 1 \
    --max-instances 10 \
    --cpu 2 \
    --memory 2Gi \
    --timeout 300 \
    --concurrency 1000 \
    --set-cloudsql-instances="${CLOUD_SQL_CONNECTION_NAME}" \
    --update-labels="environment=production,app=brainops"

# 9. Get the service URL
echo "Step 9: Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
echo "Service deployed at: $SERVICE_URL"

# 10. Test the deployment
echo "Step 10: Testing deployment..."
curl -f "${SERVICE_URL}/healthz" && echo "Health check passed!" || echo "Health check failed!"

echo "Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "To view logs:"
echo "gcloud run logs read --service=$SERVICE_NAME --region=$REGION"
echo ""
echo "To update environment variables:"
echo "gcloud run services update $SERVICE_NAME --update-env-vars KEY=VALUE --region=$REGION"