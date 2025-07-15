"""BrainOps AI Assistant Core Service."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncGenerator

from loguru import logger
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from core.config import settings
from models.assistant import (
    AssistantSession,
    AssistantMessage,
    AssistantAction,
    ActionType
)
from services.memory import MemoryService
from services.file_ops import FileOperationsService
from services.command_executor import CommandExecutor
from services.task_manager import TaskManager
from services.workflow_engine import WorkflowEngine
from services.knowledge_base import KnowledgeBase
from services.ai_orchestrator import AIOrchestrator
from utils.safety import SafetyChecker
from utils.audit import AuditLogger


class AssistantService:
    """Main AI Assistant service orchestrating all capabilities."""
    
    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        # Initialize services
        self.memory = MemoryService()
        self.file_ops = FileOperationsService()
        self.command_executor = CommandExecutor()
        self.task_manager = TaskManager()
        self.workflow_engine = WorkflowEngine()
        self.knowledge_base = KnowledgeBase()
        self.ai_orchestrator = AIOrchestrator()
        
        # Safety and audit
        self.safety_checker = SafetyChecker()
        self.audit_logger = AuditLogger()
        
        # Active sessions
        self.sessions: Dict[str, AssistantSession] = {}
        
        # System prompt
        self.system_prompt = """You are the BrainOps AI Chief of Staff, a highly capable AI assistant with full operational control over business, technical, and personal operations.

Your capabilities include:
- File system operations (read, write, create, delete files)
- Command execution (with safety checks)
- Task and project management
- AI agent orchestration
- Workflow automation
- Code review and QA
- Knowledge base access
- Real-time voice interaction

You must:
1. Always confirm destructive operations before execution
2. Log all actions for audit purposes
3. Provide clear explanations of what you're doing
4. Handle errors gracefully with recovery suggestions
5. Maintain context across conversations
6. Proactively suggest optimizations and improvements

You have access to the full operational context and can execute any authorized operation to help manage and automate all aspects of the business."""
    
    async def create_session(self, user_id: int) -> str:
        """Create a new assistant session."""
        session_id = str(uuid.uuid4())
        
        # Load user context
        user_context = await self.memory.get_user_context(user_id)
        
        # Create session
        session = AssistantSession(
            id=session_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            context=user_context,
            messages=[]
        )
        
        self.sessions[session_id] = session
        
        # Log session creation
        await self.audit_logger.log_action(
            user_id=user_id,
            action="session_created",
            details={"session_id": session_id}
        )
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        message_type: str = "chat",
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process a message from the user."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Invalid session: {session_id}")
        
        # Add user message to session
        user_msg = AssistantMessage(
            role="user",
            content=message,
            timestamp=datetime.now(timezone.utc),
            message_type=message_type,
            context=context
        )
        session.messages.append(user_msg)
        
        # Store in memory
        await self.memory.store_message(session_id, user_msg)
        
        # Analyze intent and required actions
        intent_analysis = await self._analyze_intent(message, session)
        
        # Execute actions if needed
        actions_taken = []
        if intent_analysis.get("actions"):
            for action in intent_analysis["actions"]:
                result = await self._execute_action(session, action)
                actions_taken.append(result)
        
        # Generate response
        response = await self._generate_response(
            session=session,
            intent=intent_analysis,
            actions=actions_taken
        )
        
        # Add assistant response to session
        assistant_msg = AssistantMessage(
            role="assistant",
            content=response["content"],
            timestamp=datetime.now(timezone.utc),
            message_type="response",
            actions=actions_taken,
            metadata=response.get("metadata", {})
        )
        session.messages.append(assistant_msg)
        
        # Store in memory
        await self.memory.store_message(session_id, assistant_msg)
        
        return {
            "session_id": session_id,
            "response": response["content"],
            "actions": actions_taken,
            "metadata": response.get("metadata", {}),
            "suggestions": response.get("suggestions", [])
        }
    
    async def _analyze_intent(
        self,
        message: str,
        session: AssistantSession
    ) -> Dict[str, Any]:
        """Analyze user intent and determine required actions."""
        # Get recent context
        recent_messages = session.messages[-10:]
        context_str = "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in recent_messages
        ])
        
        # Use Claude for intent analysis
        prompt = f"""Analyze this user request and determine what actions are needed.

Context:
{context_str}

Current request: {message}

Identify:
1. Primary intent
2. Required actions (file operations, commands, tasks, etc.)
3. Any safety concerns
4. Required confirmations

Return a JSON object with:
- intent: string description
- actions: array of action objects
- requires_confirmation: boolean
- safety_concerns: array of concerns
"""
        
        response = await self.anthropic.messages.create(
            model="claude-3-opus-20240229",
            messages=[
                {"role": "system", "content": "You are an intent analyzer for an AI assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        
        try:
            intent_data = json.loads(response.content[0].text)
        except:
            intent_data = {
                "intent": "chat",
                "actions": [],
                "requires_confirmation": False,
                "safety_concerns": []
            }
        
        return intent_data
    
    async def _execute_action(
        self,
        session: AssistantSession,
        action: Dict[str, Any]
    ) -> AssistantAction:
        """Execute a single action."""
        action_type = ActionType(action.get("type", "unknown"))
        
        # Check safety
        if not await self.safety_checker.is_safe(action):
            return AssistantAction(
                type=action_type,
                status="blocked",
                details={"reason": "Safety check failed"},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Check if confirmation required
        if action.get("requires_confirmation"):
            # Store pending action and return
            pending_id = await self._store_pending_action(session, action)
            return AssistantAction(
                type=action_type,
                status="pending_confirmation",
                details={"pending_id": pending_id},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Execute based on type
        try:
            if action_type == ActionType.FILE_READ:
                result = await self.file_ops.read_file(action["path"])
            elif action_type == ActionType.FILE_WRITE:
                result = await self.file_ops.write_file(
                    action["path"],
                    action["content"]
                )
            elif action_type == ActionType.FILE_DELETE:
                result = await self.file_ops.delete_file(action["path"])
            elif action_type == ActionType.COMMAND_EXECUTE:
                result = await self.command_executor.execute(
                    action["command"],
                    action.get("args", [])
                )
            elif action_type == ActionType.TASK_CREATE:
                result = await self.task_manager.create_task(action["task"])
            elif action_type == ActionType.WORKFLOW_RUN:
                result = await self.workflow_engine.run_workflow(
                    action["workflow_id"],
                    action.get("params", {})
                )
            elif action_type == ActionType.AI_QUERY:
                result = await self.ai_orchestrator.query(
                    action["query"],
                    action.get("model", "gpt-4")
                )
            else:
                result = {"error": f"Unknown action type: {action_type}"}
            
            # Log action
            await self.audit_logger.log_action(
                user_id=session.user_id,
                action=action_type.value,
                details={
                    "session_id": session.id,
                    "action": action,
                    "result": result
                }
            )
            
            return AssistantAction(
                type=action_type,
                status="completed",
                result=result,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return AssistantAction(
                type=action_type,
                status="failed",
                error=str(e),
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _generate_response(
        self,
        session: AssistantSession,
        intent: Dict[str, Any],
        actions: List[AssistantAction]
    ) -> Dict[str, Any]:
        """Generate assistant response based on intent and actions."""
        # Build context
        action_summary = "\n".join([
            f"- {action.type.value}: {action.status}"
            for action in actions
        ])
        
        # Get relevant knowledge
        knowledge = await self.knowledge_base.search(
            intent.get("intent", ""),
            limit=5
        )
        
        # Generate response using GPT-4
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
Based on this context, generate a helpful response:

User Intent: {intent.get('intent')}
Actions Taken:
{action_summary}

Relevant Knowledge:
{json.dumps(knowledge, indent=2)}

Recent Conversation:
{self._format_recent_messages(session.messages[-5:])}

Generate a response that:
1. Acknowledges what was done
2. Provides any relevant information
3. Suggests next steps if applicable
4. Is friendly and professional
"""}
        ]
        
        response = await self.openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=0.7,
            stream=False
        )
        
        content = response.choices[0].message.content
        
        # Extract any suggestions
        suggestions = await self._extract_suggestions(content, intent)
        
        return {
            "content": content,
            "suggestions": suggestions,
            "metadata": {
                "intent": intent.get("intent"),
                "actions_count": len(actions),
                "model": "gpt-4-turbo-preview"
            }
        }
    
    async def stream_response(
        self,
        session_id: str,
        message: str
    ) -> AsyncGenerator[str, None]:
        """Stream a response for real-time interaction."""
        session = self.sessions.get(session_id)
        if not session:
            yield json.dumps({"error": "Invalid session"})
            return
        
        # Analyze intent
        intent = await self._analyze_intent(message, session)
        
        # Stream the response
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message}
        ]
        
        stream = await self.openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=0.7,
            stream=True
        )
        
        full_response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield json.dumps({"content": content})
        
        # Store the complete message
        assistant_msg = AssistantMessage(
            role="assistant",
            content=full_response,
            timestamp=datetime.now(timezone.utc)
        )
        session.messages.append(assistant_msg)
        await self.memory.store_message(session_id, assistant_msg)
    
    async def confirm_action(
        self,
        session_id: str,
        pending_id: str,
        confirmed: bool
    ) -> Dict[str, Any]:
        """Confirm or reject a pending action."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Invalid session: {session_id}")
        
        # Get pending action
        pending_action = await self._get_pending_action(pending_id)
        if not pending_action:
            raise ValueError(f"Invalid pending action: {pending_id}")
        
        if confirmed:
            # Execute the action
            result = await self._execute_action(session, pending_action)
            
            # Generate confirmation response
            response = f"Action executed: {result.type.value} - Status: {result.status}"
            if result.error:
                response += f"\nError: {result.error}"
            
            return {
                "confirmed": True,
                "action": result,
                "response": response
            }
        else:
            # Action rejected
            await self.audit_logger.log_action(
                user_id=session.user_id,
                action="action_rejected",
                details={"pending_id": pending_id, "action": pending_action}
            )
            
            return {
                "confirmed": False,
                "response": "Action cancelled as requested."
            }
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[AssistantMessage]:
        """Get session message history."""
        session = self.sessions.get(session_id)
        if session:
            return session.messages[-limit:]
        
        # Load from memory if not in cache
        return await self.memory.get_session_messages(session_id, limit)
    
    async def search_history(
        self,
        user_id: int,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search through user's conversation history."""
        return await self.memory.search_messages(user_id, query, limit)
    
    async def export_session(
        self,
        session_id: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export session data."""
        session = self.sessions.get(session_id)
        if not session:
            session = await self.memory.load_session(session_id)
        
        if format == "json":
            return {
                "session_id": session.id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "actions": [
                            {
                                "type": action.type.value,
                                "status": action.status,
                                "timestamp": action.timestamp.isoformat()
                            }
                            for action in (msg.actions or [])
                        ]
                    }
                    for msg in session.messages
                ]
            }
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def shutdown(self):
        """Shutdown the assistant service."""
        # Save all active sessions
        for session_id, session in self.sessions.items():
            await self.memory.save_session(session)
        
        # Shutdown services
        await self.task_manager.shutdown()
        await self.workflow_engine.shutdown()
        
        logger.info("Assistant service shutdown complete")
    
    # Helper methods
    def _format_recent_messages(self, messages: List[AssistantMessage]) -> str:
        """Format recent messages for context."""
        return "\n".join([
            f"{msg.role}: {msg.content[:200]}..."
            if len(msg.content) > 200 else f"{msg.role}: {msg.content}"
            for msg in messages
        ])
    
    async def _extract_suggestions(
        self,
        response: str,
        intent: Dict[str, Any]
    ) -> List[str]:
        """Extract actionable suggestions from response."""
        # Simple extraction for now
        suggestions = []
        
        if "next" in response.lower():
            suggestions.append("Review next steps")
        
        if "task" in intent.get("intent", "").lower():
            suggestions.append("View all tasks")
            suggestions.append("Create new task")
        
        if "file" in intent.get("intent", "").lower():
            suggestions.append("Browse files")
            suggestions.append("Search documents")
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    async def _store_pending_action(
        self,
        session: AssistantSession,
        action: Dict[str, Any]
    ) -> str:
        """Store a pending action awaiting confirmation."""
        pending_id = str(uuid.uuid4())
        await self.memory.store_pending_action(
            session.id,
            pending_id,
            action
        )
        return pending_id
    
    async def _get_pending_action(self, pending_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a pending action."""
        return await self.memory.get_pending_action(pending_id)