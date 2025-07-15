"""
Notion integration module for BrainOps.

Handles bidirectional sync with Notion databases, page creation, and
content management. Built to leverage Notion as a knowledge base while
maintaining BrainOps as the automation engine.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import asyncio

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from ..core.settings import settings
from ..core.logging import get_logger
from ..memory.memory_store import save_notion_sync_event


logger = get_logger(__name__)


class NotionIntegrationHandler:
    """
    Comprehensive Notion API integration handler.
    
    Manages database queries, page operations, and content synchronization.
    Built to bridge structured data in Notion with automation capabilities
    in BrainOps.
    """
    
    def __init__(self):
        self.client = None
        if settings.NOTION_API_KEY:
            self.client = AsyncClient(auth=settings.NOTION_API_KEY.get_secret_value())
        else:
            logger.warning("Notion API key not configured - Notion integration disabled")
        
        # Cache database schemas to avoid repeated API calls
        self.database_schemas: Dict[str, Dict[str, Any]] = {}
        self.schema_cache_ttl = 3600  # 1 hour cache
    
    async def search_pages(
        self,
        query: str,
        filter_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search Notion workspace for pages and databases.
        
        Enables quick discovery of relevant content for automation
        workflows. Essential for knowledge-driven task execution.
        """
        if not self.client:
            return []
        
        try:
            # Build search parameters
            search_params = {
                "query": query,
                "page_size": limit
            }
            
            if filter_type:
                search_params["filter"] = {"property": "object", "value": filter_type}
            
            # Execute search
            response = await self.client.search(**search_params)
            
            # Process results for consistent format
            results = []
            for item in response.get("results", []):
                results.append(self._format_search_result(item))
            
            return results
            
        except APIResponseError as e:
            logger.error(f"Notion search failed: {str(e)}")
            return []
    
    async def get_database_items(
        self,
        database_id: str,
        filter_conditions: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, str]]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query items from a Notion database with filtering and sorting.
        
        Transforms Notion databases into actionable data sources for
        automation. Critical for data-driven workflows.
        """
        if not self.client:
            return []
        
        try:
            # Build query parameters
            query_params = {
                "database_id": database_id,
                "page_size": min(limit, 100)  # Notion max is 100
            }
            
            if filter_conditions:
                query_params["filter"] = filter_conditions
            
            if sorts:
                query_params["sorts"] = sorts
            
            # Get database schema for property interpretation
            schema = await self._get_database_schema(database_id)
            
            # Execute query
            response = await self.client.databases.query(**query_params)
            
            # Process results with schema awareness
            items = []
            for page in response.get("results", []):
                items.append(self._extract_page_properties(page, schema))
            
            # Log sync event for tracking
            await save_notion_sync_event({
                "operation": "database_query",
                "database_id": database_id,
                "items_retrieved": len(items),
                "timestamp": datetime.utcnow()
            })
            
            return items
            
        except APIResponseError as e:
            logger.error(f"Notion database query failed: {str(e)}")
            return []
    
    async def create_page(
        self,
        parent_id: str,
        title: str,
        properties: Dict[str, Any],
        content: Optional[List[Dict[str, Any]]] = None,
        parent_type: str = "database"
    ) -> Optional[str]:
        """
        Create a new page in Notion with properties and content.
        
        Enables BrainOps to push automation results back to Notion,
        closing the loop between data sources and automated actions.
        """
        if not self.client:
            return None
        
        try:
            # Build page data structure
            page_data = {
                "parent": {},
                "properties": {}
            }
            
            # Set parent reference
            if parent_type == "database":
                page_data["parent"]["database_id"] = parent_id
            else:
                page_data["parent"]["page_id"] = parent_id
            
            # Add title property (required for all pages)
            page_data["properties"]["title"] = {
                "title": [{
                    "text": {"content": title}
                }]
            }
            
            # Add custom properties
            if parent_type == "database" and properties:
                schema = await self._get_database_schema(parent_id)
                formatted_props = self._format_properties_for_creation(properties, schema)
                page_data["properties"].update(formatted_props)
            
            # Create the page
            response = await self.client.pages.create(**page_data)
            page_id = response["id"]
            
            # Add content blocks if provided
            if content:
                await self._add_blocks_to_page(page_id, content)
            
            logger.info(f"Created Notion page: {page_id}")
            return page_id
            
        except APIResponseError as e:
            logger.error(f"Notion page creation failed: {str(e)}")
            return None
    
    async def update_page_properties(
        self,
        page_id: str,
        properties: Dict[str, Any]
    ) -> bool:
        """
        Update properties of an existing Notion page.
        
        Keeps Notion data synchronized with automation outcomes,
        ensuring single source of truth across systems.
        """
        if not self.client:
            return False
        
        try:
            # Get parent database schema if applicable
            page = await self.client.pages.retrieve(page_id)
            
            formatted_props = {}
            if page["parent"].get("database_id"):
                schema = await self._get_database_schema(page["parent"]["database_id"])
                formatted_props = self._format_properties_for_creation(properties, schema)
            else:
                # Simple properties for non-database pages
                formatted_props = properties
            
            # Update the page
            await self.client.pages.update(
                page_id=page_id,
                properties=formatted_props
            )
            
            return True
            
        except APIResponseError as e:
            logger.error(f"Notion page update failed: {str(e)}")
            return False
    
    async def _get_database_schema(self, database_id: str) -> Dict[str, Any]:
        """
        Get and cache database schema for property formatting.
        
        Prevents repeated API calls while ensuring accurate property
        handling. Critical for reliable data synchronization.
        """
        # Check cache first
        cache_key = f"schema_{database_id}"
        if cache_key in self.database_schemas:
            cached_schema, cached_time = self.database_schemas[cache_key]
            if (datetime.utcnow() - cached_time).seconds < self.schema_cache_ttl:
                return cached_schema
        
        try:
            # Fetch fresh schema
            database = await self.client.databases.retrieve(database_id)
            schema = database.get("properties", {})
            
            # Cache for future use
            self.database_schemas[cache_key] = (schema, datetime.utcnow())
            
            return schema
            
        except APIResponseError as e:
            logger.error(f"Failed to retrieve database schema: {str(e)}")
            return {}
    
    def _format_search_result(self, notion_object: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format Notion search results into consistent structure.
        
        Normalizes varied Notion object types for predictable
        processing in automation workflows.
        """
        result = {
            "id": notion_object["id"],
            "type": notion_object["object"],
            "created_time": notion_object["created_time"],
            "last_edited_time": notion_object["last_edited_time"],
            "url": notion_object.get("url", ""),
            "archived": notion_object.get("archived", False)
        }
        
        # Extract title based on object type
        if notion_object["object"] == "page":
            # Get title from properties
            props = notion_object.get("properties", {})
            for prop_name, prop_value in props.items():
                if prop_value.get("type") == "title":
                    title_items = prop_value.get("title", [])
                    if title_items:
                        result["title"] = title_items[0].get("plain_text", "Untitled")
                    break
        elif notion_object["object"] == "database":
            # Database title is in title array
            title_items = notion_object.get("title", [])
            if title_items:
                result["title"] = title_items[0].get("plain_text", "Untitled Database")
        
        return result
    
    def _extract_page_properties(
        self,
        page: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract and normalize page properties based on schema.
        
        Handles Notion's complex property types to provide clean
        data for automation logic. Essential for data integrity.
        """
        extracted = {
            "id": page["id"],
            "created_time": page["created_time"],
            "last_edited_time": page["last_edited_time"],
            "url": page.get("url", ""),
            "properties": {}
        }
        
        # Process each property based on its type
        for prop_name, prop_value in page.get("properties", {}).items():
            prop_type = prop_value.get("type")
            
            if prop_type == "title":
                items = prop_value.get("title", [])
                extracted["properties"][prop_name] = items[0].get("plain_text", "") if items else ""
            
            elif prop_type == "rich_text":
                items = prop_value.get("rich_text", [])
                extracted["properties"][prop_name] = items[0].get("plain_text", "") if items else ""
            
            elif prop_type == "number":
                extracted["properties"][prop_name] = prop_value.get("number")
            
            elif prop_type == "select":
                select_val = prop_value.get("select")
                extracted["properties"][prop_name] = select_val.get("name") if select_val else None
            
            elif prop_type == "multi_select":
                extracted["properties"][prop_name] = [
                    item.get("name") for item in prop_value.get("multi_select", [])
                ]
            
            elif prop_type == "date":
                date_val = prop_value.get("date")
                if date_val:
                    extracted["properties"][prop_name] = date_val.get("start")
            
            elif prop_type == "checkbox":
                extracted["properties"][prop_name] = prop_value.get("checkbox", False)
            
            elif prop_type == "url":
                extracted["properties"][prop_name] = prop_value.get("url")
            
            elif prop_type == "email":
                extracted["properties"][prop_name] = prop_value.get("email")
            
            elif prop_type == "phone_number":
                extracted["properties"][prop_name] = prop_value.get("phone_number")
            
            # Add more property types as needed
        
        return extracted
    
    def _format_properties_for_creation(
        self,
        properties: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format properties for page creation based on database schema.
        
        Ensures data conforms to Notion's expected formats, preventing
        API errors and data corruption. Critical for reliable sync.
        """
        formatted = {}
        
        for prop_name, prop_value in properties.items():
            if prop_name not in schema:
                continue
            
            prop_config = schema[prop_name]
            prop_type = prop_config.get("type")
            
            if prop_type == "title":
                formatted[prop_name] = {
                    "title": [{
                        "text": {"content": str(prop_value)}
                    }]
                }
            
            elif prop_type == "rich_text":
                formatted[prop_name] = {
                    "rich_text": [{
                        "text": {"content": str(prop_value)}
                    }]
                }
            
            elif prop_type == "number":
                formatted[prop_name] = {"number": float(prop_value) if prop_value else None}
            
            elif prop_type == "select":
                formatted[prop_name] = {"select": {"name": str(prop_value)}} if prop_value else {"select": None}
            
            elif prop_type == "multi_select":
                if isinstance(prop_value, list):
                    formatted[prop_name] = {
                        "multi_select": [{"name": str(v)} for v in prop_value]
                    }
            
            elif prop_type == "date":
                formatted[prop_name] = {"date": {"start": str(prop_value)}} if prop_value else {"date": None}
            
            elif prop_type == "checkbox":
                formatted[prop_name] = {"checkbox": bool(prop_value)}
            
            elif prop_type == "url":
                formatted[prop_name] = {"url": str(prop_value) if prop_value else None}
            
            # Add more property types as needed
        
        return formatted
    
    async def _add_blocks_to_page(self, page_id: str, blocks: List[Dict[str, Any]]) -> bool:
        """
        Add content blocks to a Notion page.
        
        Enables rich content creation from automation results,
        making Notion a powerful presentation layer for BrainOps.
        """
        try:
            # Notion has a limit of 100 blocks per request
            for i in range(0, len(blocks), 100):
                chunk = blocks[i:i+100]
                await self.client.blocks.children.append(
                    block_id=page_id,
                    children=chunk
                )
            
            return True
            
        except APIResponseError as e:
            logger.error(f"Failed to add blocks to page: {str(e)}")
            return False


# Global handler instance
notion_handler = NotionIntegrationHandler()


# Convenience functions for task usage
async def search_notion(query: str, **kwargs) -> List[Dict[str, Any]]:
    """Search Notion workspace for relevant content."""
    return await notion_handler.search_pages(query, **kwargs)


async def query_notion_database(database_id: str, **kwargs) -> List[Dict[str, Any]]:
    """Query a Notion database with optional filters."""
    return await notion_handler.get_database_items(database_id, **kwargs)


async def create_notion_page(parent_id: str, title: str, **kwargs) -> Optional[str]:
    """Create a new page in Notion."""
    return await notion_handler.create_page(parent_id, title, **kwargs)