"""Enhanced webhook endpoints for external integrations."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.settings import Settings
from db.models import WebhookEvent
from db.session import get_db
from utils.metrics import WEBHOOK_RECEIVED, WEBHOOK_PROCESSED, WEBHOOK_FAILED
from celery_app import process_webhook_event

settings = Settings()

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookResponse(BaseModel):
    """Standard webhook response."""
    status: str
    message: Optional[str] = None
    event_id: Optional[str] = None


def verify_stripe_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Stripe webhook signature."""
    try:
        # Extract timestamp and signatures
        elements = signature.split(',')
        timestamp = None
        signatures = []
        
        for element in elements:
            key, value = element.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)
        
        if not timestamp or not signatures:
            return False
        
        # Check timestamp tolerance (5 minutes)
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:
            return False
        
        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Check if any signature matches
        return any(hmac.compare_digest(expected_sig, sig) for sig in signatures)
        
    except Exception as e:
        logger.error(f"Error verifying Stripe signature: {e}")
        return False


def verify_clickup_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify ClickUp webhook signature."""
    try:
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, signature)
        
    except Exception as e:
        logger.error(f"Error verifying ClickUp signature: {e}")
        return False


def verify_notion_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Notion webhook signature."""
    try:
        # Notion uses HMAC-SHA256
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected_sig}", signature)
        
    except Exception as e:
        logger.error(f"Error verifying Notion signature: {e}")
        return False


@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    Events handled:
    - checkout.session.completed
    - payment_intent.succeeded
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    WEBHOOK_RECEIVED.labels(source="stripe").inc()
    
    # Get raw body
    body = await request.body()
    
    # Verify signature
    if not verify_stripe_signature(body, stripe_signature, settings.STRIPE_WEBHOOK_SECRET):
        WEBHOOK_FAILED.labels(source="stripe", reason="invalid_signature").inc()
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        WEBHOOK_FAILED.labels(source="stripe", reason="invalid_json").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Check for duplicate events
    event_id = event.get("id")
    existing = db.query(WebhookEvent).filter(
        WebhookEvent.source == "stripe",
        WebhookEvent.payload["id"].astext == event_id
    ).first()
    
    if existing:
        logger.info(f"Duplicate Stripe event: {event_id}")
        return WebhookResponse(status="duplicate", event_id=event_id)
    
    # Store event
    webhook_event = WebhookEvent(
        source="stripe",
        event_type=event.get("type", "unknown"),
        payload=event,
        signature=stripe_signature
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    
    # Process event asynchronously
    process_webhook_event.delay(webhook_event.id)
    
    WEBHOOK_PROCESSED.labels(source="stripe", event_type=event.get("type")).inc()
    
    return WebhookResponse(
        status="processed",
        event_id=webhook_event.id,
        message=f"Event {event.get('type')} queued for processing"
    )


@router.post("/clickup", response_model=WebhookResponse)
async def clickup_webhook(
    request: Request,
    x_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle ClickUp webhook events.
    
    Events handled:
    - taskCreated
    - taskUpdated
    - taskDeleted
    - taskStatusUpdated
    - taskAssigneeUpdated
    - taskCommentPosted
    """
    WEBHOOK_RECEIVED.labels(source="clickup").inc()
    
    # Get raw body
    body = await request.body()
    
    # Verify signature
    if settings.CLICKUP_API_TOKEN and x_signature:
        if not verify_clickup_signature(body, x_signature, settings.CLICKUP_API_TOKEN):
            WEBHOOK_FAILED.labels(source="clickup", reason="invalid_signature").inc()
            raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        WEBHOOK_FAILED.labels(source="clickup", reason="invalid_json").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Extract event details
    event_type = event.get("event", "unknown")
    webhook_id = event.get("webhook_id")
    
    # Store event
    webhook_event = WebhookEvent(
        source="clickup",
        event_type=event_type,
        payload=event,
        signature=x_signature
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    
    # Process event asynchronously
    process_webhook_event.delay(webhook_event.id)
    
    WEBHOOK_PROCESSED.labels(source="clickup", event_type=event_type).inc()
    
    return WebhookResponse(
        status="processed",
        event_id=webhook_event.id,
        message=f"ClickUp event {event_type} queued for processing"
    )


@router.post("/notion", response_model=WebhookResponse)
async def notion_webhook(
    request: Request,
    x_notion_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle Notion webhook events.
    
    Events handled:
    - page.created
    - page.updated
    - database.created
    - database.updated
    - block.created
    - block.updated
    """
    WEBHOOK_RECEIVED.labels(source="notion").inc()
    
    # Get raw body
    body = await request.body()
    
    # Verify signature if secret is configured
    if settings.NOTION_API_KEY and x_notion_signature:
        if not verify_notion_signature(body, x_notion_signature, settings.NOTION_API_KEY):
            WEBHOOK_FAILED.labels(source="notion", reason="invalid_signature").inc()
            raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        WEBHOOK_FAILED.labels(source="notion", reason="invalid_json").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Extract event type
    event_type = "unknown"
    if "type" in event:
        event_type = event["type"]
    elif "object" in event:
        # Infer from object type
        object_type = event.get("object", "")
        if "page" in event:
            event_type = f"{object_type}.updated"
        elif "database" in event:
            event_type = f"{object_type}.updated"
    
    # Store event
    webhook_event = WebhookEvent(
        source="notion",
        event_type=event_type,
        payload=event,
        signature=x_notion_signature
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    
    # Process event asynchronously
    process_webhook_event.delay(webhook_event.id)
    
    WEBHOOK_PROCESSED.labels(source="notion", event_type=event_type).inc()
    
    return WebhookResponse(
        status="processed",
        event_id=webhook_event.id,
        message=f"Notion event {event_type} queued for processing"
    )


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle GitHub webhook events.
    
    Events handled:
    - push
    - pull_request
    - issues
    - issue_comment
    - workflow_run
    """
    WEBHOOK_RECEIVED.labels(source="github").inc()
    
    # Get raw body
    body = await request.body()
    
    # Verify signature if secret is configured
    if settings.GITHUB_SECRET and x_hub_signature_256:
        expected_sig = hmac.new(
            settings.GITHUB_SECRET.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(f"sha256={expected_sig}", x_hub_signature_256):
            WEBHOOK_FAILED.labels(source="github", reason="invalid_signature").inc()
            raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Parse event
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        WEBHOOK_FAILED.labels(source="github", reason="invalid_json").inc()
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Store event
    webhook_event = WebhookEvent(
        source="github",
        event_type=x_github_event or "unknown",
        payload=event,
        signature=x_hub_signature_256
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    
    # Process event asynchronously
    process_webhook_event.delay(webhook_event.id)
    
    WEBHOOK_PROCESSED.labels(source="github", event_type=x_github_event).inc()
    
    return WebhookResponse(
        status="processed",
        event_id=webhook_event.id,
        message=f"GitHub event {x_github_event} queued for processing"
    )


@router.get("/events")
async def list_webhook_events(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    processed: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List webhook events with filtering.
    """
    query = db.query(WebhookEvent)
    
    if source:
        query = query.filter(WebhookEvent.source == source)
    if event_type:
        query = query.filter(WebhookEvent.event_type == event_type)
    if processed is not None:
        query = query.filter(WebhookEvent.processed == processed)
    
    total = query.count()
    events = query.order_by(WebhookEvent.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "events": [
            {
                "id": e.id,
                "source": e.source,
                "event_type": e.event_type,
                "processed": e.processed,
                "processed_at": e.processed_at,
                "error": e.error,
                "retry_count": e.retry_count,
                "created_at": e.created_at
            }
            for e in events
        ]
    }


@router.post("/events/{event_id}/replay")
async def replay_webhook_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    Replay a webhook event.
    """
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Reset processing status
    event.processed = False
    event.processed_at = None
    event.error = None
    db.commit()
    
    # Queue for processing
    process_webhook_event.delay(event.id)
    
    return {"message": f"Event {event_id} queued for replay"}


@router.delete("/events/{event_id}")
async def delete_webhook_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a webhook event.
    """
    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    
    return {"message": f"Event {event_id} deleted"}