# BrainOps FastAPI Backend

Production-ready FastAPI backend for BrainOps automation platform.

## Features

- 🚀 **FastAPI** - Modern, fast web framework for building APIs
- 🔐 **Authentication** - JWT-based authentication with secure token handling
- 📊 **Database** - PostgreSQL with SQLAlchemy ORM and Alembic migrations
- 🧠 **AI Integration** - OpenAI, Anthropic Claude, and Google Gemini support
- 📦 **Task Queue** - Celery for background job processing
- 🔄 **Integrations** - ClickUp, Notion, Slack, Stripe, and more
- 📝 **Logging** - Structured logging with contextual information
- 🛡️ **Security** - CORS, rate limiting, and security headers

## Project Structure

```
apps/backend/
├── agents/          # AI agent implementations
├── core/           # Core utilities (settings, logging, security)
├── db/             # Database models and migrations
├── integrations/   # External service integrations
├── memory/         # Vector storage and knowledge base
├── routes/         # API endpoints
├── tasks/          # Background tasks
└── main.py         # Application entry point
```

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/mwwoodworth/fastapi-operator-env.git
   cd fastapi-operator-env
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   uvicorn apps.backend.main:app --reload
   ```

## Deployment

### Render

The application is configured for deployment on Render:

1. Connect your GitHub repository to Render
2. Use the provided `render.yaml` configuration
3. Set environment variables in Render dashboard
4. Deploy!

### Docker

Build and run with Docker:

```bash
docker build -t brainops-backend .
docker run -p 8000:8000 --env-file .env brainops-backend
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

See `.env.example` for all available configuration options. Key variables:

- `SECRET_KEY` - JWT signing key (generate a secure random string)
- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase project URL
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic Claude API key

## Development

### Code Style

```bash
# Format code
black apps/

# Lint
flake8 apps/

# Type checking
mypy apps/
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=apps.backend
```

## License

Proprietary - BrainOps © 2024