# BrainOps FastAPI Backend - Production Deployment Guide

## Overview

The BrainOps FastAPI backend is a production-ready AI automation platform with streaming capabilities, RAG system with pgvector, and comprehensive webhook integrations. This guide covers deployment, configuration, and operations.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Load Balancer │────▶│   FastAPI App   │────▶│   PostgreSQL    │
│     (Nginx)     │     │   (Uvicorn)     │     │   + pgvector    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Celery Worker  │────▶│      Redis      │
                        │  + Celery Beat  │     │                 │
                        └─────────────────┘     └─────────────────┘
```

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 15+ with pgvector extension
- Redis 7+
- Domain with SSL certificate
- API keys for integrations (Stripe, OpenAI, Anthropic, etc.)

## Environment Configuration

### 1. Create `.env` file

```bash
cp .env.example .env
```

### 2. Required Environment Variables

```env
# Application
ENVIRONMENT=production
DEBUG_MODE=false

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname
POSTGRES_PASSWORD=secure_password_here

# Redis
REDIS_URL=redis://redis:6379/0

# Security
JWT_SECRET=generate_with_openssl_rand_base64_32
JWT_ALGORITHM=HS256
FERNET_SECRET=generate_fernet_key_here

# AI Services
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_google_key

# Integrations
STRIPE_SECRET_KEY=your_stripe_secret
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
CLICKUP_API_TOKEN=your_clickup_token
NOTION_API_KEY=your_notion_key
GITHUB_SECRET=your_github_webhook_secret

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_key

# Other Services
VERCEL_TOKEN=your_vercel_token
TANA_API_KEY=your_tana_key
SLACK_WEBHOOK_URL=your_slack_webhook
```

### 3. Generate Secrets

```bash
# Generate JWT secret
openssl rand -base64 32

# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Deployment Options

### Option 1: Docker Compose (Recommended)

```bash
# Production deployment
docker-compose up -d

# With specific environment
docker-compose --env-file .env.production up -d

# Scale workers
docker-compose up -d --scale celery_worker=4
```

### Option 2: Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: brainops-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: brainops-api
  template:
    metadata:
      labels:
        app: brainops-api
    spec:
      containers:
      - name: api
        image: brainops/fastapi:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: brainops-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Option 3: Cloud Platforms

#### AWS ECS
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
docker build -t brainops-api .
docker tag brainops-api:latest $ECR_URI/brainops-api:latest
docker push $ECR_URI/brainops-api:latest
```

#### Google Cloud Run
```bash
# Deploy to Cloud Run
gcloud run deploy brainops-api \
  --image gcr.io/project-id/brainops-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Database Setup

### 1. Initialize Database

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Or directly
alembic upgrade head
```

### 2. Create Initial Admin User

```python
# scripts/create_admin.py
from db.session import SessionLocal
from db.models import User
from core.security import get_password_hash

db = SessionLocal()
admin = User(
    username="admin",
    email="admin@brainops.com",
    hashed_password=get_password_hash("secure_password"),
    is_active=True,
    is_superuser=True,
    roles=["admin"]
)
db.add(admin)
db.commit()
```

### 3. Enable pgvector

```sql
-- Already handled by migration, but if needed:
CREATE EXTENSION IF NOT EXISTS vector;
```

## Monitoring & Observability

### 1. Health Checks

```bash
# API health
curl https://api.brainops.com/health

# Metrics endpoint
curl https://api.brainops.com/metrics
```

### 2. Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'brainops-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
```

### 3. Logging

- Application logs: `/app/logs/app.log`
- Error logs: `/app/logs/error.log`
- Access logs: `/app/logs/access.log`

### 4. Celery Monitoring

Access Flower dashboard at `http://localhost:5555`

## SSL/TLS Configuration

### Using Certbot

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d api.brainops.com
```

### Nginx Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.brainops.com;

    ssl_certificate /etc/letsencrypt/live/api.brainops.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.brainops.com/privkey.pem;

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Backup & Recovery

### 1. Database Backup

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec postgres pg_dump -U brainops brainops_db | gzip > backup_$DATE.sql.gz

# Upload to S3
aws s3 cp backup_$DATE.sql.gz s3://brainops-backups/
```

### 2. Restore Database

```bash
# Restore from backup
gunzip < backup_20240115_120000.sql.gz | docker-compose exec -T postgres psql -U brainops brainops_db
```

## Performance Tuning

### 1. PostgreSQL Optimization

```sql
-- postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

### 2. Uvicorn Workers

```bash
# Adjust based on CPU cores
uvicorn main:app --workers 4
```

### 3. Connection Pooling

```python
# db/session.py
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Security Checklist

- [ ] All secrets in environment variables
- [ ] JWT tokens configured with secure secret
- [ ] HTTPS enabled with valid certificate
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] SQL injection protection (using SQLAlchemy)
- [ ] Webhook signature verification enabled
- [ ] Regular security updates applied
- [ ] API keys rotated regularly

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check PostgreSQL status
   docker-compose logs postgres
   
   # Verify connection string
   docker-compose exec api python -c "from db.session import engine; print(engine.url)"
   ```

2. **Celery Tasks Not Processing**
   ```bash
   # Check worker status
   docker-compose logs celery_worker
   
   # Monitor queue
   docker-compose exec redis redis-cli LLEN celery
   ```

3. **Memory Issues**
   ```bash
   # Monitor memory usage
   docker stats
   
   # Adjust worker concurrency
   celery -A celery_app worker --concurrency=2
   ```

## Scaling

### Horizontal Scaling

```bash
# Scale API instances
docker-compose up -d --scale api=3

# Scale Celery workers
docker-compose up -d --scale celery_worker=4
```

### Database Scaling

- Use read replicas for search queries
- Implement connection pooling
- Consider partitioning large tables

## Maintenance

### Regular Tasks

1. **Daily**
   - Monitor error logs
   - Check API response times
   - Review failed Celery tasks

2. **Weekly**
   - Rotate logs
   - Update dependencies
   - Review security alerts

3. **Monthly**
   - Performance analysis
   - Database optimization
   - Security audit

### Update Procedure

```bash
# 1. Backup database
./scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Build new image
docker-compose build

# 4. Run migrations
docker-compose exec api alembic upgrade head

# 5. Restart services
docker-compose down && docker-compose up -d
```

## API Documentation

Access interactive API documentation at:
- Swagger UI: `https://api.brainops.com/docs`
- ReDoc: `https://api.brainops.com/redoc`

## Support

For production support:
- Email: support@brainops.com
- Slack: #brainops-api
- Documentation: https://docs.brainops.com

---

**Last Updated**: January 2025
**Version**: 2.0.0