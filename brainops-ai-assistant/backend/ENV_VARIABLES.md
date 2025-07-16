# BrainOps AI Assistant - Environment Variables Documentation

This document lists all environment variables required for the BrainOps AI Assistant backend.

## Required Environment Variables

### Core Application Settings

- **PORT** (default: 8000)
  - The port on which the application will run
  - For Render.com deployment, set to 10000
  - Example: `PORT=8000`

- **SECRET_KEY** (required)
  - Secret key for JWT token signing and session management
  - Should be a long, random string
  - Example: `SECRET_KEY=your-very-long-random-secret-key-here`

### Database Configuration

- **DATABASE_URL** (required)
  - PostgreSQL connection string
  - Format: `postgresql://username:password@host:port/database`
  - Example: `DATABASE_URL=postgresql://user:pass@localhost:5432/brainops_ai`

- **REDIS_URL** (default: redis://localhost:6379/0)
  - Redis connection string for caching and task queues
  - Example: `REDIS_URL=redis://localhost:6379/0`

### AI Service API Keys

- **OPENAI_API_KEY** (required)
  - OpenAI API key for GPT models
  - Get from: https://platform.openai.com/api-keys
  - Example: `OPENAI_API_KEY=sk-...`

- **ANTHROPIC_API_KEY** (required)
  - Anthropic API key for Claude models
  - Get from: https://console.anthropic.com/
  - Example: `ANTHROPIC_API_KEY=sk-ant-...`

- **GOOGLE_AI_API_KEY** (optional)
  - Google AI API key for Gemini models
  - Example: `GOOGLE_AI_API_KEY=...`

### Voice Service Configuration

- **ELEVENLABS_API_KEY** (optional)
  - ElevenLabs API key for text-to-speech
  - Example: `ELEVENLABS_API_KEY=...`

- **WHISPER_MODEL** (default: base)
  - Whisper model size for speech recognition
  - Options: tiny, base, small, medium, large
  - Example: `WHISPER_MODEL=base`

### Integration Services

- **MAKE_WEBHOOK_URL** (optional)
  - Make.com webhook URL for workflow automation
  - Example: `MAKE_WEBHOOK_URL=https://hook.make.com/...`

- **CLICKUP_API_TOKEN** (optional)
  - ClickUp API token for task management integration
  - Example: `CLICKUP_API_TOKEN=pk_...`

- **NOTION_API_KEY** (optional)
  - Notion API key for knowledge base integration
  - Example: `NOTION_API_KEY=secret_...`

### Security & CORS

- **ALLOWED_ORIGINS** (default: ["http://localhost:3000", "http://localhost:3001"])
  - Comma-separated list of allowed CORS origins
  - Example: `ALLOWED_ORIGINS=["http://localhost:3000","https://app.brainops.ai"]`

- **ALGORITHM** (default: HS256)
  - JWT signing algorithm
  - Example: `ALGORITHM=HS256`

- **ACCESS_TOKEN_EXPIRE_MINUTES** (default: 30)
  - JWT token expiration time in minutes
  - Example: `ACCESS_TOKEN_EXPIRE_MINUTES=1440`

### File Storage Configuration

- **OPS_ROOT_DIR** (default: /home/brainops/operations)
  - Root directory for operations files
  - Example: `OPS_ROOT_DIR=/app/operations`

- **MAX_FILE_SIZE_MB** (default: 100)
  - Maximum file upload size in megabytes
  - Example: `MAX_FILE_SIZE_MB=50`

### Monitoring

- **SENTRY_DSN** (optional)
  - Sentry DSN for error tracking
  - Example: `SENTRY_DSN=https://...@sentry.io/...`

- **LOG_LEVEL** (default: INFO)
  - Logging level
  - Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Example: `LOG_LEVEL=INFO`

### Other Settings

- **DEBUG** (default: false)
  - Enable debug mode
  - Example: `DEBUG=false`

- **REQUIRE_CONFIRMATION** (default: true)
  - Require confirmation for dangerous operations
  - Example: `REQUIRE_CONFIRMATION=true`

- **COMMAND_TIMEOUT_SECONDS** (default: 300)
  - Command execution timeout in seconds
  - Example: `COMMAND_TIMEOUT_SECONDS=300`

- **MAX_CONCURRENT_TASKS** (default: 10)
  - Maximum number of concurrent background tasks
  - Example: `MAX_CONCURRENT_TASKS=10`

## Example .env File

```env
# Core Settings
PORT=8000
SECRET_KEY=your-very-secure-secret-key-here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/brainops_ai
REDIS_URL=redis://localhost:6379/0

# AI Services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional Services
ELEVENLABS_API_KEY=...
CLICKUP_API_TOKEN=pk_...
NOTION_API_KEY=secret_...

# Security
ALLOWED_ORIGINS=["http://localhost:3000","https://app.brainops.ai"]
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Monitoring
LOG_LEVEL=INFO
DEBUG=false
```

## Deployment Notes

### Render.com
- Set `PORT=10000` in environment variables
- Database URL will be provided by Render
- Add all required API keys

### Docker
- Use `docker run -p 8000:8000 --env-file .env brainops-ai-backend`
- Or override individual variables: `docker run -e PORT=10000 -e DATABASE_URL=... brainops-ai-backend`

### Local Development
- Copy `.env.example` to `.env`
- Fill in all required values
- Run `python main.py` or `uvicorn main:app --reload`