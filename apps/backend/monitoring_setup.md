# BrainOps Monitoring & Alerting Setup

## 1. Sentry Error Tracking

### Configuration
```bash
# In .env file
SENTRY_DSN=https://your-key@sentry.io/your-project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### Integration Points
- Automatic error capture in all API endpoints
- Performance monitoring for slow endpoints
- User context tracking
- Custom error boundaries for critical operations

### Alert Rules
1. **Critical Errors**: Immediate notification for 500 errors
2. **Performance**: Alert when P95 response time > 1s
3. **Error Rate**: Alert when error rate > 5% over 5 minutes
4. **Memory Usage**: Alert when memory > 80% for 10 minutes

## 2. Application Metrics (Prometheus/Grafana)

### Metrics Exported
- `http_requests_total`: Total HTTP requests by endpoint
- `http_request_duration_seconds`: Request latency histogram
- `active_connections`: Current WebSocket connections
- `workflow_executions_total`: Workflow execution count
- `ai_api_calls_total`: External AI service calls
- `database_connections_active`: Active DB connections
- `cache_hit_ratio`: Redis cache effectiveness

### Dashboards
1. **System Overview**: CPU, Memory, Disk, Network
2. **API Performance**: Request rates, latencies, errors
3. **Business Metrics**: Users, workflows, revenue
4. **AI Usage**: Token consumption, API costs
5. **Database Health**: Query performance, connection pools

## 3. Health Checks

### Endpoints
- `/health`: Basic liveness check
- `/api/v1/health`: API availability
- `/api/v1/health/detailed`: Component status

### Components Monitored
```json
{
  "database": {"status": "healthy", "latency_ms": 5},
  "redis": {"status": "healthy", "latency_ms": 2},
  "scheduler": {"status": "healthy", "jobs_pending": 12},
  "ai_providers": {
    "openai": {"status": "healthy", "rate_limit": "40%"},
    "anthropic": {"status": "healthy", "rate_limit": "20%"}
  },
  "integrations": {
    "stripe": {"status": "healthy"},
    "slack": {"status": "healthy"},
    "clickup": {"status": "degraded", "error": "rate_limited"}
  }
}
```

## 4. Logging (ELK Stack)

### Log Levels
- **ERROR**: Application errors, failed operations
- **WARNING**: Deprecations, performance issues
- **INFO**: Normal operations, user actions
- **DEBUG**: Detailed execution flow (dev only)

### Structured Logging
```json
{
  "timestamp": "2025-01-18T12:00:00Z",
  "level": "INFO",
  "service": "brainops-api",
  "trace_id": "abc123",
  "user_id": "user_456",
  "endpoint": "/api/v1/workflows/execute",
  "duration_ms": 125,
  "status_code": 200,
  "message": "Workflow executed successfully"
}
```

### Log Retention
- Production logs: 30 days
- Debug logs: 7 days
- Audit logs: 1 year
- Security logs: 2 years

## 5. Uptime Monitoring (Pingdom/UptimeRobot)

### Monitored Endpoints
1. `https://api.brainops.com/health` - Every 1 minute
2. `https://api.brainops.com/api/v1/health` - Every 5 minutes
3. `https://app.brainops.com` - Every 5 minutes
4. `https://docs.brainops.com` - Every 15 minutes

### Alert Escalation
1. First failure: Wait for confirmation (2 checks)
2. Confirmed down: Email + Slack notification
3. Down > 5 minutes: SMS to on-call
4. Down > 15 minutes: Call on-call engineer

## 6. Database Monitoring

### Metrics
- Query performance (slow query log)
- Connection pool utilization
- Table sizes and growth rate
- Index usage statistics
- Replication lag (if applicable)

### Automated Actions
- Kill long-running queries (> 30s)
- Alert on connection pool exhaustion
- Auto-vacuum when needed
- Index recommendation reports

## 7. Security Monitoring

### Tracked Events
- Failed login attempts
- API key usage patterns
- Unusual data access patterns
- Rate limit violations
- SQL injection attempts

### Alerts
- 5+ failed logins from same IP: Block IP
- API key used from new location: Email notification
- Bulk data export: Audit log + notification
- Detected attack pattern: Auto-block + alert

## 8. Business Metrics

### KPIs Tracked
- Daily Active Users (DAU)
- Workflow execution success rate
- Average workflow completion time
- API response times by endpoint
- Revenue metrics (MRR, churn)
- Feature adoption rates

### Reports
- Daily operational summary
- Weekly business metrics
- Monthly SLA report
- Quarterly performance review

## 9. Backup Monitoring

### Backup Schedule
- Database: Every 6 hours
- File uploads: Daily incremental
- Configuration: On every change
- Full system: Weekly

### Verification
- Automated restore tests: Weekly
- Backup integrity checks: Daily
- Storage usage alerts: When > 80%
- Retention policy enforcement

## 10. Alert Configuration

### Notification Channels
1. **Email**: All alerts
2. **Slack**: #ops-alerts channel
3. **PagerDuty**: Critical production issues
4. **SMS**: System down, data loss risk

### Alert Priorities
- **P0 (Critical)**: System down, data loss risk
- **P1 (High)**: Major feature broken, performance degraded
- **P2 (Medium)**: Minor feature issues, warnings
- **P3 (Low)**: Informational, metrics

### On-Call Rotation
- Primary: Rotates weekly
- Secondary: Always available
- Escalation: Engineering manager
- Business hours: 9 AM - 6 PM PST
- After hours: P0/P1 only

## Setup Commands

```bash
# Install monitoring agents
curl -sS https://sentry.io/install.sh | bash
docker run -d -p 9090:9090 prom/prometheus
docker run -d -p 3000:3000 grafana/grafana

# Configure alerts
./scripts/setup_monitoring.sh

# Test alert channels
./scripts/test_alerts.sh
```

## Dashboard URLs

- Sentry: https://sentry.io/organizations/brainops
- Grafana: https://monitoring.brainops.com
- Logs: https://logs.brainops.com
- Uptime: https://status.brainops.com

## Runbooks

Detailed runbooks for common issues:
1. [High Memory Usage](./runbooks/high-memory.md)
2. [Database Connection Errors](./runbooks/db-connection.md)
3. [API Rate Limiting](./runbooks/rate-limiting.md)
4. [Deployment Rollback](./runbooks/rollback.md)
5. [Data Recovery](./runbooks/data-recovery.md)