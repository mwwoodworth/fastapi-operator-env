"""
Vercel connector for deployment management
"""

import requests
from typing import Dict, Any, List, Optional
import logging
from .base import BaseConnector


logger = logging.getLogger(__name__)


class VercelConnector(BaseConnector):
    """Vercel API connector"""
    
    BASE_URL = "https://api.vercel.com"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config.get('token')
        self.team_id = config.get('team_id')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def authenticate(self) -> bool:
        """Test Vercel API token"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/v2/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_authenticated = True
                logger.info("Vercel authentication successful")
                return True
            else:
                logger.error(f"Vercel authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Vercel authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Vercel API health"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/v2/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user = response.json()
                
                return {
                    'healthy': True,
                    'message': f"Connected as {user.get('email', 'unknown')}",
                    'details': {
                        'user_id': user.get('uid'),
                        'team_id': self.team_id
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
        """List Vercel resources"""
        if resource_type == 'projects':
            return self.list_projects()
        elif resource_type == 'deployments':
            return self.list_deployments()
        
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List Vercel projects"""
        try:
            params = {}
            if self.team_id:
                params['teamId'] = self.team_id
            
            response = requests.get(
                f"{self.BASE_URL}/v9/projects",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                projects = []
                
                for project in data.get('projects', []):
                    projects.append({
                        'id': project['id'],
                        'name': project['name'],
                        'framework': project.get('framework'),
                        'created_at': project['createdAt'],
                        'updated_at': project['updatedAt']
                    })
                
                return projects
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def list_deployments(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Vercel deployments"""
        try:
            params = {}
            if self.team_id:
                params['teamId'] = self.team_id
            if project_id:
                params['projectId'] = project_id
            
            response = requests.get(
                f"{self.BASE_URL}/v6/deployments",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                deployments = []
                
                for deployment in data.get('deployments', []):
                    deployments.append({
                        'id': deployment['uid'],
                        'name': deployment['name'],
                        'state': deployment['state'],
                        'url': deployment.get('url'),
                        'created_at': deployment['createdAt']
                    })
                
                return deployments
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error listing deployments: {e}")
            return []
    
    def deploy(self, app_name: str, branch: str = 'main') -> Dict[str, Any]:
        """Trigger deployment for a project"""
        try:
            # Vercel deployments are typically triggered by git push
            # or through webhook. This is a simplified implementation.
            
            # In practice, you'd need to trigger a webhook or use
            # their deployment API which requires more setup
            
            return {
                'success': False,
                'error': 'Vercel deployment triggering not implemented - use git push or webhooks'
            }
            
        except Exception as e:
            logger.error(f"Error triggering deployment: {e}")
            return {
                'success': False,
                'error': str(e)
            }