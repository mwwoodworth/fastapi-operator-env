"""
Base connector class for all service integrations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
import logging
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for service connectors"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector with configuration
        
        Args:
            config: Service-specific configuration dictionary
        """
        self.config = config
        self._last_check_time = None
        self._is_authenticated = False
        self.service_name = self.__class__.__name__.replace('Connector', '').lower()
        
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the service
        
        Returns:
            bool: True if authentication successful
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the service
        
        Returns:
            dict: Health check results with keys:
                - healthy: bool
                - response_time: float (ms)
                - message: str
                - details: dict (optional)
        """
        pass
    
    def check_health(self) -> Dict[str, Any]:
        """
        Wrapper for health check with timing and error handling
        """
        start_time = time.time()
        
        try:
            if not self._is_authenticated:
                self.authenticate()
                
            result = self.health_check()
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            result['response_time'] = response_time
            result['checked_at'] = datetime.utcnow().isoformat()
            self._last_check_time = time.time()
            
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Health check failed for {self.service_name}: {e}")
            
            return {
                'healthy': False,
                'response_time': response_time,
                'message': f"Health check failed: {str(e)}",
                'error': str(e),
                'checked_at': datetime.utcnow().isoformat()
            }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute a function with automatic retry logic
        """
        return func(*args, **kwargs)
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """
        List resources of a specific type
        
        Args:
            resource_type: Type of resource to list
            
        Returns:
            List of resources
        """
        raise NotImplementedError(f"Resource listing not implemented for {self.service_name}")
    
    def get_logs(self, app_name: str, lines: int = 100) -> List[str]:
        """
        Get logs for an application
        
        Args:
            app_name: Application name
            lines: Number of log lines to retrieve
            
        Returns:
            List of log lines
        """
        raise NotImplementedError(f"Log retrieval not implemented for {self.service_name}")
    
    def stream_logs(self, app_name: str):
        """
        Stream logs for an application
        
        Args:
            app_name: Application name
            
        Yields:
            Log lines as they come in
        """
        raise NotImplementedError(f"Log streaming not implemented for {self.service_name}")
    
    def deploy(self, app_name: str, branch: str = 'main') -> Dict[str, Any]:
        """
        Trigger deployment for an application
        
        Args:
            app_name: Application name
            branch: Branch to deploy
            
        Returns:
            Deployment result
        """
        raise NotImplementedError(f"Deployment not implemented for {self.service_name}")
    
    def get_metrics(self, metric_type: str, start_time: Optional[datetime] = None, 
                   end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get metrics from the service
        
        Args:
            metric_type: Type of metrics to retrieve
            start_time: Start time for metrics
            end_time: End time for metrics
            
        Returns:
            Metrics data
        """
        raise NotImplementedError(f"Metrics retrieval not implemented for {self.service_name}")
    
    def create_resource(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new resource
        
        Args:
            resource_type: Type of resource to create
            data: Resource data
            
        Returns:
            Created resource data
        """
        raise NotImplementedError(f"Resource creation not implemented for {self.service_name}")
    
    def update_resource(self, resource_type: str, resource_id: str, 
                       data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing resource
        
        Args:
            resource_type: Type of resource to update
            resource_id: Resource identifier
            data: Updated resource data
            
        Returns:
            Updated resource data
        """
        raise NotImplementedError(f"Resource update not implemented for {self.service_name}")
    
    def delete_resource(self, resource_type: str, resource_id: str) -> bool:
        """
        Delete a resource
        
        Args:
            resource_type: Type of resource to delete
            resource_id: Resource identifier
            
        Returns:
            True if deletion successful
        """
        raise NotImplementedError(f"Resource deletion not implemented for {self.service_name}")
    
    def __repr__(self):
        return f"<{self.__class__.__name__} authenticated={self._is_authenticated}>"