# FastAPI Backend Troubleshooting Guide

## Common Issues and Solutions

### 1. CORS Errors

**Problem**: Frontend receives CORS errors when calling the API

**Solutions**:
```python
# Check CORS configuration in apps/backend/main.py
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")

# For Cloud Run, update environment variable
gcloud run services update fastapi-backend \
  --update-env-vars CORS_ORIGINS="https://app.brainops.com,https://localhost:3000" \
  --region=us-central1

# For local development, update .env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**Debug CORS**:
```bash
# Test CORS headers
curl -H "Origin: https://app.brainops.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: X-Requested-With" \
  -X OPTIONS \
  https://your-service-url.run.app/api/v1/health
```

### 2. Database Connection Issues

**Problem**: Cannot connect to database

**Local Development**:
```bash
# Check if postgres is running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U postgres -d brainops

# Common connection string issues
# Wrong: postgresql://user:pass@localhost:5432/db
# Right: postgresql+asyncpg://user:pass@localhost:5432/db
```

**Production (Cloud SQL)**:
```bash
# Check Cloud SQL instance status
gcloud sql instances describe brainops-postgres

# Test connection via Cloud SQL Proxy
cloud_sql_proxy -instances=PROJECT_ID:REGION:brainops-postgres=tcp:5432

# Verify connection string format
# Format: postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE
```

### 3. Secret Manager Access Issues

**Problem**: "Permission denied" accessing secrets

**Solution**:
```bash
# Grant secret accessor role to service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:fastapi-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Verify secret exists
gcloud secrets list

# Test secret access
gcloud secrets versions access latest --secret="database-url"
```

### 4. Health Check Failures

**Problem**: Cloud Run reports unhealthy service

**Debug Steps**:
```bash
# Check service logs
gcloud run services logs read fastapi-backend --limit=100 --region=us-central1

# Test health endpoint locally
curl http://localhost:8000/health

# Test detailed health
curl http://localhost:8000/health/detailed

# Common causes:
# - Database not reachable
# - Missing environment variables
# - Port mismatch (should be 8000)
```

### 5. Memory/CPU Issues

**Problem**: Service crashes or timeouts

**Monitor Resources**:
```bash
# View Cloud Run metrics
gcloud run services describe fastapi-backend --region=us-central1

# Update resources
gcloud run services update fastapi-backend \
  --cpu 4 \
  --memory 4Gi \
  --region=us-central1
```

**Optimize Gunicorn Workers**:
```bash
# Update worker configuration
gcloud run services update fastapi-backend \
  --update-env-vars WORKERS_PER_CORE=1 \
  --update-env-vars MAX_WORKERS=2 \
  --region=us-central1
```

### 6. Deployment Failures

**GitHub Actions Issues**:
```bash
# Check workflow logs in GitHub Actions tab

# Common issues:
# 1. Invalid service account key
# 2. Missing permissions
# 3. Docker build failures

# Validate service account locally
gcloud auth activate-service-account --key-file=github-actions-key.json
gcloud auth list
```

**Manual Deployment Issues**:
```bash
# Enable verbose logging
gcloud run deploy fastapi-backend \
  --image IMAGE_URL \
  --region=us-central1 \
  --verbosity=debug

# Check artifact registry
gcloud artifacts docker images list \
  --repository=brainops \
  --location=us-central1
```

### 7. Async Task Issues

**Problem**: Background tasks not running

**Debug Celery/Redis**:
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Monitor Celery workers
docker-compose logs celery-worker

# Test Redis connection
python -c "import redis; r = redis.from_url('redis://localhost:6379'); print(r.ping())"
```

### 8. API Performance Issues

**Problem**: Slow API responses

**Profiling**:
```python
# Add timing middleware (temporary)
import time
from fastapi import Request

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

**Database Query Optimization**:
```bash
# Enable SQL logging
LOG_LEVEL=DEBUG

# Check for N+1 queries
# Use SQLAlchemy eager loading
```

### 9. Static File Serving

**Problem**: Static files not accessible

**Solution**:
```python
# Add static file mounting in main.py
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

**Nginx Alternative** (for better performance):
```dockerfile
# Add nginx stage to Dockerfile
FROM nginx:alpine as static
COPY --from=builder /app/static /usr/share/nginx/html
```

### 10. Environment Variable Issues

**Problem**: Missing or incorrect environment variables

**Debug**:
```bash
# List all environment variables in Cloud Run
gcloud run services describe fastapi-backend \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env[].name)"

# Check specific variable
gcloud run services describe fastapi-backend \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env[?name=='DATABASE_URL'])"

# Update environment variable
gcloud run services update fastapi-backend \
  --update-env-vars KEY=VALUE \
  --region=us-central1
```

## Logging and Monitoring

### Enable Structured Logging

```python
# Already configured in apps/backend/core/logging_config.py
import structlog

logger = structlog.get_logger()
logger.info("api_request", method="GET", path="/health", status=200)
```

### View Logs

```bash
# Stream logs
gcloud run services logs tail fastapi-backend --region=us-central1

# Filter logs
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=fastapi-backend \
  AND severity>=ERROR" \
  --limit=50 \
  --format=json

# Export logs
gcloud logging read "resource.type=cloud_run_revision" \
  --format=json > logs.json
```

### Sentry Integration

```python
# Check Sentry configuration
import sentry_sdk
print(sentry_sdk.Hub.current.client.dsn)

# Test Sentry
sentry_sdk.capture_message("Test message")
```

## Emergency Procedures

### 1. Rollback Deployment

```bash
# List recent revisions
gcloud run revisions list --service=fastapi-backend --region=us-central1

# Rollback to previous revision
gcloud run services update-traffic fastapi-backend \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=us-central1
```

### 2. Emergency Scaling

```bash
# Scale up immediately
gcloud run services update fastapi-backend \
  --min-instances=5 \
  --max-instances=1000 \
  --region=us-central1

# Scale down after incident
gcloud run services update fastapi-backend \
  --min-instances=1 \
  --max-instances=100 \
  --region=us-central1
```

### 3. Circuit Breaker

```python
# Implement in critical endpoints
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def call_external_service():
    # External API call
    pass
```

## Performance Optimization Tips

1. **Connection Pooling**:
```python
# Configure in apps/backend/db/session.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

2. **Response Caching**:
```python
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache

@app.get("/api/v1/products")
@cache(expire=300)  # Cache for 5 minutes
async def get_products():
    return await fetch_products()
```

3. **Async Best Practices**:
```python
# Good - concurrent execution
results = await asyncio.gather(
    fetch_user(user_id),
    fetch_orders(user_id),
    fetch_preferences(user_id)
)

# Bad - sequential execution
user = await fetch_user(user_id)
orders = await fetch_orders(user_id)
preferences = await fetch_preferences(user_id)
```

## Getting Help

- **Cloud Run Issues**: https://cloud.google.com/run/docs/troubleshooting
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **GitHub Issues**: Create issue in repository
- **Logs**: Always check logs first before debugging