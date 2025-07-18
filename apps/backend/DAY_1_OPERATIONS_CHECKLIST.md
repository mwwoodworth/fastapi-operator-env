# 📋 BrainOps Day-1 Operations Checklist

**System**: BrainOps ERP/CRM/Automation Platform  
**Launch Date**: _______________  
**Production URL**: https://api.brainops.com  

---

## 🚀 Pre-Launch Verification (T-minus 1 hour)

### Configuration
- [ ] All production environment variables set in `.env`
- [ ] Database connection string verified
- [ ] Redis connection string verified  
- [ ] All API keys are production keys (not test)
- [ ] JWT secrets are unique and secure (32+ chars)
- [ ] CORS origins updated for production domains

### Infrastructure
- [ ] PostgreSQL database provisioned and accessible
- [ ] Redis cache instance running
- [ ] DNS A records pointing to production IPs
- [ ] SSL certificates installed and valid
- [ ] Load balancer health checks configured
- [ ] Auto-scaling policies active

### Security
- [ ] Firewall rules reviewed and applied
- [ ] Database access restricted to app servers only
- [ ] Redis password protected
- [ ] API rate limiting enabled
- [ ] DDoS protection active
- [ ] Secrets rotated from development

---

## 🎯 Launch Sequence (T-0)

### 1. Deploy Application
```bash
# Run deployment script
./deploy_production.sh

# Or use platform-specific deployment
render up
```

- [ ] Deployment started
- [ ] Build successful
- [ ] Container health checks passing
- [ ] All instances running (minimum 2)

### 2. Verify Core Services
- [ ] Health check endpoint responding: `curl https://api.brainops.com/health`
- [ ] API health check passing: `curl https://api.brainops.com/api/v1/health`
- [ ] Database migrations completed
- [ ] Redis cache operational
- [ ] Background workers running

### 3. Run Smoke Tests
```bash
python smoke_tests.py https://api.brainops.com
```

- [ ] All health checks pass
- [ ] Authentication flow works
- [ ] Core CRUD operations functional
- [ ] Payment integration active
- [ ] Email sending verified

---

## 🔍 Post-Launch Verification (T+30 minutes)

### Application Monitoring
- [ ] Sentry receiving error reports
- [ ] No critical errors in first 30 minutes
- [ ] Response times under SLA (<200ms p95)
- [ ] Memory usage stable
- [ ] CPU usage normal

### Integration Verification
- [ ] Stripe webhooks receiving events
- [ ] Slack notifications working
- [ ] Email delivery confirmed
- [ ] ClickUp sync active
- [ ] Weather API responding

### User Validation
- [ ] Test user can register
- [ ] Test user can login
- [ ] Test user can create project
- [ ] Test user can generate estimate
- [ ] Test user can create invoice

---

## 📊 Day-1 Metrics Dashboard

### System Health (First 24 hours)
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Uptime | 99.9% | ___% | ⬜ |
| Error Rate | <1% | ___% | ⬜ |
| Avg Response Time | <200ms | ___ms | ⬜ |
| Peak Concurrent Users | 50+ | ___ | ⬜ |
| Total API Calls | - | ___ | ⬜ |

### Business Metrics
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| New User Registrations | 10+ | ___ | ⬜ |
| Projects Created | 5+ | ___ | ⬜ |
| Workflows Executed | 20+ | ___ | ⬜ |
| AI API Calls | 50+ | ___ | ⬜ |

---

## 🚨 Incident Response Procedures

### Severity Levels
- **P0 (Critical)**: Complete outage, data loss risk
- **P1 (High)**: Major feature broken, significant degradation  
- **P2 (Medium)**: Minor feature issues, some users affected
- **P3 (Low)**: Cosmetic issues, workarounds available

### Response Times
- **P0**: Immediate (page on-call)
- **P1**: Within 30 minutes
- **P2**: Within 2 hours
- **P3**: Next business day

### Escalation Path
1. **First Responder**: Check monitoring dashboards
2. **On-Call Engineer**: Investigate and attempt fix
3. **Technical Lead**: Major decisions, rollback approval
4. **Founder/CTO**: Business impact decisions

### Common Issues & Solutions

#### High Error Rate
```bash
# Check recent deployments
git log --oneline -10

# View error details in Sentry
# Check for pattern in errors

# If deployment-related, rollback:
./rollback_production.sh
```

#### Database Connection Errors
```bash
# Check connection pool
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Restart connection pool if needed
# Scale up database if at capacity
```

#### Memory Leaks
```bash
# Identify leaking service
docker stats

# Restart affected containers
docker restart brainops-backend-xxx

# Investigate with profiler if recurring
```

---

## 📝 Day-1 Handoff Tasks

### Morning (9 AM - 12 PM)
- [ ] Review overnight metrics
- [ ] Check error logs for patterns
- [ ] Verify all scheduled jobs ran
- [ ] Test critical user flows
- [ ] Update status page

### Afternoon (12 PM - 5 PM)
- [ ] Complete remaining founder actions
- [ ] Configure automated backups
- [ ] Set up additional monitoring alerts
- [ ] Document any issues encountered
- [ ] Plan Day-2 optimizations

### End of Day (5 PM)
- [ ] Generate Day-1 report
- [ ] Schedule Day-2 standup
- [ ] Confirm on-call coverage
- [ ] Backup verification
- [ ] Celebrate successful launch! 🎉

---

## 🔧 Ongoing Operations

### Daily Tasks
- [ ] Review error logs (9 AM)
- [ ] Check system metrics (9 AM, 2 PM)
- [ ] Verify backup completion (10 AM)
- [ ] Monitor user feedback channels
- [ ] Update operational runbooks

### Weekly Tasks
- [ ] Performance review meeting
- [ ] Security scan results
- [ ] Database maintenance window
- [ ] Dependency updates check
- [ ] Team retrospective

### Monthly Tasks
- [ ] Full system backup restore test
- [ ] Disaster recovery drill
- [ ] Performance benchmark update
- [ ] Cost optimization review
- [ ] Security audit

---

## 📞 Important Contacts

### Internal Team
- **On-Call Engineer**: ________________
- **Technical Lead**: ________________
- **DevOps**: ________________
- **Product Manager**: ________________

### External Support
- **Render Support**: support@render.com
- **Database Admin**: ________________
- **Security Team**: ________________
- **Legal/Compliance**: ________________

### Emergency Contacts
- **PagerDuty**: ________________
- **Incident Hotline**: ________________
- **Founder/CEO**: ________________

---

## ✅ Sign-Off

**Launch Commander**: ________________  
**Date/Time**: ________________  
**Status**: ⬜ GO / ⬜ NO-GO  

**Notes**:
```
________________________________________________
________________________________________________
________________________________________________
```

---

## 🎯 Success Criteria

The production launch is considered successful when:
1. ✅ All smoke tests pass
2. ✅ No P0/P1 incidents in first 24 hours
3. ✅ Uptime maintained above 99.9%
4. ✅ User registrations occurring
5. ✅ All integrations functional
6. ✅ Monitoring and alerting active
7. ✅ Team has runbook access
8. ✅ Founder approval received

**System Status**: ⬜ OPERATIONAL / ⬜ DEGRADED / ⬜ DOWN

---

*This checklist should be reviewed and updated after each production deployment.*