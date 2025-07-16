"""
Notion Integration

Handles Notion API interactions for importing/exporting tasks,
knowledge management, and documentation synchronization.
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import aiohttp
import asyncio
from enum import Enum

from apps.backend.core.settings import settings
from ..core.logging import get_logger
from ..memory.memory_store import MemoryStore
from ..memory.models import MemoryType, KnowledgeCategory

logger = get_logger(__name__)


class NotionBlockType(str, Enum):
    """Notion block types."""
    PARAGRAPH = "paragraph"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    TO_DO = "to_do"
    TOGGLE = "toggle"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    DIVIDER = "divider"


class NotionClient:
    """
    Client for interacting with Notion API.
    Handles database operations, page creation, and content synchronization.
    """
    
    def __init__(self):
        self.api_key = settings.NOTION_API_KEY
        self.base_url = "https://api.notion.com/v1"
        self.memory = MemoryStore()
        
        # Database IDs for different content types
        self.tasks_db_id = settings.NOTION_TASKS_DB_ID
        self.knowledge_db_id = settings.NOTION_KNOWLEDGE_DB_ID
        self.estimates_db_id = settings.NOTION_ESTIMATES_DB_ID
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": self.version
        }
    
    async def create_page(
        self,
        parent_id: str,
        title: str,
        content: List[Dict[str, Any]],
        properties: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        cover: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a new page in Notion.
        
        Args:
            parent_id: Parent page or database ID
            title: Page title
            content: List of content blocks
            properties: Database properties (if parent is database)
            icon: Page icon (emoji or URL)
            cover: Cover image URL
            
        Returns:
            Created page ID or None
        """
        
        # Build page data
        page_data = {
            "parent": {
                "database_id": parent_id if properties else None,
                "page_id": parent_id if not properties else None
            },
            "properties": properties or {
                "title": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            },
            "children": content
        }
        
        # Remove None parent type
        if page_data["parent"]["database_id"] is None:
            del page_data["parent"]["database_id"]
        else:
            del page_data["parent"]["page_id"]
        
        # Add optional fields
        if icon:
            page_data["icon"] = {
                "type": "emoji",
                "emoji": icon
            } if len(icon) <= 2 else {
                "type": "external",
                "external": {"url": icon}
            }
        
        if cover:
            page_data["cover"] = {
                "type": "external",
                "external": {"url": cover}
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/pages",
                    headers=self.headers,
                    json=page_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        page_id = result["id"]
                        
                        logger.info(f"Created Notion page: {page_id} - {title}")
                        
                        # Store in memory
                        await self._store_page_creation(page_id, title, parent_id)
                        
                        return page_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create Notion page: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}")
            return None
    
    async def create_database_item(
        self,
        database_id: str,
        properties: Dict[str, Any]
    ) -> Optional[str]:
        """
        Create a new item in a Notion database.
        
        Args:
            database_id: Notion database ID
            properties: Item properties matching database schema
            
        Returns:
            Created item ID or None
        """
        
        # Format properties for Notion API
        formatted_properties = self._format_database_properties(properties)
        
        page_data = {
            "parent": {"database_id": database_id},
            "properties": formatted_properties
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/pages",
                    headers=self.headers,
                    json=page_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["id"]
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create database item: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error creating database item: {str(e)}")
            return None
    
    async def export_task_to_notion(
        self,
        task_id: str,
        task_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Export a BrainOps task to Notion tasks database.
        
        Args:
            task_id: BrainOps task ID
            task_data: Task data including name, description, status
            
        Returns:
            Notion page ID or None
        """
        
        if not self.tasks_db_id:
            logger.warning("Notion tasks database ID not configured")
            return None
        
        # Map task data to Notion properties
        properties = {
            "Name": task_data.get("name", "Untitled Task"),
            "Status": task_data.get("status", "Not Started"),
            "Priority": task_data.get("priority", "Medium"),
            "Description": task_data.get("description", ""),
            "BrainOps ID": task_id,
            "Created": datetime.utcnow().isoformat()
        }
        
        # Add assignee if present
        if task_data.get("assignee"):
            properties["Assignee"] = task_data["assignee"]
        
        # Add due date if present
        if task_data.get("due_date"):
            properties["Due Date"] = task_data["due_date"]
        
        # Create in tasks database
        notion_id = await self.create_database_item(self.tasks_db_id, properties)
        
        if notion_id:
            logger.info(f"Exported task {task_id} to Notion: {notion_id}")
        
        return notion_id
    
    async def export_estimate_to_notion(
        self,
        estimate_id: str,
        estimate_data: Dict[str, Any],
        pricing: Dict[str, Any]
    ) -> Optional[str]:
        """
        Export a roofing estimate to Notion estimates database.
        
        Args:
            estimate_id: BrainOps estimate ID
            estimate_data: Estimate details
            pricing: Pricing breakdown
            
        Returns:
            Notion page ID or None
        """
        
        if not self.estimates_db_id:
            logger.warning("Notion estimates database ID not configured")
            return None
        
        # Create rich content for the estimate
        content = self._build_estimate_content(estimate_data, pricing)
        
        # Database properties
        properties = {
            "Project Name": estimate_data.get("project_name", "Untitled"),
            "Total Cost": pricing.get("grand_total", 0),
            "Building Type": estimate_data.get("building_type", "Commercial"),
            "Roof Area": estimate_data.get("roof_area_sf", 0),
            "System Type": estimate_data.get("system_type", "TPO"),
            "Status": "Draft",
            "BrainOps ID": estimate_id,
            "Created": datetime.utcnow().isoformat()
        }
        
        # Create page with properties
        page_data = {
            "parent": {"database_id": self.estimates_db_id},
            "properties": self._format_database_properties(properties),
            "children": content
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/pages",
                    headers=self.headers,
                    json=page_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        notion_id = result["id"]
                        
                        logger.info(f"Exported estimate {estimate_id} to Notion: {notion_id}")
                        return notion_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to export estimate: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error exporting estimate to Notion: {str(e)}")
            return None
    
    async def import_knowledge_from_notion(
        self,
        page_id: str
    ) -> Dict[str, Any]:
        """
        Import a knowledge page from Notion into BrainOps memory.
        
        Args:
            page_id: Notion page ID
            
        Returns:
            Import result with status and details
        """
        
        try:
            # Get page content
            page_data = await self._get_page(page_id)
            if not page_data:
                return {"status": "error", "error": "Page not found"}
            
            # Get page blocks
            blocks = await self._get_page_blocks(page_id)
            
            # Extract text content
            content = self._extract_text_from_blocks(blocks)
            
            # Extract title from properties
            title = self._extract_page_title(page_data)
            
            # Determine category based on parent or tags
            category = await self._determine_knowledge_category(page_data)
            
            # Store in BrainOps memory
            memory_id = await self.memory.store_memory(
                type=MemoryType.BUSINESS_CONTEXT,
                title=f"Notion: {title}",
                content=content,
                context={
                    "source": "notion",
                    "notion_id": page_id,
                    "url": page_data.get("url"),
                    "last_edited": page_data.get("last_edited_time")
                },
                category=category,
                tags=["notion", "imported"]
            )
            
            return {
                "status": "success",
                "memory_id": str(memory_id),
                "title": title,
                "content_length": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error importing from Notion: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def sync_knowledge_base(
        self,
        database_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync an entire Notion database with BrainOps knowledge base.
        
        Args:
            database_id: Notion database ID (uses default if not provided)
            
        Returns:
            Sync results with statistics
        """
        
        target_db = database_id or self.knowledge_db_id
        if not target_db:
            return {"status": "error", "error": "No knowledge database configured"}
        
        results = {
            "status": "success",
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "pages": []
        }
        
        try:
            # Query all pages in database
            pages = await self._query_database(target_db)
            
            for page in pages:
                page_id = page["id"]
                
                # Check if already imported
                if await self._is_page_imported(page_id):
                    results["skipped"] += 1
                    continue
                
                # Import page
                import_result = await self.import_knowledge_from_notion(page_id)
                
                if import_result["status"] == "success":
                    results["imported"] += 1
                    results["pages"].append({
                        "notion_id": page_id,
                        "memory_id": import_result["memory_id"],
                        "title": import_result["title"]
                    })
                else:
                    results["errors"] += 1
            
            logger.info(f"Knowledge sync complete: {results['imported']} imported, {results['skipped']} skipped")
            
        except Exception as e:
            logger.error(f"Error syncing knowledge base: {str(e)}")
            results["status"] = "error"
            results["error"] = str(e)
        
        return results
    
    # Private helper methods
    
    def _format_database_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Format properties for Notion database API."""
        
        formatted = {}
        
        for key, value in properties.items():
            # Auto-detect property type based on value
            if isinstance(value, str):
                if key.lower() in ["name", "title"]:
                    formatted[key] = {
                        "title": [{"text": {"content": value}}]
                    }
                elif key.lower() in ["url", "link"]:
                    formatted[key] = {"url": value}
                elif key.lower() == "email":
                    formatted[key] = {"email": value}
                else:
                    formatted[key] = {
                        "rich_text": [{"text": {"content": value}}]
                    }
            
            elif isinstance(value, (int, float)):
                formatted[key] = {"number": value}
            
            elif isinstance(value, bool):
                formatted[key] = {"checkbox": value}
            
            elif isinstance(value, list):
                # Assume multi-select
                formatted[key] = {
                    "multi_select": [{"name": item} for item in value]
                }
            
            elif key.lower() in ["date", "due date", "created", "updated"]:
                formatted[key] = {"date": {"start": value}}
        
        return formatted
    
    def _build_estimate_content(
        self,
        estimate_data: Dict[str, Any],
        pricing: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build Notion blocks for estimate content."""
        
        blocks = []
        
        # Header
        blocks.append({
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Roofing Estimate Details"}
                }]
            }
        })
        
        # Executive Summary
        if estimate_data.get("executive_summary"):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": estimate_data["executive_summary"]}
                    }]
                }
            })
        
        # Pricing Summary
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Pricing Summary"}
                }]
            }
        })
        
        # Pricing table as callout
        pricing_text = f"""
Material Cost: ${pricing.get('material_cost', 0):,.2f}
Labor Cost: ${pricing.get('labor_cost', 0):,.2f}
Equipment Cost: ${pricing.get('equipment_cost', 0):,.2f}
Overhead: ${pricing.get('overhead', 0):,.2f}
Markup ({pricing.get('markup_percentage', 0)}%): ${pricing.get('markup_amount', 0):,.2f}
        
Grand Total: ${pricing.get('grand_total', 0):,.2f}
Cost per SF: ${pricing.get('cost_per_sf', 0):.2f}
        """
        
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": pricing_text.strip()}
                }],
                "icon": {"emoji": "💰"}
            }
        })
        
        # Scope of Work
        if estimate_data.get("scope_narrative"):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "Scope of Work"}
                    }]
                }
            })
            
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": estimate_data["scope_narrative"]}
                    }]
                }
            })
        
        return blocks
    
    async def _get_page(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get page data from Notion."""
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/pages/{page_id}",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting Notion page: {str(e)}")
            return None
    
    async def _get_page_blocks(self, page_id: str) -> List[Dict[str, Any]]:
        """Get all blocks from a Notion page."""
        
        blocks = []
        has_more = True
        start_cursor = None
        
        try:
            async with aiohttp.ClientSession() as session:
                while has_more:
                    url = f"{self.base_url}/blocks/{page_id}/children"
                    params = {"page_size": 100}
                    
                    if start_cursor:
                        params["start_cursor"] = start_cursor
                    
                    async with session.get(
                        url,
                        headers=self.headers,
                        params=params
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            blocks.extend(data.get("results", []))
                            has_more = data.get("has_more", False)
                            start_cursor = data.get("next_cursor")
                        else:
                            break
                            
        except Exception as e:
            logger.error(f"Error getting page blocks: {str(e)}")
        
        return blocks
    
    def _extract_text_from_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """Extract plain text from Notion blocks."""
        
        text_parts = []
        
        for block in blocks:
            block_type = block.get("type")
            block_data = block.get(block_type, {})
            
            # Extract rich text content
            rich_text = block_data.get("rich_text", [])
            
            if rich_text:
                text = "".join(rt.get("plain_text", "") for rt in rich_text)
                text_parts.append(text)
            
            # Handle special block types
            if block_type == "code":
                code_text = block_data.get("caption", [])
                if code_text:
                    text_parts.append("".join(ct.get("plain_text", "") for ct in code_text))
        
        return "\n\n".join(text_parts)
    
    def _extract_page_title(self, page_data: Dict[str, Any]) -> str:
        """Extract title from page properties."""
        
        properties = page_data.get("properties", {})
        
        # Look for common title property names
        for prop_name in ["Name", "Title", "title", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    if title_array:
                        return title_array[0].get("plain_text", "Untitled")
        
        return "Untitled"
    
    async def _determine_knowledge_category(
        self,
        page_data: Dict[str, Any]
    ) -> Optional[KnowledgeCategory]:
        """Determine knowledge category based on page data."""
        
        # Check parent database
        parent = page_data.get("parent", {})
        
        if parent.get("type") == "database_id":
            db_id = parent.get("database_id")
            
            # Map database IDs to categories
            if db_id == self.knowledge_db_id:
                # Could further categorize based on properties
                return KnowledgeCategory.BEST_PRACTICES
        
        # Default to templates
        return KnowledgeCategory.TEMPLATES
    
    async def _query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query all pages from a Notion database."""
        
        pages = []
        has_more = True
        start_cursor = None
        
        try:
            async with aiohttp.ClientSession() as session:
                while has_more:
                    query_data = {"page_size": 100}
                    
                    if filter_obj:
                        query_data["filter"] = filter_obj
                    
                    if start_cursor:
                        query_data["start_cursor"] = start_cursor
                    
                    async with session.post(
                        f"{self.base_url}/databases/{database_id}/query",
                        headers=self.headers,
                        json=query_data
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            pages.extend(data.get("results", []))
                            has_more = data.get("has_more", False)
                            start_cursor = data.get("next_cursor")
                        else:
                            break
                            
        except Exception as e:
            logger.error(f"Error querying database: {str(e)}")
        
        return pages
    
    async def _is_page_imported(self, page_id: str) -> bool:
        """Check if a Notion page has already been imported."""
        
        from ..memory.models import MemorySearchQuery
        
        # Search for existing import
        query = MemorySearchQuery(
            query=f"notion_id:{page_id}",
            max_results=1
        )
        
        results = await self.memory.search_memories(query)
        
        return len(results) > 0
    
    async def _store_page_creation(
        self,
        page_id: str,
        title: str,
        parent_id: str
    ):
        """Store page creation event in memory."""
        
        await self.memory.store_memory(
            type=MemoryType.INTEGRATION_EVENT,
            title=f"Created Notion Page: {title}",
            content=f"Page ID: {page_id}, Parent: {parent_id}",
            context={
                "integration": "notion",
                "event_type": "page_created",
                "page_id": page_id,
                "parent_id": parent_id
            },
            tags=["notion", "page_creation", page_id]
        )