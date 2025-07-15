# Integration Guide

The Operator integrates with third party services via tasks and webhooks.

- **Slack** – set `SLACK_WEBHOOK_URL` for notifications and configure `/brainops` slash command to point to `/webhook/slack/command`.
- **Stripe** – send payment webhooks to `/webhook/stripe` and define `STRIPE_WEBHOOK_SECRET` for signature verification.
- **GitHub** – push events trigger `/webhook/github`.
- **Make.com** – workflows can call `/webhook/make` to queue tasks.

Review environment variables in `.env.example` for the full list of available integrations.
