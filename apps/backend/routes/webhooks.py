"""
External Webhook Handlers

This module processes incoming webhooks from integrated services like Slack,
ClickUp, Stripe, and Make.com. Each webhook handler validates signatures,
processes events, and triggers appropriate BrainOps tasks or workflows.
"""

from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from typing import Optional, Dict, Any
import hmac
import hashlib
import json
from datetime import datetime

from apps.backend.core.settings import settings
from apps.backend.integrations.slack import process_slack_event, verify_slack_signature
from apps.backend.integrations.clickup import process_clickup_webhook, verify_clickup_signature
from apps.backend.integrations.stripe import process_stripe_event, construct_stripe_event
from apps.backend.integrations.make import process_make_webhook, verify_make_secret
from apps.backend.tasks import task_registry
from apps.backend.memory.memory_store import log_webhook_event


router = APIRouter()


@router.post("/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_signature: str = Header(None),
    x_slack_request_timestamp: str = Header(None)
) -> Dict[str, Any]:
    """
    Handle incoming Slack events and slash commands.
    
    Processes approval requests, task triggers, and interactive components
    from Slack workspace integrations.
    """
    # Read request body for signature verification
    body = await request.body()
    
    # Verify Slack signature for security
    if not verify_slack_signature(
        body,
        x_slack_signature,
        x_slack_request_timestamp,
        settings.SLACK_SIGNING_SECRET
    ):
        raise HTTPException(403, "Invalid Slack signature")
    
    # Parse Slack payload
    try:
        if request.headers.get("content-type") == "application/json":
            payload = json.loads(body)
        else:
            # URL-encoded form data from slash commands
            from urllib.parse import parse_qs
            parsed = parse_qs(body.decode())
            payload = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except Exception as e:
        raise HTTPException(400, f"Invalid payload format: {str(e)}")
    
    # Handle URL verification challenge from Slack
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    
    # Log webhook event for audit trail
    await log_webhook_event(
        source="slack",
        event_type=payload.get("type") or payload.get("command"),
        payload=payload,
        timestamp=datetime.utcnow()
    )
    
    # Process Slack event in background to return quickly
    background_tasks.add_task(
        process_slack_event,
        payload,
        settings.SLACK_BOT_TOKEN
    )
    
    # Return immediately for Slack's 3-second timeout
    return {"status": "accepted"}


@router.post("/clickup")
async def clickup_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_clickup_signature: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Handle ClickUp webhook events for task synchronization.
    
    Syncs task updates, status changes, and comments between ClickUp
    and BrainOps task management system.
    """
    # Read request body
    body = await request.body()
    
    # Verify ClickUp signature if configured
    if settings.CLICKUP_WEBHOOK_SECRET and x_clickup_signature:
        if not verify_clickup_signature(
            body,
            x_clickup_signature,
            settings.CLICKUP_WEBHOOK_SECRET
        ):
            raise HTTPException(403, "Invalid ClickUp signature")
    
    # Parse webhook payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")
    
    # Extract event details
    event_type = payload.get("event")
    task_data = payload.get("task") or payload.get("task_id")
    
    # Log webhook event
    await log_webhook_event(
        source="clickup",
        event_type=event_type,
        payload=payload,
        timestamp=datetime.utcnow()
    )
    
    # Map ClickUp events to BrainOps actions
    event_mapping = {
        "taskCreated": "sync_new_task",
        "taskUpdated": "update_task_status",
        "taskDeleted": "archive_task",
        "taskStatusUpdated": "update_task_progress",
        "taskCommentPosted": "add_task_note"
    }
    
    if event_type in event_mapping:
        # Queue appropriate task for background processing
        background_tasks.add_task(
            process_clickup_webhook,
            event_type,
            task_data,
            payload.get("webhook_id")
        )
    
    return {"status": "processed", "event": event_type}


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None)
) -> Dict[str, Any]:
    """
    Handle Stripe webhook events for payment automation.
    
    Triggers onboarding workflows, subscription updates, and invoice
    processing based on Stripe payment events.
    """
    # Read raw request body for signature verification
    body = await request.body()
    
    # Construct and verify Stripe event
    try:
        event = construct_stripe_event(
            body,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(400, f"Webhook signature verification failed: {str(e)}")
    
    # Log webhook event
    await log_webhook_event(
        source="stripe",
        event_type=event.type,
        payload=event.data,
        timestamp=datetime.utcnow()
    )
    
    # Handle specific Stripe events
    event_handlers = {
        "payment_intent.succeeded": handle_payment_success,
        "customer.subscription.created": handle_new_subscription,
        "customer.subscription.updated": handle_subscription_update,
        "invoice.payment_succeeded": handle_invoice_paid,
        "checkout.session.completed": handle_checkout_complete
    }
    
    handler = event_handlers.get(event.type)
    if handler:
        # Process event in background
        background_tasks.add_task(
            handler,
            event
        )
    
    # Acknowledge receipt of webhook
    return {"status": "success", "event_id": event.id}


@router.post("/make/{webhook_secret}")
async def make_webhook(
    webhook_secret: str,
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Handle Make.com (Integromat) webhook triggers.
    
    Allows Make.com scenarios to trigger BrainOps tasks using a
    secure webhook URL with embedded secret.
    """
    # Verify webhook secret matches configured value
    if not verify_make_secret(webhook_secret, settings.MAKE_WEBHOOK_SECRETS):
        raise HTTPException(403, "Invalid webhook secret")
    
    # Parse request payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    
    # Extract task configuration from Make.com
    task_type = payload.get("task_type")
    task_params = payload.get("parameters", {})
    user_id = payload.get("user_id")
    
    if not task_type or not user_id:
        raise HTTPException(400, "Missing required fields: task_type, user_id")
    
    # Validate task type exists
    if task_type not in task_registry:
        raise HTTPException(404, f"Unknown task type: {task_type}")
    
    # Log webhook event
    await log_webhook_event(
        source="make",
        event_type=f"task_trigger:{task_type}",
        payload=payload,
        timestamp=datetime.utcnow()
    )
    
    # Queue task for execution
    background_tasks.add_task(
        process_make_webhook,
        task_type,
        task_params,
        user_id,
        webhook_secret
    )
    
    return {
        "status": "accepted",
        "task_type": task_type,
        "message": f"Task {task_type} queued for execution"
    }


@router.post("/generic/{integration}/{secret}")
async def generic_webhook(
    integration: str,
    secret: str,
    request: Request,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Generic webhook handler for custom integrations.
    
    Provides a flexible endpoint for receiving webhooks from any
    service with basic secret-based authentication.
    """
    # Verify integration is allowed and secret is valid
    allowed_integrations = settings.GENERIC_WEBHOOK_INTEGRATIONS
    if integration not in allowed_integrations:
        raise HTTPException(404, f"Integration not configured: {integration}")
    
    expected_secret = allowed_integrations.get(integration, {}).get("secret")
    if secret != expected_secret:
        raise HTTPException(403, "Invalid webhook secret")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    
    # Log webhook event
    await log_webhook_event(
        source=integration,
        event_type=payload.get("event_type", "unknown"),
        payload=payload,
        timestamp=datetime.utcnow()
    )
    
    # Route to appropriate handler based on integration config
    handler_config = allowed_integrations[integration]
    if handler_config.get("task_mapping"):
        # Map webhook data to task execution
        task_type = handler_config["task_mapping"].get(
            payload.get("event_type")
        )
        
        if task_type:
            background_tasks.add_task(
                execute_mapped_task,
                task_type,
                payload,
                integration
            )
    
    return {
        "status": "received",
        "integration": integration,
        "timestamp": datetime.utcnow().isoformat()
    }


# Helper functions for specific event handlers
async def handle_payment_success(event):
    """Process successful payment and trigger onboarding."""
    # Extract customer and payment details
    customer_id = event.data.object.customer
    amount = event.data.object.amount
    
    # Trigger customer onboarding workflow
    await task_registry["customer_onboarding"].run({
        "customer_id": customer_id,
        "payment_amount": amount,
        "trigger_source": "stripe_payment"
    })


async def handle_new_subscription(event):
    """Handle new subscription creation."""
    # Update user subscription status and benefits
    subscription = event.data.object
    await update_user_subscription(
        customer_id=subscription.customer,
        plan_id=subscription.items.data[0].price.id,
        status="active"
    )
