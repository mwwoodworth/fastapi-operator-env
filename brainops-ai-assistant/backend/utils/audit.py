"""Audit logging for security and compliance."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import aiofiles

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from core.database import get_db
from core.config import settings
from models.db import AuditLog as AuditLogDB


class AuditLogger:
    """Centralized audit logging for all operations."""
    
    def __init__(self):
        self.audit_dir = settings.OPS_ROOT_DIR / "audit_logs"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure we have a file-based backup
        self.current_log_file = self.audit_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    async def log_action(
        self,
        user_id: int,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Dict[str, Any] = None,
        success: bool = True,
        error: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log a general action."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "success": success,
            "error": error,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        # Write to file immediately
        await self._write_to_file(log_entry)
        
        # Store in database
        log_id = await self._store_in_db(log_entry)
        
        # Log critical failures to system logger
        if not success and error:
            logger.error(f"Audit: Failed action {action} by user {user_id}: {error}")
        
        return log_id
    
    async def log_file_operation(
        self,
        operation: str,
        path: str,
        user_id: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log file system operations."""
        return await self.log_action(
            user_id=user_id or 0,
            action=f"file_{operation}",
            resource_type="file",
            resource_id=path,
            details={
                "operation": operation,
                "path": path,
                **(details or {})
            },
            success=success,
            error=error
        )
    
    async def log_command_execution(
        self,
        command: str,
        args: List[str] = None,
        user_id: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
        exit_code: Optional[int] = None,
        stdout_lines: Optional[int] = None,
        stderr_lines: Optional[int] = None,
        duration: Optional[float] = None,
        cwd: Optional[str] = None,
        status: Optional[str] = None
    ):
        """Log command executions."""
        details = {
            "command": command,
            "args": args or [],
            "status": status
        }
        
        if exit_code is not None:
            details["exit_code"] = exit_code
        if stdout_lines is not None:
            details["stdout_lines"] = stdout_lines
        if stderr_lines is not None:
            details["stderr_lines"] = stderr_lines
        if duration is not None:
            details["duration_seconds"] = duration
        if cwd is not None:
            details["working_directory"] = cwd
        
        return await self.log_action(
            user_id=user_id or 0,
            action="command_execute",
            resource_type="command",
            resource_id=command,
            details=details,
            success=success,
            error=error
        )
    
    async def log_api_request(
        self,
        method: str,
        path: str,
        user_id: Optional[int] = None,
        status_code: int = 200,
        duration_ms: Optional[float] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log API requests."""
        return await self.log_action(
            user_id=user_id or 0,
            action="api_request",
            resource_type="api",
            resource_id=f"{method} {path}",
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "request_size": request_size,
                "response_size": response_size
            },
            success=status_code < 400,
            error=error,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    async def log_authentication(
        self,
        user_id: int,
        event: str,  # login, logout, token_refresh, failed_login
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication events."""
        return await self.log_action(
            user_id=user_id,
            action=f"auth_{event}",
            resource_type="authentication",
            details=details or {},
            success=success,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    async def log_ai_interaction(
        self,
        user_id: int,
        session_id: str,
        interaction_type: str,  # chat, voice, api
        model: str,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log AI model interactions."""
        return await self.log_action(
            user_id=user_id,
            action="ai_interaction",
            resource_type="ai_session",
            resource_id=session_id,
            details={
                "interaction_type": interaction_type,
                "model": model,
                "tokens_used": tokens_used,
                "cost_usd": cost,
                "duration_ms": duration_ms
            },
            success=success,
            error=error
        )
    
    async def log_security_event(
        self,
        event_type: str,  # unauthorized_access, permission_denied, suspicious_activity
        user_id: Optional[int] = None,
        details: Dict[str, Any] = None,
        severity: str = "medium",  # low, medium, high, critical
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log security-related events."""
        log_entry = await self.log_action(
            user_id=user_id or 0,
            action=f"security_{event_type}",
            resource_type="security",
            details={
                "severity": severity,
                **(details or {})
            },
            success=False,  # Security events are always concerning
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Alert on high/critical security events
        if severity in ["high", "critical"]:
            logger.critical(f"SECURITY EVENT: {event_type} - User: {user_id} - Details: {details}")
            # TODO: Send alerts via email/slack
        
        return log_entry
    
    async def get_user_activity(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity logs for a specific user."""
        async with get_db() as db:
            query = select(AuditLogDB).where(
                AuditLogDB.user_id == user_id
            )
            
            if action_filter:
                query = query.where(AuditLogDB.action.like(f"%{action_filter}%"))
            
            query = query.order_by(desc(AuditLogDB.timestamp))
            query = query.limit(limit).offset(offset)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            return [self._db_to_dict(log) for log in logs]
    
    async def get_security_events(
        self,
        severity: Optional[str] = None,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get security event logs."""
        async with get_db() as db:
            query = select(AuditLogDB).where(
                AuditLogDB.action.like("security_%")
            )
            
            if severity:
                query = query.where(
                    AuditLogDB.details["severity"].astext == severity
                )
            
            if since:
                query = query.where(AuditLogDB.timestamp >= since)
            
            query = query.order_by(desc(AuditLogDB.timestamp))
            query = query.limit(limit)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            return [self._db_to_dict(log) for log in logs]
    
    async def get_command_history(
        self,
        limit: int = 50,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get command execution history."""
        async with get_db() as db:
            query = select(AuditLogDB).where(
                AuditLogDB.action == "command_execute"
            )
            
            if user_id:
                query = query.where(AuditLogDB.user_id == user_id)
            
            query = query.order_by(desc(AuditLogDB.timestamp))
            query = query.limit(limit)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            return [self._db_to_dict(log) for log in logs]
    
    async def generate_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate an audit report for a time period."""
        async with get_db() as db:
            query = select(AuditLogDB).where(
                AuditLogDB.timestamp >= start_date,
                AuditLogDB.timestamp <= end_date
            )
            
            if user_id:
                query = query.where(AuditLogDB.user_id == user_id)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            # Analyze logs
            total_actions = len(logs)
            failed_actions = sum(1 for log in logs if not log.success)
            
            action_counts = {}
            user_activity = {}
            
            for log in logs:
                # Count by action type
                action_counts[log.action] = action_counts.get(log.action, 0) + 1
                
                # Count by user
                user_activity[log.user_id] = user_activity.get(log.user_id, 0) + 1
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "summary": {
                    "total_actions": total_actions,
                    "successful_actions": total_actions - failed_actions,
                    "failed_actions": failed_actions,
                    "failure_rate": failed_actions / total_actions if total_actions > 0 else 0
                },
                "action_breakdown": action_counts,
                "user_activity": user_activity,
                "top_users": sorted(
                    user_activity.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            }
    
    async def _write_to_file(self, log_entry: Dict[str, Any]):
        """Write log entry to file for backup."""
        try:
            async with aiofiles.open(self.current_log_file, mode='a') as f:
                await f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")
    
    async def _store_in_db(self, log_entry: Dict[str, Any]) -> str:
        """Store log entry in database."""
        try:
            async with get_db() as db:
                db_log = AuditLogDB(
                    id=str(uuid.uuid4()),
                    user_id=log_entry["user_id"],
                    action=log_entry["action"],
                    resource_type=log_entry.get("resource_type"),
                    resource_id=log_entry.get("resource_id"),
                    details=log_entry.get("details", {}),
                    success=log_entry["success"],
                    error=log_entry.get("error"),
                    ip_address=log_entry.get("ip_address"),
                    user_agent=log_entry.get("user_agent"),
                    timestamp=datetime.fromisoformat(log_entry["timestamp"])
                )
                db.add(db_log)
                await db.commit()
                return db_log.id
        except Exception as e:
            logger.error(f"Failed to store audit log in database: {e}")
            # Return a fallback ID
            return f"file_only_{datetime.utcnow().timestamp()}"
    
    def _db_to_dict(self, log: AuditLogDB) -> Dict[str, Any]:
        """Convert database model to dictionary."""
        return {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "success": log.success,
            "error": log.error,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent
        }


# Convenience function for quick logging
audit = AuditLogger()