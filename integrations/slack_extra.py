"""
Slack integration module for BrainOps.

Handles Slack slash commands, event subscriptions, and interactive components.
Built to enable seamless approval workflows and task triggers without leaving
the communication tools your team already uses.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import HTTPException, Request, Form, status
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..core.settings import settings
from ..core.logging import get_logger
from ..tasks import execute_task
from ..memory.memory_store import save_slack_interaction


logger = get_logger(__name__)


class SlackIntegrationHandler:
    """
    Comprehensive Slack integration handler.
    
    Manages secure webhook verification, command processing, and
    interactive message handling. Built to keep critical decisions
    moving without context switching.
    """
    
    def __init__(self):
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN.get_secret_value() if settings.SLACK_BOT_TOKEN else None)
        self.signing_secret = settings.SLACK_SIGNING_SECRET.get_secret_value() if settings.SLACK_SIGNING_SECRET else None
        
        if not self.signing_secret:
            logger.warning("Slack signing secret not configured - Slack integration disabled")
        
        # Map slash commands to task IDs
        self.command_mapping = {
            "/estimate": "quick_roof_estimate",
            "/approve": "process_approval",
            "/task": "create_task_from_slack",
            "/status": "check_task_status",
            "/help": "show_slack_help"
        }
    
    def verify_slack_request(self, request_body: str, timestamp: str, signature: str) -> bool:
        """
        Verify request genuinely came from Slack.
        
        Prevents unauthorized commands from triggering business-critical
        automations. Essential security layer for production systems.
        """
        if not self.signing_secret:
            return False
        
        # Check timestamp to prevent replay attacks (5 minute window)
        try:
            request_timestamp = int(timestamp)
            current_timestamp = int(time.time())
            
            if abs(current_timestamp - request_timestamp) > 300:
                logger.warning("Slack request timestamp outside acceptable window")
                return False
                
        except (ValueError, TypeError):
            return False
        
        # Verify signature
        sig_basestring = f"v0:{timestamp}:{request_body}"
        computed_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(computed_signature, signature)
    
    async def handle_slash_command(self, request: Request) -> Dict[str, Any]:
        """
        Process incoming Slack slash commands.
        
        Transforms quick Slack commands into full automation workflows,
        keeping your team productive without leaving their flow.
        """
        # Get request body and headers for verification
        body = await request.body()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        
        # Verify request authenticity
        if not self.verify_slack_request(body.decode(), timestamp, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Slack signature"
            )
        
        # Parse form data
        form_data = await request.form()
        command_data = {
            "command": form_data.get("command"),
            "text": form_data.get("text", ""),
            "user_id": form_data.get("user_id"),
            "user_name": form_data.get("user_name"),
            "channel_id": form_data.get("channel_id"),
            "team_id": form_data.get("team_id"),
            "response_url": form_data.get("response_url")
        }
        
        # Log interaction for audit trail
        await save_slack_interaction({
            "type": "slash_command",
            "command": command_data["command"],
            "user_id": command_data["user_id"],
            "channel_id": command_data["channel_id"],
            "timestamp": datetime.utcnow()
        })
        
        # Route to appropriate handler
        return await self._route_command(command_data)
    
    async def _route_command(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route slash commands to appropriate task handlers.
        
        Provides immediate acknowledgment while processing happens
        in background, preventing Slack timeouts on complex operations.
        """
        command = command_data["command"]
        
        # Get mapped task ID
        task_id = self.command_mapping.get(command)
        if not task_id:
            return {
                "response_type": "ephemeral",
                "text": f"Unknown command: {command}"
            }
        
        # Special handling for help command
        if task_id == "show_slack_help":
            return self._generate_help_response()
        
        # Parse command arguments
        args = self._parse_command_args(command_data["text"])
        
        # Build task inputs
        task_inputs = {
            "command": command,
            "args": args,
            "user_id": command_data["user_id"],
            "user_name": command_data["user_name"],
            "channel_id": command_data["channel_id"],
            "response_url": command_data["response_url"]
        }
        
        # Execute task asynchronously
        try:
            # Quick acknowledgment to Slack
            self._send_delayed_response(
                command_data["response_url"],
                {
                    "response_type": "in_channel",
                    "text": f"Processing {command} request..."
                }
            )
            
            # Execute actual task
            result = await execute_task(
                task_id=task_id,
                inputs=task_inputs,
                context={
                    "source": "slack",
                    "team_id": command_data["team_id"]
                }
            )
            
            # Send result back to Slack
            self._send_delayed_response(
                command_data["response_url"],
                result.get("slack_response", {
                    "response_type": "in_channel",
                    "text": "Task completed successfully"
                })
            )
            
            return {"response_type": "in_channel", "text": "✓ Processing..."}
            
        except Exception as e:
            logger.error(f"Slack command execution failed: {str(e)}", exc_info=True)
            
            return {
                "response_type": "ephemeral",
                "text": f"❌ Command failed: {str(e)}"
            }
    
    async def handle_interaction(self, request: Request) -> Dict[str, Any]:
        """
        Handle interactive messages (buttons, select menus, etc).
        
        Enables approval workflows and multi-step processes directly
        within Slack, keeping decisions moving at the speed of business.
        """
        # Verify and parse payload
        body = await request.body()
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        
        if not self.verify_slack_request(body.decode(), timestamp, signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Slack signature"
            )
        
        # Parse interaction payload
        form_data = await request.form()
        payload = json.loads(form_data.get("payload", "{}"))
        
        # Route based on interaction type
        interaction_type = payload.get("type")
        
        if interaction_type == "block_actions":
            return await self._handle_block_action(payload)
        elif interaction_type == "view_submission":
            return await self._handle_view_submission(payload)
        else:
            logger.warning(f"Unhandled interaction type: {interaction_type}")
            return {"response_action": "clear"}
    
    async def _handle_block_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process button clicks and menu selections.
        
        Transforms UI interactions into business actions, maintaining
        context and authorization throughout the flow.
        """
        user = payload["user"]
        actions = payload.get("actions", [])
        
        for action in actions:
            action_id = action.get("action_id", "")
            
            # Handle approval actions
            if action_id.startswith("approve_"):
                task_id = action_id.replace("approve_", "")
                await self._process_approval(task_id, user["id"], True)
                
                return {
                    "response_action": "update",
                    "text": f"✅ Approved by <@{user['id']}>"
                }
            
            elif action_id.startswith("reject_"):
                task_id = action_id.replace("reject_", "")
                await self._process_approval(task_id, user["id"], False)
                
                return {
                    "response_action": "update",
                    "text": f"❌ Rejected by <@{user['id']}>"
                }
        
        return {"response_action": "clear"}
    
    def send_message(self, channel: str, text: str, blocks: Optional[List[Dict]] = None) -> bool:
        """
        Send a message to a Slack channel.
        
        Provides reliable notification delivery for task completions,
        alerts, and status updates. Built to handle failures gracefully.
        """
        if not self.client:
            logger.warning("Slack client not configured")
            return False
        
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks
            )
            
            return response["ok"]
            
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            return False
    
    def _parse_command_args(self, text: str) -> Dict[str, Any]:
        """
        Parse slash command arguments into structured data.
        
        Handles various argument formats to make commands flexible
        and user-friendly without sacrificing reliability.
        """
        args = {}
        
        # Handle key=value pairs
        if "=" in text:
            for pair in text.split():
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    args[key] = value
        else:
            # Simple positional argument
            args["value"] = text.strip()
        
        return args
    
    def _generate_help_response(self) -> Dict[str, Any]:
        """
        Generate help message for available commands.
        
        Provides clear, actionable guidance for team members to
        leverage automation without memorizing syntax.
        """
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Available BrainOps Commands:*"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "`/estimate [description]` - Quick roof estimate\n"
                                "`/approve [task_id]` - Approve pending task\n"
                                "`/task [description]` - Create new task\n"
                                "`/status [task_id]` - Check task status"
                    }
                }
            ]
        }
    
    def _send_delayed_response(self, response_url: str, message: Dict[str, Any]) -> None:
        """
        Send delayed response to Slack webhook URL.
        
        Enables long-running operations without hitting Slack's
        3-second timeout. Essential for complex automations.
        """
        import httpx
        
        try:
            with httpx.Client() as client:
                client.post(response_url, json=message)
        except Exception as e:
            logger.error(f"Failed to send delayed Slack response: {str(e)}")
    
    async def _process_approval(self, task_id: str, user_id: str, approved: bool) -> None:
        """
        Process approval action from Slack.
        
        Maintains audit trail and triggers downstream automations
        based on approval decisions. Critical for workflow integrity.
        """
        await execute_task(
            task_id="process_approval_decision",
            inputs={
                "target_task_id": task_id,
                "approver_id": user_id,
                "approved": approved,
                "approval_source": "slack"
            },
            context={"source": "slack_interaction"}
        )


# Global handler instance
slack_handler = SlackIntegrationHandler()


# Convenience functions for routes
async def handle_slack_command(request: Request) -> Dict[str, Any]:
    """Route handler for Slack slash commands."""
    return await slack_handler.handle_slash_command(request)


async def handle_slack_interaction(request: Request) -> Dict[str, Any]:
    """Route handler for Slack interactive components."""
    return await slack_handler.handle_interaction(request)