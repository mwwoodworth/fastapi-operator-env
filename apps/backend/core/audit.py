"""
Audit logging functionality for tracking user actions.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json
from ..core.logging import get_logger

logger = get_logger(__name__)


async def audit_log(
    user_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Log an audit event for compliance and security tracking.
    
    Args:
        user_id: ID of the user performing the action
        action: Action being performed (e.g., 'task_created', 'task_updated')
        resource_type: Type of resource (e.g., 'task', 'project', 'user')
        resource_id: ID of the resource being acted upon
        details: Additional details about the action
        ip_address: IP address of the request
    """
    audit_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": str(user_id),
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "details": details or {},
        "ip_address": ip_address
    }
    
    # Log to structured logger
    logger.info("audit_event", **audit_entry)
    
    # In production, would also:
    # 1. Write to audit database table
    # 2. Send to SIEM system
    # 3. Trigger alerts for sensitive actions