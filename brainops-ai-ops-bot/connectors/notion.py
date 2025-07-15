"""
Notion connector for database and documentation integration
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from notion_client import Client
from .base import BaseConnector


logger = logging.getLogger(__name__)


class NotionConnector(BaseConnector):
    """Notion API connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_token = config.get('api_token')
        self.database_ids = config.get('database_ids', {})
        self.client = None
    
    def authenticate(self) -> bool:
        """Initialize Notion client"""
        try:
            self.client = Client(auth=self.api_token)
            # Test authentication by getting user info
            users = self.client.users.list()
            
            if users:
                self._is_authenticated = True
                logger.info("Notion authentication successful")
                return True
            else:
                logger.error("Notion authentication failed")
                return False
                
        except Exception as e:
            logger.error(f"Notion authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Notion API health"""
        try:
            # Try to list users as a health check
            users = self.client.users.list()
            
            # Check if we can access configured databases
            accessible_dbs = 0
            for db_name, db_id in self.database_ids.items():
                try:
                    self.client.databases.retrieve(db_id)
                    accessible_dbs += 1
                except:
                    pass
            
            return {
                'healthy': True,
                'message': f"Connected successfully",
                'details': {
                    'users_count': len(users.get('results', [])),
                    'configured_databases': len(self.database_ids),
                    'accessible_databases': accessible_dbs
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Notion resources"""
        if resource_type == 'databases':
            return self.list_databases()
        elif resource_type == 'pages':
            return self.list_pages()
        elif resource_type == 'users':
            return self.list_users()
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_databases(self) -> List[Dict[str, Any]]:
        """List accessible databases"""
        try:
            databases = []
            
            # List configured databases
            for db_name, db_id in self.database_ids.items():
                try:
                    db = self.client.databases.retrieve(db_id)
                    databases.append({
                        'id': db['id'],
                        'name': db_name,
                        'title': self._get_title(db.get('title', [])),
                        'created_time': db['created_time'],
                        'last_edited_time': db['last_edited_time']
                    })
                except Exception as e:
                    logger.error(f"Cannot access database {db_name}: {e}")
            
            return databases
            
        except Exception as e:
            logger.error(f"Error listing databases: {e}")
            return []
    
    def list_pages(self, database_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List pages from a database"""
        try:
            if not database_id:
                # Use the first configured database
                if self.database_ids:
                    database_id = list(self.database_ids.values())[0]
                else:
                    return []
            
            response = self.client.databases.query(database_id=database_id)
            pages = []
            
            for page in response.get('results', []):
                pages.append({
                    'id': page['id'],
                    'created_time': page['created_time'],
                    'last_edited_time': page['last_edited_time'],
                    'properties': self._extract_properties(page.get('properties', {}))
                })
            
            return pages
            
        except Exception as e:
            logger.error(f"Error listing pages: {e}")
            return []
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List Notion users"""
        try:
            response = self.client.users.list()
            users = []
            
            for user in response.get('results', []):
                users.append({
                    'id': user['id'],
                    'type': user['type'],
                    'name': user.get('name', 'Unknown'),
                    'email': user.get('person', {}).get('email', 'N/A') if user['type'] == 'person' else 'N/A'
                })
            
            return users
            
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
    def create_resource(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Notion resource"""
        if resource_type == 'page':
            return self.create_page(data)
        else:
            raise ValueError(f"Cannot create resource type: {resource_type}")
    
    def create_page(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new page in a database"""
        try:
            database_id = page_data.pop('database_id')
            properties = page_data.pop('properties', {})
            
            # Convert properties to Notion format
            notion_properties = self._format_properties(properties)
            
            response = self.client.pages.create(
                parent={"database_id": database_id},
                properties=notion_properties
            )
            
            return {
                'success': True,
                'page_id': response['id'],
                'url': response['url']
            }
            
        except Exception as e:
            logger.error(f"Error creating page: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_resource(self, resource_type: str, resource_id: str, 
                       data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a Notion resource"""
        if resource_type == 'page':
            return self.update_page(resource_id, data)
        else:
            raise ValueError(f"Cannot update resource type: {resource_type}")
    
    def update_page(self, page_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing page"""
        try:
            properties = update_data.get('properties', {})
            notion_properties = self._format_properties(properties)
            
            response = self.client.pages.update(
                page_id=page_id,
                properties=notion_properties
            )
            
            return {
                'success': True,
                'page_id': response['id']
            }
            
        except Exception as e:
            logger.error(f"Error updating page: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search(self, query: str, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search Notion content"""
        try:
            search_params = {
                'query': query
            }
            
            if filter_type:
                search_params['filter'] = {
                    'property': 'object',
                    'value': filter_type  # 'page' or 'database'
                }
            
            response = self.client.search(**search_params)
            results = []
            
            for result in response.get('results', []):
                results.append({
                    'id': result['id'],
                    'type': result['object'],
                    'title': self._get_title(result.get('title', [])) if result['object'] == 'database' 
                            else self._extract_page_title(result),
                    'url': result.get('url', ''),
                    'last_edited_time': result['last_edited_time']
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def _get_title(self, title_array: List[Dict]) -> str:
        """Extract title from Notion title array"""
        if not title_array:
            return "Untitled"
        
        return ''.join([t.get('plain_text', '') for t in title_array])
    
    def _extract_page_title(self, page: Dict) -> str:
        """Extract title from page properties"""
        properties = page.get('properties', {})
        
        # Look for common title property names
        for prop_name in ['Title', 'Name', 'title', 'name']:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop['type'] == 'title':
                    return self._get_title(prop.get('title', []))
        
        return "Untitled"
    
    def _extract_properties(self, properties: Dict) -> Dict[str, Any]:
        """Extract simplified properties from Notion properties"""
        simplified = {}
        
        for prop_name, prop_value in properties.items():
            prop_type = prop_value['type']
            
            if prop_type == 'title':
                simplified[prop_name] = self._get_title(prop_value.get('title', []))
            elif prop_type == 'rich_text':
                simplified[prop_name] = self._get_title(prop_value.get('rich_text', []))
            elif prop_type == 'number':
                simplified[prop_name] = prop_value.get('number')
            elif prop_type == 'select':
                simplified[prop_name] = prop_value.get('select', {}).get('name')
            elif prop_type == 'multi_select':
                simplified[prop_name] = [s['name'] for s in prop_value.get('multi_select', [])]
            elif prop_type == 'date':
                simplified[prop_name] = prop_value.get('date', {}).get('start')
            elif prop_type == 'checkbox':
                simplified[prop_name] = prop_value.get('checkbox', False)
            elif prop_type == 'url':
                simplified[prop_name] = prop_value.get('url')
            elif prop_type == 'email':
                simplified[prop_name] = prop_value.get('email')
            elif prop_type == 'phone_number':
                simplified[prop_name] = prop_value.get('phone_number')
        
        return simplified
    
    def _format_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Format properties for Notion API"""
        formatted = {}
        
        for prop_name, prop_value in properties.items():
            if isinstance(prop_value, str):
                # Assume it's a title or text
                formatted[prop_name] = {
                    'title': [{'text': {'content': prop_value}}]
                }
            elif isinstance(prop_value, (int, float)):
                formatted[prop_name] = {'number': prop_value}
            elif isinstance(prop_value, bool):
                formatted[prop_name] = {'checkbox': prop_value}
            elif isinstance(prop_value, list):
                # Assume multi-select
                formatted[prop_name] = {
                    'multi_select': [{'name': item} for item in prop_value]
                }
            elif isinstance(prop_value, dict):
                # Pass through if already formatted
                formatted[prop_name] = prop_value
        
        return formatted