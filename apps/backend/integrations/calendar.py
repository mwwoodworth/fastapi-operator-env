"""
Calendar integration service for task scheduling.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class CalendarIntegration:
    """Service for calendar system integration."""
    
    async def create_event(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a calendar event for a task.
        """
        # Mock implementation
        # In production, would integrate with Google Calendar, Outlook, etc.
        
        event_id = str(uuid.uuid4())
        
        return {
            "event_id": event_id,
            "calendar_type": "google",
            "status": "created",
            "url": f"https://calendar.google.com/event/{event_id}"
        }
    
    async def update_event(
        self,
        event_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.
        """
        # Mock implementation
        return {
            "event_id": event_id,
            "status": "updated",
            "changes": list(updates.keys())
        }
    
    async def delete_event(
        self,
        event_id: str
    ) -> Dict[str, Any]:
        """
        Delete a calendar event.
        """
        # Mock implementation
        return {
            "event_id": event_id,
            "status": "deleted"
        }
    
    async def get_user_events(
        self,
        user_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get user's calendar events for a date range.
        """
        # Mock implementation
        return []


class CalendarSync:
    """Service for syncing calendar events with external systems."""
    
    def __init__(self):
        self.integration = CalendarIntegration()
        self.sync_status = {}
    
    async def sync_task_to_calendar(
        self,
        task_id: str,
        user_id: str,
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sync a task to the user's calendar."""
        # Extract event details from task
        start_time = task_data.get('scheduled_start', datetime.utcnow())
        end_time = task_data.get('scheduled_end', datetime.utcnow())
        title = task_data.get('title', 'Task')
        description = task_data.get('description', '')
        
        # Create calendar event
        result = await self.integration.create_event(
            task_id=uuid.UUID(task_id),
            user_id=uuid.UUID(user_id),
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        
        # Track sync status
        self.sync_status[task_id] = {
            'synced_at': datetime.utcnow(),
            'calendar_event_id': result.get('event_id'),
            'status': 'synced'
        }
        
        return result
    
    async def remove_from_calendar(self, task_id: str) -> Dict[str, Any]:
        """Remove a task from calendar."""
        if task_id in self.sync_status:
            event_id = self.sync_status[task_id].get('calendar_event_id')
            if event_id:
                result = await self.integration.delete_event(event_id)
                del self.sync_status[task_id]
                return result
        
        return {'status': 'not_found'}
    
    async def update_calendar_event(
        self,
        task_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update calendar event for a task."""
        if task_id in self.sync_status:
            event_id = self.sync_status[task_id].get('calendar_event_id')
            if event_id:
                result = await self.integration.update_event(event_id, updates)
                self.sync_status[task_id]['last_updated'] = datetime.utcnow()
                return result
        
        return {'status': 'not_found'}
    
    def get_sync_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get sync status for a task."""
        return self.sync_status.get(task_id)


# Alias for backward compatibility
CalendarService = CalendarIntegration