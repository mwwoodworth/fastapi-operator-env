"""
ClickUp Integration

Handles webhook processing and API interactions with ClickUp
for task synchronization and project management workflows.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import aiohttp
import asyncio
from enum import Enum

from ..core.settings import get_settings
from ..core.logging import get_logger
from ..memory.memory_store import MemoryStore
from ..memory.models import MemoryType

logger = get_logger(__name__)


class ClickUpStatus(str, Enum):
    """Standard ClickUp task statuses."""
    OPEN = "open"
    IN_PROGRESS = "in progress"
    REVIEW = "review"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ClickUpPriority(int, Enum):
    """ClickUp priority levels."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class ClickUpClient:
    """
    Client for interacting with ClickUp API v2.
    Handles task creation, updates, and webhook processing.
    """
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.CLICKUP_API_KEY
        self.workspace_id = settings.CLICKUP_WORKSPACE_ID
        self.base_url = "https://api.clickup.com/api/v2"
        self.memory = MemoryStore()
        
        # Default configurations
        self.default_list_id = settings.CLICKUP_DEFAULT_LIST_ID
        self.estimate_list_id = settings.CLICKUP_ESTIMATE_LIST_ID or self.default_list_id
        
        # Headers for API requests
        self.headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def create_task(
        self,
        name: str,
        description: str,
        list_id: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        priority: ClickUpPriority = ClickUpPriority.NORMAL,
        due_date: Optional[datetime] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Create a new task in ClickUp.
        
        Args:
            name: Task name
            description: Task description (supports markdown)
            list_id: ClickUp list ID (uses default if not provided)
            assignees: List of assignee user IDs
            tags: Task tags
            priority: Task priority level
            due_date: Due date for the task
            custom_fields: Custom field values
            
        Returns:
            Created task ID
        """
        
        # Build task data
        task_data = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "priority": priority.value,
            "notify_all": True
        }
        
        # Add optional fields
        if assignees:
            task_data["assignees"] = assignees
            
        if due_date:
            # Convert to Unix timestamp (milliseconds)
            task_data["due_date"] = int(due_date.timestamp() * 1000)
            
        if custom_fields:
            task_data["custom_fields"] = self._format_custom_fields(custom_fields)
        
        # Add any additional kwargs
        task_data.update(kwargs)
        
        # Determine list ID
        target_list = list_id or self.default_list_id
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/list/{target_list}/task",
                    headers=self.headers,
                    json=task_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        task_id = result["id"]
                        
                        logger.info(f"Created ClickUp task: {task_id} - {name}")
                        
                        # Store in memory for tracking
                        await self._store_task_creation(task_id, name, task_data)
                        
                        return task_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create ClickUp task: {error_text}")
                        raise Exception(f"ClickUp API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Error creating ClickUp task: {str(e)}")
            raise
    
    async def update_task(
        self,
        task_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing ClickUp task.
        
        Args:
            task_id: ClickUp task ID
            updates: Dictionary of fields to update
            
        Returns:
            Success status
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"{self.base_url}/task/{task_id}",
                    headers=self.headers,
                    json=updates
                ) as response:
                    if response.status == 200:
                        logger.info(f"Updated ClickUp task: {task_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to update task {task_id}: {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error updating ClickUp task: {str(e)}")
            return False
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task details from ClickUp.
        
        Args:
            task_id: ClickUp task ID
            
        Returns:
            Task data or None if not found
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/task/{task_id}",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to get task {task_id}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting ClickUp task: {str(e)}")
            return None
    
    async def create_estimate_task(
        self,
        project_name: str,
        estimate_id: str,
        due_date: Optional[datetime] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a specialized task for roofing estimates.
        
        Args:
            project_name: Name of the roofing project
            estimate_id: BrainOps estimate ID
            due_date: Proposal due date
            custom_data: Additional estimate data
            
        Returns:
            Created task ID
        """
        
        # Build description with estimate details
        description = f"""## Roofing Estimate: {project_name}

**Estimate ID:** {estimate_id}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d')}

### Project Details
"""
        
        if custom_data:
            for key, value in custom_data.items():
                description += f"- **{key.replace('_', ' ').title()}:** {value}\n"
        
        description += f"\n[View Full Estimate](https://brainops.app/estimates/{estimate_id})"
        
        # Set default due date if not provided
        if not due_date:
            due_date = datetime.utcnow() + timedelta(days=7)
        
        # Create task with estimate tag
        return await self.create_task(
            name=f"Estimate: {project_name}",
            description=description,
            list_id=self.estimate_list_id,
            tags=["estimate", "roofing"],
            priority=ClickUpPriority.HIGH,
            due_date=due_date,
            custom_fields=custom_data
        )
    
    async def handle_webhook(
        self,
        event_type: str,
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process incoming ClickUp webhooks.
        
        Args:
            event_type: Type of webhook event
            task_data: Task data from webhook
            
        Returns:
            Processing result
        """
        
        logger.info(f"Processing ClickUp webhook: {event_type}")
        
        # Extract task information
        task_id = task_data.get("id")
        task_name = task_data.get("name")
        
        # Route based on event type
        if event_type == "taskCreated":
            return await self._handle_task_created(task_data)
            
        elif event_type == "taskUpdated":
            return await self._handle_task_updated(task_data)
            
        elif event_type == "taskDeleted":
            return await self._handle_task_deleted(task_data)
            
        elif event_type == "taskCommentPosted":
            return await self._handle_comment_posted(task_data)
            
        else:
            logger.warning(f"Unhandled webhook event type: {event_type}")
            return {"status": "ignored", "event_type": event_type}
    
    async def sync_task_to_brainops(
        self,
        task_id: str,
        create_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Sync a ClickUp task to BrainOps system.
        
        Args:
            task_id: ClickUp task ID
            create_memory: Whether to create memory record
            
        Returns:
            Sync result
        """
        
        # Get task details
        task = await self.get_task(task_id)
        if not task:
            return {"status": "error", "error": "Task not found"}
        
        # Extract relevant information
        task_info = {
            "clickup_id": task_id,
            "name": task.get("name"),
            "description": task.get("description"),
            "status": task.get("status", {}).get("status"),
            "priority": task.get("priority"),
            "due_date": task.get("due_date"),
            "assignees": [a.get("username") for a in task.get("assignees", [])],
            "tags": [t.get("name") for t in task.get("tags", [])],
            "custom_fields": task.get("custom_fields", [])
        }
        
        # Store in memory if requested
        if create_memory:
            await self.memory.store_memory(
                type=MemoryType.TASK_EXECUTION,
                title=f"ClickUp Task: {task_info['name']}",
                content=task_info["description"] or "",
                context={
                    "source": "clickup",
                    "task_data": task_info,
                    "sync_time": datetime.utcnow().isoformat()
                },
                tags=["clickup", "task"] + task_info["tags"]
            )
        
        return {
            "status": "success",
            "task_info": task_info,
            "synced_at": datetime.utcnow().isoformat()
        }
    
    # Private helper methods
    
    def _format_custom_fields(self, fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format custom fields for ClickUp API."""
        
        formatted = []
        
        for field_id, value in fields.items():
            # ClickUp expects specific format for custom fields
            formatted.append({
                "id": field_id,
                "value": value
            })
        
        return formatted
    
    async def _store_task_creation(
        self,
        task_id: str,
        task_name: str,
        task_data: Dict[str, Any]
    ):
        """Store task creation event in memory."""
        
        await self.memory.store_memory(
            type=MemoryType.INTEGRATION_EVENT,
            title=f"Created ClickUp Task: {task_name}",
            content=f"Task ID: {task_id}",
            context={
                "integration": "clickup",
                "event_type": "task_created",
                "task_id": task_id,
                "task_data": task_data
            },
            tags=["clickup", "task_creation", task_id]
        )
    
    async def _handle_task_created(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task created webhook event."""
        
        task_id = task_data.get("id")
        task_name = task_data.get("name", "Unknown")
        
        # Check if task needs BrainOps processing
        tags = [t.get("name") for t in task_data.get("tags", [])]
        
        if "brainops" in tags or "automation" in tags:
            # Trigger automation workflow
            logger.info(f"Task {task_id} tagged for automation")
            
            # This would trigger appropriate BrainOps workflows
            # For example, generate documentation or estimates
            
        return {
            "status": "processed",
            "event_type": "taskCreated",
            "task_id": task_id
        }
    
    async def _handle_task_updated(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task updated webhook event."""
        
        task_id = task_data.get("id")
        
        # Check what changed
        history_items = task_data.get("history_items", [])
        
        for item in history_items:
            field = item.get("field")
            
            if field == "status":
                old_status = item.get("before", {}).get("status")
                new_status = item.get("after", {}).get("status")
                
                logger.info(f"Task {task_id} status changed: {old_status} -> {new_status}")
                
                # Handle status-specific logic
                if new_status == "closed":
                    # Task completed - trigger any follow-up actions
                    pass
        
        return {
            "status": "processed",
            "event_type": "taskUpdated",
            "task_id": task_id
        }
    
    async def _handle_task_deleted(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task deleted webhook event."""
        
        task_id = task_data.get("id")
        
        # Clean up any related data
        logger.info(f"Task {task_id} deleted from ClickUp")
        
        return {
            "status": "processed",
            "event_type": "taskDeleted",
            "task_id": task_id
        }
    
    async def _handle_comment_posted(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle comment posted webhook event."""
        
        task_id = task_data.get("id")
        comment = task_data.get("comment", {})
        comment_text = comment.get("text_content", "")
        
        # Check for automation triggers in comments
        if "@brainops" in comment_text.lower():
            # Parse command from comment
            logger.info(f"BrainOps mentioned in task {task_id} comment")
            
            # This would trigger appropriate actions based on comment content
        
        return {
            "status": "processed",
            "event_type": "taskCommentPosted",
            "task_id": task_id
        }
    
    async def get_lists(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all lists in a workspace or folder.
        
        Args:
            folder_id: Optional folder ID to filter lists
            
        Returns:
            List of ClickUp lists
        """
        
        try:
            url = f"{self.base_url}/folder/{folder_id}/list" if folder_id else f"{self.base_url}/team/{self.workspace_id}/list"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("lists", [])
                    else:
                        logger.error(f"Failed to get lists: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error getting ClickUp lists: {str(e)}")
            return []
    
    async def create_webhook(
        self,
        endpoint_url: str,
        events: List[str],
        list_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a webhook subscription in ClickUp.
        
        Args:
            endpoint_url: URL to receive webhook events
            events: List of event types to subscribe to
            list_id: Optional list ID to filter events
            
        Returns:
            Webhook ID if successful
        """
        
        webhook_data = {
            "endpoint": endpoint_url,
            "events": events
        }
        
        if list_id:
            webhook_data["list_id"] = list_id
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/team/{self.workspace_id}/webhook",
                    headers=self.headers,
                    json=webhook_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        webhook_id = result.get("id")
                        logger.info(f"Created ClickUp webhook: {webhook_id}")
                        return webhook_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create webhook: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error creating ClickUp webhook: {str(e)}")
            return None