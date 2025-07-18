# BrainOps FastAPI Backend - Complete Endpoint Specification

## Overview
This document outlines all required endpoints for the BrainOps ecosystem, spanning all business verticals and ensuring complete coverage for a production-grade, AI-powered SaaS system.

## API Structure
- Base URL: `https://api.brainops.com`
- API Version: `/api/v1`
- Authentication: JWT Bearer tokens
- Content-Type: `application/json`

## 1. Authentication & User Management

### Core Auth Endpoints ✅ (Implemented)
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout user
- `GET /auth/me` - Get current user
- `PUT /auth/me` - Update user profile
- `POST /auth/change-password` - Change password
- `POST /auth/verify-email/{token}` - Verify email

### Missing Auth Endpoints ❌
- `POST /auth/forgot-password` - Request password reset
- `POST /auth/reset-password` - Reset password with token
- `POST /auth/resend-verification` - Resend email verification
- `POST /auth/two-factor/enable` - Enable 2FA
- `POST /auth/two-factor/disable` - Disable 2FA
- `POST /auth/two-factor/verify` - Verify 2FA code
- `GET /auth/sessions` - List active sessions
- `DELETE /auth/sessions/{session_id}` - Revoke session
- `POST /auth/api-keys` - Create API key
- `GET /auth/api-keys` - List API keys
- `DELETE /auth/api-keys/{key_id}` - Revoke API key

## 2. User & Team Management

### User Endpoints ❌
- `GET /users` - List users (admin)
- `GET /users/{user_id}` - Get user details
- `PUT /users/{user_id}` - Update user (admin)
- `DELETE /users/{user_id}` - Delete user
- `POST /users/{user_id}/suspend` - Suspend user
- `POST /users/{user_id}/activate` - Activate user
- `GET /users/{user_id}/activity` - Get user activity

### Team/Organization Endpoints ❌
- `POST /teams` - Create team
- `GET /teams` - List teams
- `GET /teams/{team_id}` - Get team details
- `PUT /teams/{team_id}` - Update team
- `DELETE /teams/{team_id}` - Delete team
- `POST /teams/{team_id}/members` - Add member
- `DELETE /teams/{team_id}/members/{user_id}` - Remove member
- `PUT /teams/{team_id}/members/{user_id}/role` - Update member role

## 3. Project Management

### Project CRUD ❌
- `POST /projects` - Create project
- `GET /projects` - List projects
- `GET /projects/{project_id}` - Get project
- `PUT /projects/{project_id}` - Update project
- `DELETE /projects/{project_id}` - Delete project
- `POST /projects/{project_id}/archive` - Archive project
- `POST /projects/{project_id}/restore` - Restore project

### Task Management ❌
- `POST /projects/{project_id}/tasks` - Create task
- `GET /projects/{project_id}/tasks` - List tasks
- `GET /tasks/{task_id}` - Get task
- `PUT /tasks/{task_id}` - Update task
- `DELETE /tasks/{task_id}` - Delete task
- `POST /tasks/{task_id}/assign` - Assign task
- `POST /tasks/{task_id}/complete` - Complete task
- `POST /tasks/{task_id}/comments` - Add comment
- `GET /tasks/{task_id}/comments` - Get comments

## 4. AI Services

### Chat & Conversation ❌
- `POST /ai/chat` - Send chat message
- `GET /ai/chat/sessions` - List chat sessions
- `GET /ai/chat/sessions/{session_id}` - Get session history
- `DELETE /ai/chat/sessions/{session_id}` - Delete session
- `POST /ai/chat/sessions/{session_id}/export` - Export conversation

### Document Generation ❌
- `POST /ai/documents/generate` - Generate document
- `POST /ai/documents/templates` - Create template
- `GET /ai/documents/templates` - List templates
- `PUT /ai/documents/templates/{template_id}` - Update template
- `DELETE /ai/documents/templates/{template_id}` - Delete template

### Analysis & Intelligence ❌
- `POST /ai/analyze/text` - Analyze text
- `POST /ai/analyze/document` - Analyze document
- `POST /ai/analyze/image` - Analyze image
- `POST /ai/summarize` - Summarize content
- `POST /ai/translate` - Translate text
- `POST /ai/extract` - Extract entities/data

### Model Management ❌
- `GET /ai/models` - List available models
- `POST /ai/models/select` - Select model for session
- `GET /ai/models/usage` - Get usage stats
- `GET /ai/models/costs` - Get cost breakdown

## 5. Memory & Knowledge Base

### Memory Operations ✅ (Implemented)
- `POST /memory/write` - Write memory
- `POST /memory/query` - Query memories
- `POST /memory/context` - Get context
- `GET /memory/{memory_id}` - Get memory
- `PUT /memory/{memory_id}` - Update memory
- `DELETE /memory/{memory_id}` - Delete memory

### Document Management ✅/❌ (Partial)
- `POST /memory/upload` ✅ - Upload document
- `GET /documents` ❌ - List documents
- `GET /documents/{doc_id}` ❌ - Get document
- `DELETE /documents/{doc_id}` ❌ - Delete document
- `POST /documents/{doc_id}/reprocess` ❌ - Reprocess document

### Knowledge Organization ❌
- `POST /collections` - Create collection
- `GET /collections` - List collections
- `PUT /collections/{collection_id}` - Update collection
- `DELETE /collections/{collection_id}` - Delete collection
- `POST /collections/{collection_id}/items` - Add to collection

## 6. Automation & Workflows

### Workflow Management ❌
- `POST /workflows` - Create workflow
- `GET /workflows` - List workflows
- `GET /workflows/{workflow_id}` - Get workflow
- `PUT /workflows/{workflow_id}` - Update workflow
- `DELETE /workflows/{workflow_id}` - Delete workflow
- `POST /workflows/{workflow_id}/execute` - Execute workflow
- `GET /workflows/{workflow_id}/runs` - Get execution history

### Triggers & Scheduling ❌
- `POST /triggers` - Create trigger
- `GET /triggers` - List triggers
- `PUT /triggers/{trigger_id}` - Update trigger
- `DELETE /triggers/{trigger_id}` - Delete trigger
- `POST /triggers/{trigger_id}/enable` - Enable trigger
- `POST /triggers/{trigger_id}/disable` - Disable trigger

### Task Execution ✅/❌ (Partial)
- `POST /tasks/design` ✅ - Design task
- `POST /tasks/run` ✅ - Run task
- `GET /tasks/{task_id}/status` ✅ - Get status
- `GET /tasks/{task_id}/result` ✅ - Get result
- `GET /tasks/history` ✅ - Task history
- `POST /tasks/{task_id}/cancel` ❌ - Cancel task
- `POST /tasks/{task_id}/retry` ❌ - Retry task

## 7. Integrations

### Webhook Management ✅/❌ (Partial)
- `POST /webhooks/slack` ✅ - Slack webhook
- `POST /webhooks/clickup` ✅ - ClickUp webhook
- `POST /webhooks/stripe` ✅ - Stripe webhook
- `POST /webhooks/make/{secret}` ✅ - Make webhook
- `POST /webhooks/generic/{integration}/{secret}` ✅ - Generic webhook
- `GET /webhooks` ❌ - List webhooks
- `POST /webhooks/configure` ❌ - Configure webhook
- `DELETE /webhooks/{webhook_id}` ❌ - Delete webhook

### Integration Management ❌
- `GET /integrations` - List integrations
- `POST /integrations/{type}/connect` - Connect integration
- `DELETE /integrations/{type}/disconnect` - Disconnect
- `GET /integrations/{type}/status` - Check status
- `POST /integrations/{type}/sync` - Force sync

## 8. Marketplace & Products

### Product Management ❌
- `POST /products` - Create product
- `GET /products` - List products
- `GET /products/{product_id}` - Get product
- `PUT /products/{product_id}` - Update product
- `DELETE /products/{product_id}` - Delete product
- `POST /products/{product_id}/publish` - Publish product
- `POST /products/{product_id}/unpublish` - Unpublish

### Purchase & Licensing ❌
- `POST /purchases` - Create purchase
- `GET /purchases` - List purchases
- `GET /purchases/{purchase_id}` - Get purchase
- `POST /purchases/{purchase_id}/download` - Download product
- `GET /licenses` - List licenses
- `POST /licenses/activate` - Activate license
- `POST /licenses/deactivate` - Deactivate license

## 9. Field Operations / Roofing

### Inspections ❌
- `POST /inspections` - Create inspection
- `GET /inspections` - List inspections
- `GET /inspections/{inspection_id}` - Get inspection
- `PUT /inspections/{inspection_id}` - Update inspection
- `POST /inspections/{inspection_id}/photos` - Upload photos
- `POST /inspections/{inspection_id}/complete` - Complete

### Estimates ❌
- `POST /estimates` - Create estimate
- `GET /estimates` - List estimates
- `GET /estimates/{estimate_id}` - Get estimate
- `PUT /estimates/{estimate_id}` - Update estimate
- `POST /estimates/{estimate_id}/send` - Send to client
- `POST /estimates/{estimate_id}/approve` - Approve estimate

### Field Data ❌
- `POST /measurements` - Submit measurements
- `POST /photos/upload` - Upload field photo
- `GET /photos` - List photos
- `POST /signatures` - Capture signature
- `POST /locations` - Log location

## 10. Billing & Subscriptions

### Subscription Management ❌
- `GET /subscriptions` - List subscriptions
- `POST /subscriptions` - Create subscription
- `PUT /subscriptions/{sub_id}` - Update subscription
- `DELETE /subscriptions/{sub_id}` - Cancel subscription
- `POST /subscriptions/{sub_id}/upgrade` - Upgrade plan
- `POST /subscriptions/{sub_id}/downgrade` - Downgrade plan

### Billing ❌
- `GET /invoices` - List invoices
- `GET /invoices/{invoice_id}` - Get invoice
- `POST /invoices/{invoice_id}/pay` - Pay invoice
- `GET /payment-methods` - List payment methods
- `POST /payment-methods` - Add payment method
- `DELETE /payment-methods/{method_id}` - Remove method

## 11. Analytics & Reporting

### Analytics ❌
- `GET /analytics/overview` - Dashboard overview
- `GET /analytics/usage` - Usage analytics
- `GET /analytics/revenue` - Revenue analytics
- `GET /analytics/performance` - Performance metrics
- `POST /analytics/custom` - Custom query

### Reports ❌
- `POST /reports/generate` - Generate report
- `GET /reports` - List reports
- `GET /reports/{report_id}` - Get report
- `POST /reports/{report_id}/schedule` - Schedule report
- `POST /reports/{report_id}/export` - Export report

## 12. Admin & System

### System Management ❌
- `GET /admin/stats` - System statistics
- `GET /admin/health/detailed` ✅ - Detailed health
- `GET /admin/logs` - System logs
- `GET /admin/config` - Get configuration
- `PUT /admin/config` - Update configuration
- `POST /admin/maintenance/enable` - Enable maintenance
- `POST /admin/maintenance/disable` - Disable maintenance

### Audit & Compliance ❌
- `GET /audit/logs` - Audit logs
- `GET /audit/events` - Audit events
- `POST /audit/export` - Export audit data
- `GET /compliance/gdpr/export/{user_id}` - GDPR export
- `DELETE /compliance/gdpr/delete/{user_id}` - GDPR delete

## 13. Communication

### Notifications ❌
- `GET /notifications` - List notifications
- `POST /notifications/mark-read` - Mark as read
- `POST /notifications/mark-all-read` - Mark all read
- `PUT /notifications/preferences` - Update preferences

### Messaging ❌
- `POST /messages/send` - Send message
- `GET /messages` - List messages
- `GET /messages/{thread_id}` - Get thread
- `POST /messages/{message_id}/reply` - Reply to message

## 14. Search & Discovery

### Search ❌
- `POST /search` - Global search
- `POST /search/advanced` - Advanced search
- `GET /search/suggestions` - Search suggestions
- `GET /search/history` - Search history

## Summary

### Implementation Status:
- ✅ Fully Implemented: 18 endpoints
- ❌ Not Implemented: 180+ endpoints
- 🔧 Partially Implemented: 8 endpoints

### Priority Implementation Order:
1. Complete missing auth/security endpoints
2. Implement core CRUD for users, projects, tasks
3. Build out AI service endpoints
4. Complete automation/workflow system
5. Add marketplace functionality
6. Implement field operations
7. Build billing/subscription system
8. Add analytics and admin tools