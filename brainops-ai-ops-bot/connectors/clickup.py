"""
ClickUp connector for task management integration
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from .base import BaseConnector


logger = logging.getLogger(__name__)


class ClickUpConnector(BaseConnector):
    """ClickUp API connector"""
    
    BASE_URL = "https://api.clickup.com/api/v2"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_token = config.get('api_token')
        self.workspace_id = config.get('workspace_id')
        self.folder_ids = config.get('folder_ids', {})
        self.headers = {
            'Authorization': self.api_token,
            'Content-Type': 'application/json'
        }
    
    def authenticate(self) -> bool:
        """Verify ClickUp API token"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_authenticated = True
                logger.info("ClickUp authentication successful")
                return True
            else:
                logger.error(f"ClickUp authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"ClickUp authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check ClickUp API health"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/team",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                teams = response.json().get('teams', [])
                return {
                    'healthy': True,
                    'message': f"Connected to {len(teams)} team(s)",
                    'details': {
                        'teams_count': len(teams),
                        'workspace_id': self.workspace_id
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': f"API returned status {response.status_code}"
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List ClickUp resources"""
        if resource_type == 'tasks':
            return self.list_tasks()
        elif resource_type == 'lists':
            return self.list_lists()
        elif resource_type == 'folders':
            return self.list_folders()
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_tasks(self, list_id: Optional[str] = None, 
                  status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tasks from ClickUp"""
        try:
            params = {}
            if status:
                params['statuses[]'] = status
            
            # If no list_id provided, get tasks from workspace
            if not list_id:
                url = f"{self.BASE_URL}/team/{self.workspace_id}/task"
            else:
                url = f"{self.BASE_URL}/list/{list_id}/task"
            
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                tasks = response.json().get('tasks', [])
                return [
                    {
                        'id': task['id'],
                        'name': task['name'],
                        'status': task['status']['status'],
                        'priority': task.get('priority', {}).get('priority', 'none'),
                        'due_date': task.get('due_date'),
                        'assignees': [a['username'] for a in task.get('assignees', [])]
                    }
                    for task in tasks
                ]
            else:
                logger.error(f"Failed to list tasks: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return []
    
    def list_lists(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List ClickUp lists"""
        try:
            if folder_id:
                url = f"{self.BASE_URL}/folder/{folder_id}/list"
            else:
                # Get lists from workspace
                url = f"{self.BASE_URL}/team/{self.workspace_id}/list"
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                lists = response.json().get('lists', [])
                return [
                    {
                        'id': lst['id'],
                        'name': lst['name'],
                        'task_count': lst.get('task_count', 0),
                        'status': lst.get('status', {})
                    }
                    for lst in lists
                ]
            else:
                logger.error(f"Failed to list lists: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing lists: {e}")
            return []
    
    def list_folders(self) -> List[Dict[str, Any]]:
        """List ClickUp folders"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/team/{self.workspace_id}/folder",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                folders = response.json().get('folders', [])
                return [
                    {
                        'id': folder['id'],
                        'name': folder['name'],
                        'list_count': len(folder.get('lists', [])),
                        'space': folder.get('space', {}).get('name')
                    }
                    for folder in folders
                ]
            else:
                logger.error(f"Failed to list folders: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []
    
    def create_resource(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a ClickUp resource"""
        if resource_type == 'task':
            return self.create_task(data)
        else:
            raise ValueError(f"Cannot create resource type: {resource_type}")
    
    def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task"""
        try:
            list_id = task_data.pop('list_id')
            
            response = requests.post(
                f"{self.BASE_URL}/list/{list_id}/task",
                headers=self.headers,
                json=task_data,
                timeout=10
            )
            
            if response.status_code == 200:
                task = response.json()
                return {
                    'success': True,
                    'task_id': task['id'],
                    'url': task['url']
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to create task: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_resource(self, resource_type: str, resource_id: str, 
                       data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a ClickUp resource"""
        if resource_type == 'task':
            return self.update_task(resource_id, data)
        else:
            raise ValueError(f"Cannot update resource type: {resource_type}")
    
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing task"""
        try:
            response = requests.put(
                f"{self.BASE_URL}/task/{task_id}",
                headers=self.headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'task_id': task_id
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to update task: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_task_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get comments for a task"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/task/{task_id}/comment",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                comments = response.json().get('comments', [])
                return [
                    {
                        'id': comment['id'],
                        'text': comment['comment_text'],
                        'user': comment['user']['username'],
                        'date': comment['date']
                    }
                    for comment in comments
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting comments: {e}")
            return []
    
    def add_comment(self, task_id: str, comment_text: str) -> bool:
        """Add a comment to a task"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/task/{task_id}/comment",
                headers=self.headers,
                json={'comment_text': comment_text},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False