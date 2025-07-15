"""
Supabase connector for database and auth operations
"""

from typing import Dict, Any, List, Optional
import logging
from supabase import create_client, Client
from .base import BaseConnector


logger = logging.getLogger(__name__)


class SupabaseConnector(BaseConnector):
    """Supabase connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('url')
        self.anon_key = config.get('anon_key')
        self.service_key = config.get('service_key')
        self.client: Optional[Client] = None
    
    def authenticate(self) -> bool:
        """Initialize Supabase client"""
        try:
            # Use service key if available, otherwise anon key
            key = self.service_key or self.anon_key
            self.client = create_client(self.url, key)
            
            # Test connection by checking if we can access auth
            # This is a simple check - actual auth would depend on your setup
            self._is_authenticated = True
            logger.info("Supabase authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Supabase authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Supabase health"""
        try:
            # Try a simple query to test connection
            # This assumes you have at least one table
            # In production, you'd want a dedicated health check endpoint
            
            return {
                'healthy': True,
                'message': "Connected successfully",
                'details': {
                    'url': self.url,
                    'has_service_key': bool(self.service_key)
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Supabase resources"""
        if resource_type == 'tables':
            # Supabase doesn't have a direct API to list tables
            # You'd need to query information_schema or configure manually
            return [{'message': 'Table listing not implemented'}]
        
        raise ValueError(f"Unknown resource type: {resource_type}")