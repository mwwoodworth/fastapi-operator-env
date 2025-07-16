#!/bin/bash
set -e

echo "Starting Vercel deployment for BrainOps AI Assistant Dashboard..."

# Check if we're in the right directory
if [ ! -d "~/brainops-deploy/brainops-ai-assistant-frontend" ]; then
    echo "Error: Frontend directory not found at ~/brainops-deploy/brainops-ai-assistant-frontend"
    echo "Please ensure the frontend repository is cloned to the correct location."
    exit 1
fi

cd ~/brainops-deploy/brainops-ai-assistant-frontend

# Install Vercel CLI if not present
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI..."
    npm install -g vercel
fi

# Create .env.local from .env.master
echo "Setting up environment variables..."
cat > .env.local << EOF
# Public Environment Variables (accessible in browser)
NEXT_PUBLIC_API_URL=https://brainops-fastapi-ops-<your-cloud-run-hash>.a.run.app
NEXT_PUBLIC_SUPABASE_URL=$SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=$NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
NEXT_PUBLIC_AI_COPILOT_ENABLED=TRUE
NEXT_PUBLIC_AR_MODE_ENABLED=TRUE
NEXT_PUBLIC_ESTIMATOR_ENABLED=TRUE
NEXT_PUBLIC_SALES_ENABLED=TRUE
NEXT_PUBLIC_MAINTENANCE_MODE=FALSE
NEXT_PUBLIC_BASE_URL=https://www.myroofgenius.com
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX
NEXT_PUBLIC_MAPBOX_TOKEN=$MAPBOX_TOKEN

# Server-side Environment Variables
SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET
OPENAI_API_KEY=$OPENAI_API_KEY
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
GEMINI_API_KEY=$GEMINI_API_KEY
SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
NOTION_TOKEN=$NOTION_TOKEN
CLICKUP_API_TOKEN=$CLICKUP_API_TOKEN
RESEND_API_KEY=$RESEND_API_KEY
SENTRY_DSN=$SENTRY_DSN
EOF

# Login to Vercel
echo "Logging in to Vercel..."
vercel login

# Link to Vercel project
echo "Linking to Vercel project..."
vercel link

# Deploy to production
echo "Deploying to production..."
vercel --prod

# Get deployment URL
DEPLOYMENT_URL=$(vercel ls --json | jq -r '.[0].url')
echo "Deployment complete!"
echo "Dashboard URL: https://$DEPLOYMENT_URL"

# Optional: Set up custom domain
read -p "Do you want to set up a custom domain? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your custom domain (e.g., dashboard.brainops.com): " CUSTOM_DOMAIN
    vercel domains add $CUSTOM_DOMAIN
    echo "Custom domain added. Please update your DNS records as instructed by Vercel."
fi

echo "Vercel deployment script completed!"