#!/bin/bash

# BrainOps AI Assistant - Production Deployment Script

set -e

echo "🚀 Starting BrainOps AI Assistant deployment..."

# Check if required environment variables are set
if [[ -z "$OPENAI_API_KEY" || -z "$ANTHROPIC_API_KEY" || -z "$ELEVENLABS_API_KEY" ]]; then
    echo "❌ Error: Required API keys not set. Please set:"
    echo "  - OPENAI_API_KEY"
    echo "  - ANTHROPIC_API_KEY"
    echo "  - ELEVENLABS_API_KEY"
    exit 1
fi

echo "✅ Environment variables validated"

# Build and start services
echo "🔧 Building and starting services..."
docker-compose down --volumes --remove-orphans
docker-compose build --no-cache
docker-compose up -d

echo "⏳ Waiting for services to become healthy..."

# Wait for backend to be ready
echo "🔄 Checking backend health..."
until curl -f http://localhost:8000/api/status > /dev/null 2>&1; do
    echo "⏳ Waiting for backend..."
    sleep 5
done
echo "✅ Backend is healthy"

# Wait for frontend to be ready
echo "🔄 Checking frontend health..."
until curl -f http://localhost:3000 > /dev/null 2>&1; do
    echo "⏳ Waiting for frontend..."
    sleep 5
done
echo "✅ Frontend is healthy"

# Check database migrations
echo "🔄 Running database migrations..."
docker-compose exec backend python -m alembic upgrade head

echo "🎉 Deployment completed successfully!"
echo ""
echo "📱 Services are now running:"
echo "  - Frontend: http://localhost:3000"
echo "  - Backend API: http://localhost:8000"
echo "  - API Documentation: http://localhost:8000/docs"
echo "  - Celery Flower: http://localhost:5555"
echo "  - Database: postgresql://brainops:brainops@localhost:5432/brainops"
echo "  - Redis: redis://localhost:6379"
echo ""
echo "🔍 To view logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "🛑 To stop services:"
echo "  docker-compose down"
echo ""
echo "🌟 BrainOps AI Assistant is now operational!"