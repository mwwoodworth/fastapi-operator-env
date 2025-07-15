"""Memory service for persistent session and context management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from loguru import logger
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.config import settings
from models.db import (
    AssistantSessionDB,
    AssistantMessageDB,
    AssistantActionDB,
    User
)
from models.assistant import (
    AssistantSession,
    AssistantMessage,
    AssistantAction,
    ActionType
)


class MemoryService:
    """Persistent memory service for assistant conversations and context."""
    
    def __init__(self):
        self.cache_ttl = timedelta(hours=24)
        self.max_context_messages = 100
        self.context_cache: Dict[str, Dict[str, Any]] = {}
    
    async def get_user_context(self, user_id: int) -> Dict[str, Any]:
        """Get user context including preferences and history."""
        try:
            async with get_db() as db:
                # Get user info
                user_result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return {}
                
                # Get recent session statistics
                recent_sessions = await db.execute(
                    select(AssistantSessionDB)
                    .where(AssistantSessionDB.user_id == user_id)
                    .where(AssistantSessionDB.created_at >= datetime.utcnow() - timedelta(days=30))
                    .order_by(desc(AssistantSessionDB.created_at))
                    .limit(10)
                )
                
                sessions = recent_sessions.scalars().all()
                
                # Get frequently used actions
                frequent_actions = await self._get_frequent_actions(user_id)
                
                # Get user preferences (stored in latest session context)
                preferences = {}
                if sessions:
                    latest_session = sessions[0]
                    if latest_session.context:
                        preferences = latest_session.context.get("preferences", {})
                
                context = {
                    "user_id": user_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "preferences": preferences,
                    "recent_sessions_count": len(sessions),
                    "frequent_actions": frequent_actions,
                    "last_active": sessions[0].updated_at.isoformat() if sessions else None
                }
                
                # Cache context
                self.context_cache[f"user_{user_id}"] = {
                    "context": context,
                    "cached_at": datetime.utcnow()
                }
                
                return context
                
        except Exception as e:
            logger.error(f"Error getting user context for user {user_id}: {e}")
            return {}
    
    async def store_message(
        self,
        session_id: str,
        message: AssistantMessage
    ) -> str:
        """Store a message in the database."""
        try:
            async with get_db() as db:
                # Create database message
                db_message = AssistantMessageDB(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role=message.role,
                    content=message.content,
                    timestamp=message.timestamp,
                    message_type=message.message_type,
                    attachments=message.attachments or [],
                    metadata=message.metadata or {},
                    context=message.context or {}
                )
                
                db.add(db_message)
                
                # Store associated actions
                if message.actions:
                    for action in message.actions:
                        db_action = AssistantActionDB(
                            id=str(uuid.uuid4()),
                            message_id=db_message.id,
                            type=action.type.value,
                            status=action.status,
                            details=action.details or {},
                            result=action.result,
                            error=action.error,
                            timestamp=action.timestamp,
                            confirmation_required=action.confirmation_required,
                            confirmed_by=action.confirmed_by,
                            confirmed_at=action.confirmed_at
                        )
                        db.add(db_action)
                
                await db.commit()
                
                # Update session timestamp
                await self._update_session_timestamp(session_id)
                
                return db_message.id
                
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            raise
    
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[AssistantMessage]:
        """Get messages for a session."""
        try:
            async with get_db() as db:
                # Get messages with actions
                result = await db.execute(
                    select(AssistantMessageDB)
                    .options(selectinload(AssistantMessageDB.actions))
                    .where(AssistantMessageDB.session_id == session_id)
                    .order_by(AssistantMessageDB.timestamp)
                    .limit(limit)
                    .offset(offset)
                )
                
                db_messages = result.scalars().all()
                
                # Convert to domain models
                messages = []
                for db_msg in db_messages:
                    # Convert actions
                    actions = []
                    for db_action in db_msg.actions:
                        action = AssistantAction(
                            type=ActionType(db_action.type),
                            status=db_action.status,
                            details=db_action.details,
                            result=db_action.result,
                            error=db_action.error,
                            timestamp=db_action.timestamp,
                            confirmation_required=db_action.confirmation_required,
                            confirmed_by=db_action.confirmed_by,
                            confirmed_at=db_action.confirmed_at
                        )
                        actions.append(action)
                    
                    message = AssistantMessage(
                        role=db_msg.role,
                        content=db_msg.content,
                        timestamp=db_msg.timestamp,
                        message_type=db_msg.message_type,
                        actions=actions,
                        attachments=db_msg.attachments,
                        metadata=db_msg.metadata,
                        context=db_msg.context
                    )
                    messages.append(message)
                
                return messages
                
        except Exception as e:
            logger.error(f"Error getting session messages: {e}")
            return []
    
    async def search_messages(
        self,
        user_id: int,
        query: str,
        limit: int = 20,
        message_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search through user's messages."""
        try:
            async with get_db() as db:
                # Build query
                search_query = select(AssistantMessageDB).join(
                    AssistantSessionDB,
                    AssistantMessageDB.session_id == AssistantSessionDB.id
                ).where(
                    AssistantSessionDB.user_id == user_id
                ).where(
                    AssistantMessageDB.content.ilike(f"%{query}%")
                )
                
                if message_type:
                    search_query = search_query.where(
                        AssistantMessageDB.message_type == message_type
                    )
                
                search_query = search_query.order_by(
                    desc(AssistantMessageDB.timestamp)
                ).limit(limit)
                
                result = await db.execute(search_query)
                messages = result.scalars().all()
                
                # Format results
                results = []
                for msg in messages:
                    results.append({
                        "id": msg.id,
                        "session_id": msg.session_id,
                        "role": msg.role,
                        "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "message_type": msg.message_type,
                        "relevance_score": self._calculate_relevance(msg.content, query)
                    })
                
                # Sort by relevance
                results.sort(key=lambda x: x["relevance_score"], reverse=True)
                
                return results
                
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []
    
    async def save_session(self, session: AssistantSession):
        """Save session to database."""
        try:
            async with get_db() as db:
                # Update or create session
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.id == session.id
                    )
                )
                
                db_session = result.scalar_one_or_none()
                
                if db_session:
                    # Update existing
                    db_session.updated_at = session.updated_at
                    db_session.ended_at = session.ended_at
                    db_session.context = session.context
                    db_session.active = session.active
                    db_session.mode = session.mode
                else:
                    # Create new
                    db_session = AssistantSessionDB(
                        id=session.id,
                        user_id=session.user_id,
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                        ended_at=session.ended_at,
                        context=session.context,
                        active=session.active,
                        mode=session.mode
                    )
                    db.add(db_session)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            raise
    
    async def load_session(self, session_id: str) -> Optional[AssistantSession]:
        """Load session from database."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.id == session_id
                    )
                )
                
                db_session = result.scalar_one_or_none()
                
                if not db_session:
                    return None
                
                # Load messages
                messages = await self.get_session_messages(session_id)
                
                # Create session object
                session = AssistantSession(
                    id=db_session.id,
                    user_id=db_session.user_id,
                    created_at=db_session.created_at,
                    updated_at=db_session.updated_at,
                    ended_at=db_session.ended_at,
                    messages=messages,
                    context=db_session.context,
                    active=db_session.active,
                    mode=db_session.mode
                )
                
                return session
                
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return None
    
    async def store_pending_action(
        self,
        session_id: str,
        pending_id: str,
        action: Dict[str, Any]
    ):
        """Store a pending action awaiting confirmation."""
        try:
            async with get_db() as db:
                # Store in session context
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.id == session_id
                    )
                )
                
                db_session = result.scalar_one_or_none()
                
                if db_session:
                    if not db_session.context:
                        db_session.context = {}
                    
                    if "pending_actions" not in db_session.context:
                        db_session.context["pending_actions"] = {}
                    
                    db_session.context["pending_actions"][pending_id] = {
                        "action": action,
                        "created_at": datetime.utcnow().isoformat(),
                        "expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat()
                    }
                    
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"Error storing pending action: {e}")
            raise
    
    async def get_pending_action(self, pending_id: str) -> Optional[Dict[str, Any]]:
        """Get a pending action by ID."""
        try:
            async with get_db() as db:
                # Search all sessions for the pending action
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.context.contains({"pending_actions": {pending_id: {}}})
                    )
                )
                
                db_session = result.scalar_one_or_none()
                
                if not db_session or not db_session.context:
                    return None
                
                pending_actions = db_session.context.get("pending_actions", {})
                pending_action = pending_actions.get(pending_id)
                
                if not pending_action:
                    return None
                
                # Check expiration
                expires_at = datetime.fromisoformat(pending_action["expires_at"])
                if datetime.utcnow() > expires_at:
                    # Remove expired action
                    del pending_actions[pending_id]
                    await db.commit()
                    return None
                
                return pending_action["action"]
                
        except Exception as e:
            logger.error(f"Error getting pending action: {e}")
            return None
    
    async def update_user_preferences(
        self,
        user_id: int,
        preferences: Dict[str, Any]
    ):
        """Update user preferences."""
        try:
            async with get_db() as db:
                # Get user's latest session
                result = await db.execute(
                    select(AssistantSessionDB)
                    .where(AssistantSessionDB.user_id == user_id)
                    .order_by(desc(AssistantSessionDB.updated_at))
                    .limit(1)
                )
                
                db_session = result.scalar_one_or_none()
                
                if db_session:
                    if not db_session.context:
                        db_session.context = {}
                    
                    db_session.context["preferences"] = preferences
                    await db.commit()
                    
                    # Update cache
                    cache_key = f"user_{user_id}"
                    if cache_key in self.context_cache:
                        self.context_cache[cache_key]["context"]["preferences"] = preferences
                        
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            raise
    
    async def get_conversation_summary(
        self,
        session_id: str,
        max_messages: int = 20
    ) -> Dict[str, Any]:
        """Get a summary of the conversation."""
        try:
            messages = await self.get_session_messages(session_id, max_messages)
            
            if not messages:
                return {"summary": "No messages in this conversation."}
            
            # Calculate statistics
            total_messages = len(messages)
            user_messages = sum(1 for m in messages if m.role == "user")
            assistant_messages = sum(1 for m in messages if m.role == "assistant")
            
            # Count actions
            total_actions = sum(len(m.actions or []) for m in messages)
            action_types = {}
            for msg in messages:
                if msg.actions:
                    for action in msg.actions:
                        action_types[action.type.value] = action_types.get(action.type.value, 0) + 1
            
            # Get timespan
            start_time = messages[0].timestamp
            end_time = messages[-1].timestamp
            duration = end_time - start_time
            
            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "total_actions": total_actions,
                "action_breakdown": action_types,
                "duration_minutes": duration.total_seconds() / 60,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "avg_message_length": sum(len(m.content) for m in messages) / total_messages
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_sessions(self, days_old: int = 90):
        """Clean up old sessions and messages."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            async with get_db() as db:
                # Delete old sessions
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.updated_at < cutoff_date
                    )
                )
                
                old_sessions = result.scalars().all()
                
                for session in old_sessions:
                    # Delete messages and actions
                    await db.execute(
                        select(AssistantMessageDB).where(
                            AssistantMessageDB.session_id == session.id
                        )
                    )
                    
                    # Delete session
                    await db.delete(session)
                
                await db.commit()
                
                logger.info(f"Cleaned up {len(old_sessions)} old sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")
            raise
    
    # Helper methods
    async def _update_session_timestamp(self, session_id: str):
        """Update session timestamp."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(AssistantSessionDB).where(
                        AssistantSessionDB.id == session_id
                    )
                )
                
                db_session = result.scalar_one_or_none()
                
                if db_session:
                    db_session.updated_at = datetime.utcnow()
                    await db.commit()
                    
        except Exception as e:
            logger.error(f"Error updating session timestamp: {e}")
    
    async def _get_frequent_actions(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get frequently used actions for a user."""
        try:
            async with get_db() as db:
                # Get actions from recent sessions
                result = await db.execute(
                    select(AssistantActionDB)
                    .join(AssistantMessageDB, AssistantActionDB.message_id == AssistantMessageDB.id)
                    .join(AssistantSessionDB, AssistantMessageDB.session_id == AssistantSessionDB.id)
                    .where(AssistantSessionDB.user_id == user_id)
                    .where(AssistantActionDB.timestamp >= datetime.utcnow() - timedelta(days=30))
                )
                
                actions = result.scalars().all()
                
                # Count action types
                action_counts = {}
                for action in actions:
                    action_counts[action.type] = action_counts.get(action.type, 0) + 1
                
                # Sort by frequency
                frequent_actions = sorted(
                    action_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:limit]
                
                return [
                    {"action_type": action_type, "count": count}
                    for action_type, count in frequent_actions
                ]
                
        except Exception as e:
            logger.error(f"Error getting frequent actions: {e}")
            return []
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """Calculate relevance score for search results."""
        content_lower = content.lower()
        query_lower = query.lower()
        
        # Simple relevance scoring
        score = 0.0
        
        # Exact match
        if query_lower in content_lower:
            score += 1.0
        
        # Word matches
        query_words = query_lower.split()
        content_words = content_lower.split()
        
        matching_words = sum(1 for word in query_words if word in content_words)
        if query_words:
            score += (matching_words / len(query_words)) * 0.5
        
        # Length penalty (shorter matches are more relevant)
        length_factor = min(1.0, 100 / len(content))
        score *= length_factor
        
        return score