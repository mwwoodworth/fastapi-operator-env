# BrainOps AI Ops Bot

A comprehensive DevOps automation bot that integrates with multiple services to provide health checks, monitoring, deployments, and real-time alerts.

## Features

- **Multi-Service Integration**: ClickUp, Notion, GitHub, Slack, Airtable, Supabase, Stripe, Render, Vercel, and more
- **Health Monitoring**: Real-time health checks for all integrated services
- **Automated Deployments**: Trigger deployments and monitor build status
- **Alert System**: Slack and email notifications for errors, downtime, or build failures
- **Secure Credential Management**: All secrets stored securely with masked logging
- **Extensible Architecture**: Easy to add new service integrations
- **Multiple Run Modes**: CLI, Server (API), or Scheduled Jobs

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd brainops-ai-ops-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and add your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials (see Configuration section below).

### 3. Usage

#### CLI Mode
```bash
# Check health of all services
python bot.py health --all

# Check specific service
python bot.py health --service github

# Deploy to Render
python bot.py deploy --service render --app myapp

# Fetch logs
python bot.py logs --service vercel --app myapp --lines 100

# List resources
python bot.py list --service clickup --resource tasks
```

#### Server Mode (API)
```bash
# Start the API server
python bot.py serve --port 8000

# API endpoints will be available at:
# GET  /health/{service}
# POST /deploy/{service}
# GET  /logs/{service}/{app}
# GET  /resources/{service}/{type}
```

#### Scheduled Mode
```bash
# Run scheduled health checks every 5 minutes
python bot.py schedule --interval 5
```

## Configuration

### Environment Variables

Create a `.env` file with the following structure:

```env
# ClickUp
CLICKUP_API_TOKEN=your_token_here
CLICKUP_WORKSPACE_ID=your_workspace_id

# Notion
NOTION_API_TOKEN=your_token_here
NOTION_DATABASE_IDS={"master": "db_id", "bids": "db_id"}

# GitHub
GITHUB_TOKEN=your_token_here
GITHUB_REPOS=["repo1", "repo2"]

# Slack
SLACK_BOT_TOKEN=your_token_here
SLACK_WEBHOOK_URL=your_webhook_url
SLACK_ALERT_CHANNEL=#alerts

# Add other services...
```

See `.env.example` for the complete list of required variables.

### Alert Configuration

Configure alert preferences in `config/alerts.yaml`:

```yaml
alerts:
  channels:
    - type: slack
      channel: "#critical-alerts"
      severity: ["critical", "error"]
    - type: email
      recipients: ["ops@brainops.com"]
      severity: ["critical"]
  
  thresholds:
    response_time: 5000  # ms
    error_rate: 0.05     # 5%
    uptime: 0.99         # 99%
```

## Service Integrations

### Currently Supported Services

1. **ClickUp**: Tasks, lists, workspaces
2. **Notion**: Databases, pages, blocks
3. **GitHub**: Repos, actions, deployments
4. **Slack**: Messages, channels, webhooks
5. **Airtable**: Bases, tables, records
6. **Supabase**: Database, auth, storage
7. **Stripe**: Payments, subscriptions, webhooks
8. **Render**: Apps, services, deployments
9. **Vercel**: Projects, deployments, domains
10. **Make.com**: Scenarios, webhooks, executions
11. **Toggl**: Time tracking, reports
12. **ConvertKit**: Subscribers, forms, sequences
13. **Tana**: Nodes, workspaces
14. **OpenAI/Claude**: API usage, models

### Adding New Integrations

1. Create a new connector in `connectors/`:

```python
# connectors/newservice.py
from connectors.base import BaseConnector

class NewServiceConnector(BaseConnector):
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key')
    
    def health_check(self):
        # Implement health check
        pass
    
    def get_resources(self, resource_type):
        # Implement resource listing
        pass
```

2. Register in `connectors/__init__.py`:

```python
CONNECTORS = {
    'newservice': NewServiceConnector,
    # ... other connectors
}
```

3. Add configuration to `.env.example`

## Monitoring & Alerts

The bot continuously monitors service health and sends alerts when:

- Service is down or unreachable
- API errors exceed threshold
- Build/deployment failures
- Response time degradation
- Custom conditions (configurable)

### Alert Types

- **Critical**: Service down, auth failures
- **Error**: Build failures, API errors
- **Warning**: Slow response, high error rate
- **Info**: Successful deployments, status updates

## Security

- All credentials stored in environment variables
- Secrets are masked in logs (shows only first/last 4 chars)
- Encryption for sensitive data in transit
- Audit logging for all operations
- Role-based access control (when in server mode)

## Development

### Project Structure

```
brainops-ai-ops-bot/
├── bot.py                 # Main entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment file
├── config/
│   ├── __init__.py
│   ├── settings.py       # Configuration management
│   └── alerts.yaml       # Alert configuration
├── connectors/
│   ├── __init__.py
│   ├── base.py          # Base connector class
│   ├── clickup.py       # ClickUp integration
│   ├── notion.py        # Notion integration
│   └── ...              # Other service connectors
├── core/
│   ├── __init__.py
│   ├── monitor.py       # Health monitoring
│   ├── alerts.py        # Alert management
│   ├── scheduler.py     # Job scheduling
│   └── security.py      # Security utilities
├── api/
│   ├── __init__.py
│   ├── app.py          # FastAPI application
│   └── routes.py       # API routes
└── tests/
    ├── __init__.py
    └── test_*.py       # Unit tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test
pytest tests/test_connectors.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API tokens in `.env`
   - Check token permissions/scopes
   - Ensure tokens haven't expired

2. **Connection Timeouts**
   - Check network connectivity
   - Verify service endpoints
   - Adjust timeout settings in config

3. **Missing Dependencies**
   - Run `pip install -r requirements.txt`
   - Check Python version (3.8+ required)

### Debug Mode

Enable debug logging:

```bash
# Set in .env
LOG_LEVEL=DEBUG

# Or via command line
python bot.py --debug health --all
```

## License

MIT License - See LICENSE file for details

## Support

- Documentation: [docs.brainops.com/ai-ops-bot](https://docs.brainops.com/ai-ops-bot)
- Issues: [GitHub Issues](https://github.com/brainops/ai-ops-bot/issues)
- Email: support@brainops.com