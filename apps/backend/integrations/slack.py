"""
Slack Integration

Handles Slack slash commands, event handling, and workflow approvals
for the BrainOps operator system. Enables human-in-the-loop patterns.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import json
import hmac
import hashlib
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier

from apps.backend.core.settings import settings
from ..core.logging import get_logger
from ..memory.memory_store import MemoryStore
from ..tasks import get_task_registry

logger = get_logger(__name__)


class SlackIntegration:
    """
    Manages Slack integration for BrainOps operator workflows.
    Handles commands, approvals, and notifications.
    """
    
    def __init__(self):
        self.client = AsyncWebClient(token=settings.SLACK_BOT_TOKEN)
        self.signature_verifier = SignatureVerifier(settings.SLACK_SIGNING_SECRET)
        self.memory = MemoryStore()
        
        # Approval tracking
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        
        # Channel configuration
        self.default_channel = settings.SLACK_DEFAULT_CHANNEL
        self.approval_channel = settings.SLACK_APPROVAL_CHANNEL or self.default_channel
    
    async def verify_request(self, body: str, headers: Dict[str, str]) -> bool:
        """
        Verify that the request came from Slack.
        
        Args:
            body: Request body as string
            headers: Request headers
            
        Returns:
            True if request is valid
        """
        
        timestamp = headers.get("X-Slack-Request-Timestamp", "")
        signature = headers.get("X-Slack-Signature", "")
        
        return self.signature_verifier.is_valid_request(body, timestamp, signature)
    
    async def handle_slash_command(
        self,
        command: str,
        text: str,
        user_id: str,
        channel_id: str,
        response_url: str
    ) -> Dict[str, Any]:
        """
        Handle incoming slash commands from Slack.
        
        Args:
            command: Slash command (e.g., /brainops)
            text: Command text
            user_id: Slack user ID
            channel_id: Slack channel ID
            response_url: URL for delayed responses
            
        Returns:
            Immediate response to Slack
        """
        
        logger.info(f"Received slash command: {command} '{text}' from {user_id}")
        
        # Parse command and arguments
        parts = text.strip().split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1] if len(parts) > 1 else ""
        
        # Route to appropriate handler
        if subcommand == "help":
            return await self._handle_help_command()
            
        elif subcommand == "task":
            return await self._handle_task_command(args, user_id, channel_id, response_url)
            
        elif subcommand == "status":
            return await self._handle_status_command(args, user_id)
            
        elif subcommand == "search":
            return await self._handle_search_command(args, user_id, channel_id)
            
        elif subcommand == "approve":
            return await self._handle_approve_command(args, user_id)
            
        else:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: `{subcommand}`. Try `/brainops help`"
            }
    
    async def handle_interactive_action(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle interactive components (buttons, select menus).
        
        Args:
            payload: Slack interactive payload
            
        Returns:
            Response to update the message
        """
        
        action_type = payload.get("type")
        
        if action_type == "block_actions":
            # Handle button clicks
            actions = payload.get("actions", [])
            if actions:
                action = actions[0]
                action_id = action.get("action_id")
                value = action.get("value")
                
                if action_id.startswith("approve_"):
                    return await self._handle_approval_action(
                        approval_id=value,
                        approved=True,
                        user=payload.get("user", {})
                    )
                    
                elif action_id.startswith("reject_"):
                    return await self._handle_approval_action(
                        approval_id=value,
                        approved=False,
                        user=payload.get("user", {})
                    )
        
        return {"text": "Action received"}
    
    async def send_approval_request(
        self,
        task_id: str,
        task_type: str,
        description: str,
        details: Dict[str, Any],
        requester: Optional[str] = None
    ) -> str:
        """
        Send an approval request to Slack.
        
        Args:
            task_id: Task identifier
            task_type: Type of task requiring approval
            description: Human-readable description
            details: Additional details for decision-making
            requester: User who initiated the task
            
        Returns:
            Approval ID for tracking
        """
        
        approval_id = f"approval_{task_id}_{datetime.utcnow().timestamp()}"
        
        # Store pending approval
        self.pending_approvals[approval_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "description": description,
            "details": details,
            "requester": requester,
            "created_at": datetime.utcnow(),
            "status": "pending"
        }
        
        # Build approval message blocks
        blocks = self._build_approval_blocks(
            approval_id=approval_id,
            task_type=task_type,
            description=description,
            details=details,
            requester=requester
        )
        
        try:
            # Send to approval channel
            result = await self.client.chat_postMessage(
                channel=self.approval_channel,
                text=f"Approval needed for: {description}",
                blocks=blocks
            )
            
            # Store message timestamp for updates
            self.pending_approvals[approval_id]["message_ts"] = result["ts"]
            
            logger.info(f"Sent approval request: {approval_id}")
            
            return approval_id
            
        except SlackApiError as e:
            logger.error(f"Failed to send approval request: {e}")
            raise
    
    async def send_notification(
        self,
        channel: str,
        message: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ) -> bool:
        """
        Send a notification to a Slack channel.
        
        Args:
            channel: Channel ID or name
            message: Plain text message
            blocks: Optional rich message blocks
            thread_ts: Optional thread timestamp for replies
            
        Returns:
            Success status
        """
        
        try:
            await self.client.chat_postMessage(
                channel=channel or self.default_channel,
                text=message,
                blocks=blocks,
                thread_ts=thread_ts
            )
            return True
            
        except SlackApiError as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    # Private handler methods
    
    async def _handle_help_command(self) -> Dict[str, Any]:
        """Handle the help command."""
        
        help_text = """
*BrainOps Operator Commands:*

• `/brainops task <task_type> [parameters]` - Run a task
• `/brainops status <task_id>` - Check task status
• `/brainops search <query>` - Search knowledge base
• `/brainops approve <approval_id>` - Approve a pending request
• `/brainops help` - Show this help message

*Available Tasks:*
• `generate_product_docs` - Generate product documentation
• `generate_roof_estimate` - Create roofing estimate
• `autopublish_content` - Auto-publish content

*Example:*
`/brainops task generate_estimate project:"Office Building" area:15000`
        """
        
        return {
            "response_type": "ephemeral",
            "text": help_text
        }
    
    async def _handle_task_command(
        self,
        args: str,
        user_id: str,
        channel_id: str,
        response_url: str
    ) -> Dict[str, Any]:
        """Handle task execution command."""
        
        # Parse task type and parameters
        parts = args.split(maxsplit=1)
        if not parts:
            return {
                "response_type": "ephemeral",
                "text": "Please specify a task type. Example: `/brainops task generate_estimate`"
            }
        
        task_type = parts[0]
        params_str = parts[1] if len(parts) > 1 else ""
        
        # Parse parameters (simple key:value format)
        params = self._parse_task_parameters(params_str)
        
        # Get task registry
        task_registry = get_task_registry()
        
        if task_type not in task_registry:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown task type: `{task_type}`. Available tasks: {', '.join(task_registry.keys())}"
            }
        
        # Start task execution asynchronously
        asyncio.create_task(
            self._execute_task_async(
                task_type=task_type,
                params=params,
                user_id=user_id,
                channel_id=channel_id,
                response_url=response_url
            )
        )
        
        return {
            "response_type": "ephemeral",
            "text": f"Starting task: `{task_type}`... I'll notify you when complete."
        }
    
    async def _handle_status_command(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """Handle status check command."""
        
        if not task_id:
            return {
                "response_type": "ephemeral",
                "text": "Please provide a task ID. Example: `/brainops status task_123`"
            }
        
        # Query task status from memory
        # This would be implemented with actual task tracking
        
        return {
            "response_type": "ephemeral",
            "text": f"Task `{task_id}` status: In Progress (mock response)"
        }
    
    async def _handle_search_command(
        self,
        query: str,
        user_id: str,
        channel_id: str
    ) -> Dict[str, Any]:
        """Handle knowledge search command."""
        
        if not query:
            return {
                "response_type": "ephemeral",
                "text": "Please provide a search query. Example: `/brainops search TPO roofing specs`"
            }
        
        # Search knowledge base
        from ..memory.models import MemorySearchQuery
        
        search_query = MemorySearchQuery(
            query=query,
            max_results=5,
            min_relevance_score=0.7
        )
        
        results = await self.memory.search_memories(search_query)
        
        if not results:
            return {
                "response_type": "ephemeral",
                "text": f"No results found for: `{query}`"
            }
        
        # Format results
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Search Results for:* `{query}`"
                }
            },
            {"type": "divider"}
        ]
        
        for result in results[:3]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{result.title}*\n{result.summary}"
                }
            })
        
        return {
            "response_type": "ephemeral",
            "blocks": blocks
        }
    
    async def _handle_approve_command(self, approval_id: str, user_id: str) -> Dict[str, Any]:
        """Handle direct approval command."""
        
        if not approval_id:
            return {
                "response_type": "ephemeral",
                "text": "Please provide an approval ID. Example: `/brainops approve approval_123`"
            }
        
        if approval_id not in self.pending_approvals:
            return {
                "response_type": "ephemeral",
                "text": f"Approval `{approval_id}` not found or already processed."
            }
        
        # Process approval
        await self._handle_approval_action(
            approval_id=approval_id,
            approved=True,
            user={"id": user_id}
        )
        
        return {
            "response_type": "ephemeral",
            "text": f"Approved: `{approval_id}`"
        }
    
    async def _handle_approval_action(
        self,
        approval_id: str,
        approved: bool,
        user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process approval or rejection action."""
        
        if approval_id not in self.pending_approvals:
            return {"text": "Approval not found or already processed."}
        
        approval = self.pending_approvals[approval_id]
        
        # Update approval status
        approval["status"] = "approved" if approved else "rejected"
        approval["decided_by"] = user.get("id")
        approval["decided_at"] = datetime.utcnow()
        
        # Update the original message
        action_text = "✅ Approved" if approved else "❌ Rejected"
        
        updated_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{action_text} by <@{user.get('id')}>*\n\n{approval['description']}"
                }
            }
        ]
        
        # Notify the task system
        asyncio.create_task(
            self._notify_task_decision(
                task_id=approval["task_id"],
                approved=approved,
                approval_id=approval_id
            )
        )
        
        # Remove from pending
        del self.pending_approvals[approval_id]
        
        return {
            "blocks": updated_blocks
        }
    
    # Helper methods
    
    def _parse_task_parameters(self, params_str: str) -> Dict[str, Any]:
        """Parse task parameters from string format."""
        
        params = {}
        
        # Simple key:value parsing
        # Example: project:"Office Building" area:15000
        import re
        
        pattern = r'(\w+):("([^"]*)"|(\S+))'
        matches = re.findall(pattern, params_str)
        
        for match in matches:
            key = match[0]
            value = match[2] if match[2] else match[3]
            
            # Try to convert to appropriate type
            try:
                if value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
            except:
                pass
            
            params[key] = value
        
        return params
    
    def _build_approval_blocks(
        self,
        approval_id: str,
        task_type: str,
        description: str,
        details: Dict[str, Any],
        requester: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Build Slack blocks for approval request."""
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔔 Approval Required"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Task Type:* `{task_type}`\n*Description:* {description}"
                }
            }
        ]
        
        # Add requester if provided
        if requester:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Requested by <@{requester}>"
                    }
                ]
            })
        
        # Add details section
        if details:
            detail_text = "\n".join([
                f"• *{k}:* {v}"
                for k, v in details.items()
                if k not in ["task_id", "task_type"]
            ])
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Details:*\n{detail_text}"
                }
            })
        
        # Add action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve"
                    },
                    "style": "primary",
                    "action_id": f"approve_{approval_id}",
                    "value": approval_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Reject"
                    },
                    "style": "danger",
                    "action_id": f"reject_{approval_id}",
                    "value": approval_id
                }
            ]
        })
        
        return blocks
    
    async def _execute_task_async(
        self,
        task_type: str,
        params: Dict[str, Any],
        user_id: str,
        channel_id: str,
        response_url: str
    ):
        """Execute task asynchronously and send results."""
        
        try:
            # Get task module
            task_registry = get_task_registry()
            task_module = task_registry[task_type]
            
            # Create context
            context = {
                "user_id": user_id,
                "channel_id": channel_id,
                "source": "slack"
            }
            
            # Execute task
            result = await task_module.run(context, **params)
            
            # Send result notification
            if result.get("status") == "success":
                await self.send_notification(
                    channel=channel_id,
                    message=f"✅ Task `{task_type}` completed successfully!",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Task Complete: {task_type}*\n{result.get('summary', 'Task completed')}"
                            }
                        }
                    ]
                )
            else:
                await self.send_notification(
                    channel=channel_id,
                    message=f"❌ Task `{task_type}` failed: {result.get('error', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"Task execution failed: {str(e)}")
            await self.send_notification(
                channel=channel_id,
                message=f"❌ Task `{task_type}` failed with error: {str(e)}"
            )
    
    async def _notify_task_decision(
        self,
        task_id: str,
        approved: bool,
        approval_id: str
    ):
        """Notify task system of approval decision."""
        
        # This would integrate with your task queue/workflow system
        logger.info(f"Task {task_id} {'approved' if approved else 'rejected'} via {approval_id}")
        
        # Store decision in memory
        from ..memory.models import MemoryType
        
        await self.memory.store_memory(
            type=MemoryType.INTEGRATION_EVENT,
            title=f"Slack Approval: {task_id}",
            content=f"Task {task_id} was {'approved' if approved else 'rejected'}",
            context={
                "task_id": task_id,
                "approval_id": approval_id,
                "approved": approved,
                "integration": "slack"
            },
            tags=["approval", "slack", task_id]
        )