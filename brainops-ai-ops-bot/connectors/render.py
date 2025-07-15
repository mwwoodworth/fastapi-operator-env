"""
Render connector for deployment and service management
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from .base import BaseConnector


logger = logging.getLogger(__name__)


class RenderConnector(BaseConnector):
    """Render API connector"""
    
    BASE_URL = "https://api.render.com/v1"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.service_ids = config.get('service_ids', {})
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def authenticate(self) -> bool:
        """Verify Render API key"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/services",
                headers=self.headers,
                params={'limit': 1},
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_authenticated = True
                logger.info("Render authentication successful")
                return True
            else:
                logger.error(f"Render authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Render authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Render API health"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/services",
                headers=self.headers,
                params={'limit': 20},
                timeout=10
            )
            
            if response.status_code == 200:
                services = response.json()
                
                # Check configured services
                service_statuses = {}
                for name, service_id in self.service_ids.items():
                    service_status = self._get_service_status(service_id)
                    if service_status:
                        service_statuses[name] = service_status
                
                return {
                    'healthy': True,
                    'message': f"Connected, monitoring {len(service_statuses)} services",
                    'details': {
                        'total_services': len(services),
                        'configured_services': len(self.service_ids),
                        'service_statuses': service_statuses
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
    
    def _get_service_status(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific service"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/services/{service_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                service = response.json()
                return {
                    'status': service.get('state'),
                    'suspended': service.get('suspended', False),
                    'url': service.get('url', ''),
                    'type': service.get('type')
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return None
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Render resources"""
        if resource_type == 'services':
            return self.list_services()
        elif resource_type == 'deployments':
            return self.list_deployments()
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_services(self) -> List[Dict[str, Any]]:
        """List all services"""
        try:
            services = []
            response = requests.get(
                f"{self.BASE_URL}/services",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                for service in response.json():
                    services.append({
                        'id': service['id'],
                        'name': service['name'],
                        'type': service['type'],
                        'state': service['state'],
                        'suspended': service.get('suspended', False),
                        'url': service.get('url', ''),
                        'created_at': service['createdAt'],
                        'updated_at': service['updatedAt']
                    })
            
            return services
            
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return []
    
    def list_deployments(self, service_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List deployments for a service"""
        try:
            deployments = []
            
            # If no service_id, get deployments for all configured services
            service_ids = [service_id] if service_id else list(self.service_ids.values())
            
            for sid in service_ids:
                response = requests.get(
                    f"{self.BASE_URL}/services/{sid}/deploys",
                    headers=self.headers,
                    params={'limit': 10},
                    timeout=10
                )
                
                if response.status_code == 200:
                    for deploy in response.json():
                        deployments.append({
                            'id': deploy['id'],
                            'service_id': sid,
                            'status': deploy['status'],
                            'trigger': deploy['trigger'],
                            'created_at': deploy['createdAt'],
                            'updated_at': deploy['updatedAt'],
                            'finished_at': deploy.get('finishedAt'),
                            'commit': deploy.get('commit', {})
                        })
            
            return deployments
            
        except Exception as e:
            logger.error(f"Error listing deployments: {e}")
            return []
    
    def deploy(self, app_name: str, branch: str = 'main') -> Dict[str, Any]:
        """Trigger a deployment"""
        try:
            # Get service ID from app name
            service_id = self.service_ids.get(app_name)
            if not service_id:
                # Try direct service ID
                service_id = app_name
            
            response = requests.post(
                f"{self.BASE_URL}/services/{service_id}/deploys",
                headers=self.headers,
                json={'clearCache': 'clear'},
                timeout=10
            )
            
            if response.status_code in [201, 200]:
                deploy = response.json()
                return {
                    'success': True,
                    'deployment_id': deploy['id'],
                    'status': deploy['status']
                }
            else:
                return {
                    'success': False,
                    'error': f"Deployment failed with status {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Error triggering deployment: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_logs(self, app_name: str, lines: int = 100) -> List[str]:
        """Get service logs"""
        try:
            # Get service ID from app name
            service_id = self.service_ids.get(app_name, app_name)
            
            response = requests.get(
                f"{self.BASE_URL}/services/{service_id}/logs",
                headers=self.headers,
                params={'tail': lines},
                timeout=10
            )
            
            if response.status_code == 200:
                logs_data = response.json()
                return [log['message'] for log in logs_data]
            else:
                return [f"Failed to get logs: status {response.status_code}"]
                
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return [f"Error getting logs: {str(e)}"]
    
    def stream_logs(self, app_name: str):
        """Stream service logs (not fully implemented - would need WebSocket)"""
        # Note: Render uses WebSocket for log streaming
        # This is a simplified version that polls
        service_id = self.service_ids.get(app_name, app_name)
        
        yield f"Streaming logs for {app_name} (service: {service_id})..."
        yield "Note: Real-time streaming requires WebSocket connection"
        
        # Get recent logs
        logs = self.get_logs(app_name, lines=50)
        for log in logs:
            yield log
    
    def get_metrics(self, metric_type: str, start_time: Optional[datetime] = None, 
                   end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get service metrics"""
        try:
            metrics = {}
            
            for service_name, service_id in self.service_ids.items():
                response = requests.get(
                    f"{self.BASE_URL}/services/{service_id}",
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    service = response.json()
                    metrics[service_name] = {
                        'state': service['state'],
                        'cpu': service.get('metrics', {}).get('cpu'),
                        'memory': service.get('metrics', {}).get('memory'),
                        'disk': service.get('metrics', {}).get('disk')
                    }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    def suspend_service(self, service_id: str) -> bool:
        """Suspend a service"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/services/{service_id}/suspend",
                headers=self.headers,
                timeout=10
            )
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Error suspending service: {e}")
            return False
    
    def resume_service(self, service_id: str) -> bool:
        """Resume a suspended service"""
        try:
            response = requests.post(
                f"{self.BASE_URL}/services/{service_id}/resume",
                headers=self.headers,
                timeout=10
            )
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Error resuming service: {e}")
            return False
    
    def scale_service(self, service_id: str, instances: int) -> bool:
        """Scale a service (if supported)"""
        try:
            response = requests.patch(
                f"{self.BASE_URL}/services/{service_id}",
                headers=self.headers,
                json={'numInstances': instances},
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error scaling service: {e}")
            return False