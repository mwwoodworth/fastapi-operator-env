# Production Go-Live Checklist

Use this list before launching BrainStackStudio in production.

- [ ] Set `ENVIRONMENT=production` and verify all required secrets are present
- [ ] Configure `AUTH_USERS` and `ADMIN_USERS`
- [ ] Run `celery -A celery_app worker` for background tasks
- [ ] Configure `BRAINSTACK_API_URL` and `BRAINSTACK_API_KEY`
- [ ] Configure Make.com webhooks (`MAKE_PUBLISH_WEBHOOK` and `MAKE_SALE_WEBHOOK`)
- [ ] Configure `NEWSLETTER_API_URL` and `NEWSLETTER_API_KEY`
- [ ] Point domain DNS records to hosting provider
- [ ] Enable Stripe or marketplace links in site settings
- [ ] Run database migrations
- [ ] Verify dashboard metrics and sales data update in real time
- [ ] Test a sample purchase flow end-to-end
- [ ] Trigger `generate_product_docs` for each product and review output
