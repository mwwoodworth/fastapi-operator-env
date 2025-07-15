"""
Airtable connector for database operations
"""

import requests
from typing import Dict, Any, List, Optional
import logging
from .base import BaseConnector


logger = logging.getLogger(__name__)


class AirtableConnector(BaseConnector):
    """Airtable API connector"""
    
    BASE_URL = "https://api.airtable.com/v0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.base_ids = config.get('base_ids', {})
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def authenticate(self) -> bool:
        """Verify Airtable API key"""
        try:
            # Test with a simple request to list bases
            response = requests.get(
                "https://api.airtable.com/v0/meta/bases",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_authenticated = True
                logger.info("Airtable authentication successful")
                return True
            else:
                logger.error(f"Airtable authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Airtable authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Airtable API health"""
        try:
            response = requests.get(
                "https://api.airtable.com/v0/meta/bases",
                headers=self.headers,
                params={'limit': 1},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'message': "Connected successfully",
                    'details': {
                        'configured_bases': len(self.base_ids)
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
        """List Airtable resources"""
        if resource_type == 'tables':
            return self.list_tables()
        elif resource_type == 'records':
            # Default to first base/table
            if self.base_ids:
                base_name = list(self.base_ids.keys())[0]
                return self.list_records(base_name)
        
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_tables(self, base_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tables in a base"""
        # Note: Airtable doesn't have a direct API to list tables
        # This would need to be configured manually
        return [
            {'name': 'Configured tables would be listed here'}
        ]
    
    def list_records(self, base_name: str, table_name: str = None) -> List[Dict[str, Any]]:
        """List records from a table"""
        try:
            base_id = self.base_ids.get(base_name)
            if not base_id:
                logger.error(f"Base {base_name} not configured")
                return []
            
            # Would need table name to actually list records
            if not table_name:
                return []
            
            response = requests.get(
                f"{self.BASE_URL}/{base_id}/{table_name}",
                headers=self.headers,
                params={'maxRecords': 100},
                timeout=10
            )
            
            if response.status_code == 200:
                records = response.json().get('records', [])
                return [
                    {
                        'id': record['id'],
                        'fields': record['fields'],
                        'created_time': record['createdTime']
                    }
                    for record in records
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error listing records: {e}")
            return []