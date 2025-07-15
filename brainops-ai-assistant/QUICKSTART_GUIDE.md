# BrainOps AI Assistant - Quickstart Guide

## 🚀 Quick Start - Get Running in 5 Minutes

This guide will get your BrainOps AI Assistant up and running in production in under 5 minutes.

---

## 📋 Prerequisites

- **Python 3.8+** installed
- **PostgreSQL 12+** with pgvector extension
- **Redis** server running
- **Git** for version control
- **Docker** (optional, for containerized deployment)

---

## ⚡ Lightning Fast Setup

### Step 1: Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/brainops/ai-assistant.git
cd ai-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### Step 2: Environment Configuration

Create `.env` file in the backend directory:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost/brainops_ai
REDIS_URL=redis://localhost:6379

# API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Security
SECRET_KEY=your_super_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
MAX_UPLOAD_SIZE=50MB
```

### Step 3: Database Setup

```bash
# Create database
createdb brainops_ai

# Install pgvector extension
psql -d brainops_ai -c "CREATE EXTENSION vector;"

# Initialize database
cd backend
python -c "
import asyncio
from core.database import init_db
asyncio.run(init_db())
"
```

### Step 4: Launch Backend

```bash
# Start the backend server
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Launch Frontend

```bash
# In a new terminal
cd frontend
npm install
npm run dev
```

### Step 6: Access Your Assistant

- **Backend API**: http://localhost:8000
- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs

---

## 🐳 Docker Deployment (Alternative)

### Quick Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up -d

# Access the application
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### Docker Environment File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/brainops_ai
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app

  db:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=brainops_ai
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

---

## 🎯 Immediate Usage

### 1. Access the Dashboard

Navigate to `http://localhost:3000` and you'll see:

- **Chat Interface**: Start conversing with your AI assistant
- **Voice Commands**: Click the microphone for voice interaction
- **File Operations**: Upload and manage documents
- **Task Management**: Create and track tasks
- **Workflow Automation**: Set up automated processes
- **Knowledge Base**: Search and manage company knowledge

### 2. First Commands to Try

```
# Chat Examples
"What can you help me with?"
"Create a task to review security protocols"
"Search for API documentation"
"What workflows are currently active?"

# Voice Commands
"Show me the dashboard"
"Create task for deployment"
"Search files for user guide"
"Start email processing workflow"
```

### 3. Key Features Overview

- **AI Chat**: Natural language conversations with context awareness
- **Voice Interface**: Hands-free operation with voice commands
- **File Management**: Secure file upload, download, and versioning
- **Task Tracking**: Intelligent task management and prioritization
- **Workflow Automation**: Custom automation for business processes
- **Knowledge Search**: Instant access to historical and current information

---

## 🔧 Configuration Options

### Essential Settings

```python
# backend/core/config.py
class Settings:
    # Database
    DATABASE_URL: str = "postgresql://..."
    
    # AI Services
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    DEFAULT_AI_MODEL: str = "gpt-4-turbo-preview"
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Features
    ENABLE_VOICE_INTERFACE: bool = True
    ENABLE_FILE_OPERATIONS: bool = True
    ENABLE_WORKFLOW_AUTOMATION: bool = True
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
```

### Database Configuration

```python
# Production settings
DATABASE_URL = "postgresql://user:pass@localhost/brainops_ai"

# Development settings
DATABASE_URL = "sqlite:///./brainops_ai.db"
```

---

## 🧪 Testing Your Installation

### Run System Tests

```bash
# Test core functionality
cd backend
python test_memory_core.py

# Test RAG system
python test_rag_simple.py

# Test data ingestion
python test_data_ingestion.py

# Test knowledge access
python test_knowledge_access.py

# Run all tests
python -m pytest
```

### Verify API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# Authentication test
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme123!"}'

# Chat test
curl -X POST http://localhost:8000/api/assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message":"Hello, how can you help me?"}'
```

---

## 🔐 Security Setup

### 1. Change Default Credentials

```bash
# Create admin user
python -c "
import asyncio
from services.auth import AuthService
auth = AuthService()
asyncio.run(auth.create_user(
    email='admin@yourcompany.com',
    username='admin',
    password='your_secure_password',
    is_superuser=True
))
"
```

### 2. SSL Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Environment Security

```bash
# Set secure file permissions
chmod 600 .env
chmod 600 backend/.env

# Use environment variables in production
export DATABASE_URL="postgresql://..."
export OPENAI_API_KEY="sk-..."
export SECRET_KEY="your-secret-key"
```

---

## 🚀 Production Deployment

### 1. Production Environment

```bash
# Production dependencies
pip install gunicorn uvicorn[standard]

# Start production server
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 2. Process Management

```bash
# Using systemd
sudo systemctl start brainops-ai-backend
sudo systemctl enable brainops-ai-backend

# Using supervisor
supervisord -c /etc/supervisor/conf.d/brainops-ai.conf
```

### 3. Monitoring

```bash
# Health monitoring
curl -f http://localhost:8000/api/health || exit 1

# Performance monitoring
curl http://localhost:8000/api/metrics

# Log monitoring
tail -f /var/log/brainops-ai/application.log
```

---

## 📊 Performance Optimization

### Database Optimization

```sql
-- Create indexes for better performance
CREATE INDEX idx_messages_embedding ON assistant_messages USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_embedding ON knowledge_entries USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_messages_timestamp ON assistant_messages(timestamp);
CREATE INDEX idx_tasks_status ON tasks(status);
```

### Redis Configuration

```redis
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Application Scaling

```python
# backend/main.py
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="info",
        access_log=True
    )
```

---

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Error**
   ```bash
   # Check database status
   pg_isready -h localhost -p 5432
   
   # Test connection
   psql -h localhost -U postgres -d brainops_ai
   ```

2. **Redis Connection Error**
   ```bash
   # Check Redis status
   redis-cli ping
   
   # Monitor Redis
   redis-cli monitor
   ```

3. **API Key Issues**
   ```bash
   # Verify API keys
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
   ```

4. **File Upload Issues**
   ```bash
   # Check file permissions
   ls -la uploads/
   
   # Create upload directory
   mkdir -p uploads && chmod 755 uploads
   ```

### Debug Mode

```bash
# Enable debug mode
export DEBUG=true
export LOG_LEVEL=DEBUG

# Start with debug logging
python main.py
```

---

## 📚 Next Steps

### 1. Customize Your Assistant

- **Add Custom Commands**: Extend voice commands in `services/voice_interface.py`
- **Custom Workflows**: Create automation workflows in `services/workflow_engine.py`
- **UI Customization**: Modify frontend components in `frontend/src/components/`

### 2. Integration Setup

- **External APIs**: Configure integrations in `services/integrations/`
- **Webhook Endpoints**: Set up webhooks for external systems
- **SSO Integration**: Configure single sign-on with your identity provider

### 3. Advanced Features

- **Multi-tenant Support**: Configure for multiple organizations
- **Advanced Analytics**: Set up performance and usage analytics
- **Custom AI Models**: Integrate additional AI service providers

---

## 🎉 You're Ready to Go!

Your BrainOps AI Assistant is now running and ready to transform your business operations. The system includes:

- ✅ **Complete AI Assistant**: Chat, voice, and automation capabilities
- ✅ **Production Security**: Enterprise-grade security and audit logging
- ✅ **Scalable Architecture**: Designed for growth and high availability
- ✅ **Comprehensive Testing**: Validated across all critical components
- ✅ **Full Documentation**: Complete guides and troubleshooting procedures

### Support Resources

- **Technical Documentation**: Complete system documentation
- **API Reference**: Interactive API documentation at `/docs`
- **Test Suite**: Comprehensive testing framework
- **Monitoring**: Real-time system health and performance monitoring

---

**Welcome to the future of AI-powered business automation!** 🚀

*Need help? All documentation and troubleshooting procedures are included in the system documentation.*