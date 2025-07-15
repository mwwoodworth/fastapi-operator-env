# 🤖 BrainOps AI Ops Bot

> **Production-ready DevOps automation and monitoring bot for multi-service infrastructure management.**

## 🚀 Overview

BrainOps AI Ops Bot is a comprehensive DevOps automation platform that integrates with 11+ services to provide:
- **Real-time health monitoring** across all integrated services
- **Automated deployment triggers** with rollback capabilities
- **Multi-channel alerting** via Slack, email, and webhooks
- **Scheduled task management** with cron-like scheduling
- **Service resource management** and monitoring
- **CLI and API interfaces** for maximum flexibility

## 📦 Supported Integrations

### Core Services
- **Render** - Deployment management and monitoring
- **Vercel** - Frontend deployment and analytics
- **GitHub** - Repository management and CI/CD
- **Slack** - Team communication and alerts

### Business Tools
- **ClickUp** - Project management and task tracking
- **Notion** - Knowledge base and documentation
- **Airtable** - Database management and workflows
- **Stripe** - Payment processing and billing

### Data & Storage
- **Supabase** - Database and backend services
- **PostgreSQL** - Primary data storage

### AI & ML
- **OpenAI** - GPT models and AI automation
- **Claude/Anthropic** - Advanced AI capabilities

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Interface │    │   API Server    │    │  Web Dashboard  │
│                 │    │  (FastAPI)      │    │   (Future)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │              Core Engine                        │
         │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
         │  │  Monitor    │ │  Scheduler  │ │   Alerts    ││
         │  │  System     │ │  Engine     │ │  Manager    ││
         │  └─────────────┘ └─────────────┘ └─────────────┘│
         └─────────────────────────────────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │              Service Connectors                 │
         │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
         │  │ Render  │ │ Vercel  │ │ GitHub  │ │  Slack  ││
         │  └─────────┘ └─────────┘ └─────────┘ └─────────┘│
         │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
         │  │ClickUp  │ │ Notion  │ │Airtable │ │ Stripe  ││
         │  └─────────┘ └─────────┘ └─────────┘ └─────────┘│
         └─────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/mwwoodworth/brainops-ai-ops-bot.git
cd brainops-ai-ops-bot

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 2. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run health check
python bot.py health --all

# Start API server
python bot.py serve --port 8000

# Schedule monitoring (runs in background)
python bot.py schedule --interval 5
```

### 3. Docker Deployment

```bash
# Build image
docker build -t brainops-ai-ops-bot .

# Run container
docker run -p 8000:8000 --env-file .env brainops-ai-ops-bot
```

## 🌐 Render Deployment

### One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mwwoodworth/brainops-ai-ops-bot)

### Manual Deployment

1. **Create Render Account** at https://render.com
2. **Create New Web Service** from Dashboard
3. **Connect Repository**: `https://github.com/mwwoodworth/brainops-ai-ops-bot`
4. **Configure Settings**:
   - Runtime: `Docker`
   - Branch: `main`
   - Build Command: `Auto-detected`
   - Start Command: `Auto-detected`
   - Health Check Path: `/health`
5. **Set Environment Variables** (see [Environment Variables](#environment-variables))
6. **Deploy**

## 🔧 Environment Variables

### Required Variables

```bash
# Database (provided by Render)
DATABASE_URL=postgresql://...

# Core Services (at least one required)
RENDER_API_KEY=your_render_api_key
GITHUB_TOKEN=ghp_your_github_token
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# Alert Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
EMAIL_ALERT_RECIPIENTS=["admin@example.com"]
```

### Optional Variables

```bash
# Additional Services
VERCEL_TOKEN=your_vercel_token
CLICKUP_API_TOKEN=your_clickup_token
NOTION_API_TOKEN=secret_your_notion_token
STRIPE_API_KEY_LIVE=sk_live_your_stripe_key
SUPABASE_URL=https://your-project.supabase.co
OPENAI_API_KEY=sk-your_openai_key
CLAUDE_API_KEY=sk-ant-your_claude_key

# Feature Flags
ENABLE_SLACK_ALERTS=true
ENABLE_EMAIL_ALERTS=true
ENABLE_HEALTH_CHECKS=true
ENABLE_AUTO_DEPLOY=false
```

## 📚 API Documentation

### Core Endpoints

#### Health Check
```http
GET /health
```
Returns basic health status of the API.

#### Service Health Check
```http
POST /health/check
Content-Type: application/json

{
  "services": ["render", "github", "slack"],
  "parallel": true
}
```

#### Deployment Trigger
```http
POST /deploy
Content-Type: application/json

{
  "service": "render",
  "app": "my-app",
  "branch": "main"
}
```

#### Alert Management
```http
POST /alerts/send
Content-Type: application/json

{
  "service": "render",
  "severity": "error",
  "message": "Service is down",
  "details": {"response_time": "timeout"}
}
```

#### Job Scheduling
```http
POST /jobs
Content-Type: application/json

{
  "func_name": "health_check",
  "interval_minutes": 5
}
```

### Full API Documentation

Once deployed, visit `/docs` for interactive API documentation.

## 🖥️ CLI Usage

### Health Monitoring

```bash
# Check all services
python bot.py health --all

# Check specific service
python bot.py health --service render

# Get health summary
python bot.py health --all --format table
```

### Deployment Management

```bash
# Deploy to Render
python bot.py deploy --service render --app my-app --branch main

# Deploy with wait
python bot.py deploy --service render --app my-app --wait
```

### Log Management

```bash
# Fetch logs
python bot.py logs --service render --app my-app --lines 100

# Follow logs
python bot.py logs --service render --app my-app --follow
```

### Resource Management

```bash
# List services
python bot.py list --service render --resource services

# List databases
python bot.py list --service render --resource databases

# List deployments
python bot.py list --service github --resource deployments
```

### Scheduled Monitoring

```bash
# Run health checks every 5 minutes
python bot.py schedule --interval 5

# Monitor specific services
python bot.py schedule --interval 10 --services render,github,slack
```

### Alert Testing

```bash
# Test all alert channels
python bot.py test-alerts

# Check bot configuration
python bot.py info
```

## 📊 Monitoring & Alerting

### Alert Channels

- **Slack**: Real-time notifications to configured channels
- **Email**: Multi-recipient email alerts via Resend
- **Webhooks**: Custom webhook endpoints for integration

### Alert Types

- **Critical**: Service downtime, deployment failures
- **Warning**: Performance degradation, high response times
- **Info**: Deployment success, scheduled task completion

### Alert Configuration

```bash
# Alert thresholds
ALERT_COOLDOWN_MINUTES=15
ERROR_THRESHOLD=5
RESPONSE_TIME_THRESHOLD_MS=5000

# Alert channels
ENABLE_SLACK_ALERTS=true
ENABLE_EMAIL_ALERTS=true
SLACK_ALERT_CHANNEL=#alerts
EMAIL_ALERT_RECIPIENTS=["admin@example.com", "ops@example.com"]
```

## 🔐 Security

### Authentication

- **Environment Variables**: All credentials stored securely
- **API Keys**: Masked in logs and API responses
- **JWT Tokens**: Secure API authentication (optional)

### Best Practices

- Use service-specific API keys with minimal permissions
- Rotate credentials regularly
- Enable audit logging for all operations
- Use secure webhook URLs with authentication

## 🛠️ Development

### Project Structure

```
brainops-ai-ops-bot/
├── api/                 # FastAPI application
│   ├── __init__.py
│   └── app.py
├── bot.py              # CLI interface
├── config/             # Configuration management
│   ├── __init__.py
│   ├── settings.py
│   └── alerts.yaml
├── connectors/         # Service integrations
│   ├── __init__.py
│   ├── base.py
│   ├── render.py
│   ├── github.py
│   └── ...
├── core/              # Core functionality
│   ├── __init__.py
│   ├── monitor.py
│   ├── scheduler.py
│   └── alerts.py
├── Dockerfile
├── requirements.txt
├── render.yaml
└── README.md
```

### Adding New Connectors

1. Create new connector in `connectors/` directory
2. Inherit from `BaseConnector` class
3. Implement required methods:
   - `health_check()`
   - `deploy()`
   - `get_logs()`
   - `list_resources()`
4. Add configuration to `settings.py`
5. Register in `connectors/__init__.py`

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Service Connection Errors

```bash
# Check credentials
python bot.py info

# Test specific service
python bot.py health --service render
```

#### 2. Deployment Failures

```bash
# Check logs
python bot.py logs --service render --app my-app

# Verify environment variables
python bot.py config
```

#### 3. Alert Delivery Issues

```bash
# Test alerts
python bot.py test-alerts

# Check configuration
python bot.py info
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG_MODE=true
python bot.py --debug health --all
```

## 📝 Deployment Checklist

- [ ] Environment variables configured
- [ ] Database connection established
- [ ] Service credentials validated
- [ ] Health checks passing
- [ ] Alert channels tested
- [ ] Backup and monitoring configured
- [ ] SSL certificates installed
- [ ] Domain configured (if applicable)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/mwwoodworth/brainops-ai-ops-bot/issues)
- **Documentation**: [API Docs](https://brainops-ai-ops-bot.onrender.com/docs)
- **Email**: support@brainops.com

---

**Built with ❤️ by BrainOps**

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>