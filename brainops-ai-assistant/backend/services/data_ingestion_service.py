"""Data ingestion service for bulk loading historical data."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import aiofiles
from loguru import logger
import docx
import pypdf
import markdown

from core.database import get_db
from models.db import (
    KnowledgeEntryDB,
    FileMetadataDB,
    AssistantMessageDB,
    AssistantSessionDB,
    TaskDB,
    WorkflowDB,
    AuditLog,
    User
)
from services.rag_service import RAGService
from services.file_operations import FileOperationsService


class DataIngestionService:
    """Service for ingesting and indexing historical data."""
    
    def __init__(self):
        self.rag_service = RAGService()
        self.file_ops = FileOperationsService()
        self.supported_formats = {
            '.txt': self._process_text_file,
            '.md': self._process_markdown_file,
            '.pdf': self._process_pdf_file,
            '.docx': self._process_docx_file,
            '.json': self._process_json_file,
            '.py': self._process_code_file,
            '.js': self._process_code_file,
            '.ts': self._process_code_file,
            '.html': self._process_html_file,
            '.css': self._process_code_file,
            '.sql': self._process_code_file,
            '.yml': self._process_yaml_file,
            '.yaml': self._process_yaml_file,
        }
    
    async def initialize(self):
        """Initialize the data ingestion service."""
        await self.rag_service.initialize()
        logger.info("Data ingestion service initialized")
    
    async def ingest_directory(
        self, 
        directory_path: str, 
        user_id: int,
        recursive: bool = True,
        skip_existing: bool = True,
        category: str = "imported"
    ) -> Dict[str, Any]:
        """Ingest all supported files from a directory."""
        try:
            stats = {
                "total_files": 0,
                "processed_files": 0,
                "skipped_files": 0,
                "errors": 0,
                "categories": {}
            }
            
            directory = Path(directory_path)
            if not directory.exists():
                raise ValueError(f"Directory does not exist: {directory_path}")
            
            # Get all files
            pattern = "**/*" if recursive else "*"
            files = [f for f in directory.glob(pattern) if f.is_file()]
            stats["total_files"] = len(files)
            
            logger.info(f"Found {len(files)} files to process in {directory_path}")
            
            # Process files in batches
            batch_size = 10
            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._process_file(file_path, user_id, category, skip_existing) for file_path in batch],
                    return_exceptions=True
                )
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        stats["errors"] += 1
                        logger.error(f"File processing error: {result}")
                    elif result:
                        if result.get("skipped"):
                            stats["skipped_files"] += 1
                        else:
                            stats["processed_files"] += 1
                            
                        # Track categories
                        file_category = result.get("category", "unknown")
                        stats["categories"][file_category] = stats["categories"].get(file_category, 0) + 1
            
            logger.info(f"Directory ingestion completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to ingest directory {directory_path}: {e}")
            return {"error": str(e), "total_files": 0, "processed_files": 0}
    
    async def _process_file(
        self, 
        file_path: Path, 
        user_id: int, 
        category: str,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """Process a single file."""
        try:
            # Check if file already exists
            if skip_existing:
                async with get_db() as db:
                    existing_file = await db.scalar(
                        select(FileMetadataDB).where(FileMetadataDB.path == str(file_path))
                    )
                    if existing_file:
                        return {"skipped": True, "reason": "already_exists", "path": str(file_path)}
            
            # Get file info
            file_stats = file_path.stat()
            file_extension = file_path.suffix.lower()
            
            # Check if file format is supported
            if file_extension not in self.supported_formats:
                return {"skipped": True, "reason": "unsupported_format", "path": str(file_path)}
            
            # Process file content
            processor = self.supported_formats[file_extension]
            content_data = await processor(file_path)
            
            if not content_data:
                return {"skipped": True, "reason": "no_content", "path": str(file_path)}
            
            # Create file metadata record
            file_metadata = FileMetadataDB(
                id=str(uuid.uuid4()),
                path=str(file_path),
                filename=file_path.name,
                size_bytes=file_stats.st_size,
                mime_type=mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
                checksum=await self._calculate_file_checksum(file_path),
                created_by=user_id,
                tags=[category, file_extension.replace('.', '')]
            )
            
            # Create knowledge entry
            knowledge_entry = KnowledgeEntryDB(
                id=str(uuid.uuid4()),
                title=content_data.get("title", file_path.name),
                content=content_data["content"],
                type=self._determine_content_type(file_extension),
                category=category,
                tags=content_data.get("tags", []) + [file_extension.replace('.', ''), category],
                source=str(file_path),
                created_by=user_id,
                metadata={
                    "file_size": file_stats.st_size,
                    "file_extension": file_extension,
                    "processing_method": processor.__name__,
                    "ingestion_timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Save to database
            async with get_db() as db:
                db.add(file_metadata)
                db.add(knowledge_entry)
                await db.commit()
                
                # Index for RAG
                await self.rag_service.index_knowledge_entry(knowledge_entry)
            
            logger.debug(f"Processed file: {file_path}")
            return {
                "processed": True,
                "path": str(file_path),
                "category": category,
                "content_length": len(content_data["content"]),
                "file_size": file_stats.st_size
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return {"error": str(e), "path": str(file_path)}
    
    async def _process_text_file(self, file_path: Path) -> Dict[str, Any]:
        """Process plain text file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            return {
                "title": file_path.name,
                "content": content,
                "tags": ["text", "document"]
            }
        except Exception as e:
            logger.error(f"Failed to process text file {file_path}: {e}")
            return None
    
    async def _process_markdown_file(self, file_path: Path) -> Dict[str, Any]:
        """Process markdown file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Convert markdown to HTML for better processing
            html_content = markdown.markdown(content)
            
            return {
                "title": file_path.stem,
                "content": content,
                "tags": ["markdown", "document"],
                "metadata": {
                    "html_content": html_content
                }
            }
        except Exception as e:
            logger.error(f"Failed to process markdown file {file_path}: {e}")
            return None
    
    async def _process_pdf_file(self, file_path: Path) -> Dict[str, Any]:
        """Process PDF file."""
        try:
            text_content = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        text_content.append(f"Page {page_num + 1}:\n{text}")
            
            content = "\n\n".join(text_content)
            
            return {
                "title": file_path.stem,
                "content": content,
                "tags": ["pdf", "document"],
                "metadata": {
                    "page_count": len(pdf_reader.pages)
                }
            }
        except Exception as e:
            logger.error(f"Failed to process PDF file {file_path}: {e}")
            return None
    
    async def _process_docx_file(self, file_path: Path) -> Dict[str, Any]:
        """Process Word document."""
        try:
            doc = docx.Document(file_path)
            
            # Extract text from paragraphs
            paragraphs = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    paragraphs.append(paragraph.text)
            
            content = "\n\n".join(paragraphs)
            
            return {
                "title": file_path.stem,
                "content": content,
                "tags": ["docx", "document", "word"],
                "metadata": {
                    "paragraph_count": len(paragraphs)
                }
            }
        except Exception as e:
            logger.error(f"Failed to process DOCX file {file_path}: {e}")
            return None
    
    async def _process_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Process JSON file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Parse JSON to validate and extract structure
            data = json.loads(content)
            
            # Create a readable representation
            formatted_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            return {
                "title": file_path.name,
                "content": formatted_content,
                "tags": ["json", "data", "structured"],
                "metadata": {
                    "json_keys": list(data.keys()) if isinstance(data, dict) else [],
                    "data_type": type(data).__name__
                }
            }
        except Exception as e:
            logger.error(f"Failed to process JSON file {file_path}: {e}")
            return None
    
    async def _process_code_file(self, file_path: Path) -> Dict[str, Any]:
        """Process code file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Determine language from extension
            language_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.html': 'html',
                '.css': 'css',
                '.sql': 'sql'
            }
            
            language = language_map.get(file_path.suffix.lower(), 'text')
            
            return {
                "title": file_path.name,
                "content": content,
                "tags": ["code", language, "programming"],
                "metadata": {
                    "language": language,
                    "line_count": len(content.splitlines())
                }
            }
        except Exception as e:
            logger.error(f"Failed to process code file {file_path}: {e}")
            return None
    
    async def _process_html_file(self, file_path: Path) -> Dict[str, Any]:
        """Process HTML file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Extract text content using basic parsing
            # In a production environment, you'd use BeautifulSoup or similar
            import re
            text_content = re.sub(r'<[^>]+>', '', content)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            return {
                "title": file_path.stem,
                "content": text_content,
                "tags": ["html", "web", "markup"],
                "metadata": {
                    "raw_html": content[:1000] + "..." if len(content) > 1000 else content
                }
            }
        except Exception as e:
            logger.error(f"Failed to process HTML file {file_path}: {e}")
            return None
    
    async def _process_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Process YAML file."""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Parse YAML to validate
            import yaml
            data = yaml.safe_load(content)
            
            return {
                "title": file_path.name,
                "content": content,
                "tags": ["yaml", "configuration", "structured"],
                "metadata": {
                    "yaml_keys": list(data.keys()) if isinstance(data, dict) else [],
                    "data_type": type(data).__name__
                }
            }
        except Exception as e:
            logger.error(f"Failed to process YAML file {file_path}: {e}")
            return None
    
    def _determine_content_type(self, file_extension: str) -> str:
        """Determine content type based on file extension."""
        type_map = {
            '.txt': 'document',
            '.md': 'document',
            '.pdf': 'document',
            '.docx': 'document',
            '.json': 'data',
            '.py': 'code',
            '.js': 'code',
            '.ts': 'code',
            '.html': 'markup',
            '.css': 'code',
            '.sql': 'code',
            '.yml': 'configuration',
            '.yaml': 'configuration'
        }
        return type_map.get(file_extension.lower(), 'document')
    
    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum for a file."""
        try:
            import hashlib
            hash_sha256 = hashlib.sha256()
            
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    async def ingest_chat_history(self, chat_data: List[Dict[str, Any]], user_id: int) -> Dict[str, Any]:
        """Ingest chat history data."""
        try:
            stats = {
                "total_messages": len(chat_data),
                "processed_messages": 0,
                "sessions_created": 0,
                "errors": 0
            }
            
            # Group messages by session
            sessions = {}
            for message_data in chat_data:
                session_id = message_data.get("session_id") or str(uuid.uuid4())
                if session_id not in sessions:
                    sessions[session_id] = []
                sessions[session_id].append(message_data)
            
            async with get_db() as db:
                for session_id, messages in sessions.items():
                    try:
                        # Create session
                        session = AssistantSessionDB(
                            id=session_id,
                            user_id=user_id,
                            created_at=datetime.fromisoformat(messages[0].get("timestamp", datetime.utcnow().isoformat())),
                            context={"source": "historical_import"},
                            mode="chat"
                        )
                        db.add(session)
                        stats["sessions_created"] += 1
                        
                        # Add messages
                        for msg_data in messages:
                            message = AssistantMessageDB(
                                id=str(uuid.uuid4()),
                                session_id=session_id,
                                role=msg_data.get("role", "user"),
                                content=msg_data.get("content", ""),
                                timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.utcnow().isoformat())),
                                message_type=msg_data.get("type", "chat"),
                                metadata=msg_data.get("metadata", {}),
                                context=msg_data.get("context", {})
                            )
                            db.add(message)
                            
                            # Index for RAG
                            await self.rag_service.index_message(message)
                            stats["processed_messages"] += 1
                        
                        await db.commit()
                        
                    except Exception as e:
                        await db.rollback()
                        stats["errors"] += 1
                        logger.error(f"Failed to process session {session_id}: {e}")
            
            logger.info(f"Chat history ingestion completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to ingest chat history: {e}")
            return {"error": str(e), "total_messages": 0, "processed_messages": 0}
    
    async def ingest_project_data(self, project_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Ingest project data (tasks, workflows, etc.)."""
        try:
            stats = {
                "tasks_created": 0,
                "workflows_created": 0,
                "knowledge_entries_created": 0,
                "errors": 0
            }
            
            async with get_db() as db:
                # Process tasks
                for task_data in project_data.get("tasks", []):
                    try:
                        task = TaskDB(
                            id=str(uuid.uuid4()),
                            title=task_data.get("title", "Imported Task"),
                            description=task_data.get("description", ""),
                            status=task_data.get("status", "completed"),
                            priority=task_data.get("priority", "medium"),
                            created_by=user_id,
                            created_at=datetime.fromisoformat(task_data.get("created_at", datetime.utcnow().isoformat())),
                            tags=task_data.get("tags", []) + ["imported"],
                            metadata=task_data.get("metadata", {})
                        )
                        db.add(task)
                        stats["tasks_created"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Failed to create task: {e}")
                
                # Process workflows
                for workflow_data in project_data.get("workflows", []):
                    try:
                        workflow = WorkflowDB(
                            id=str(uuid.uuid4()),
                            name=workflow_data.get("name", "Imported Workflow"),
                            description=workflow_data.get("description", ""),
                            trigger=workflow_data.get("trigger", {"type": "manual"}),
                            steps=workflow_data.get("steps", []),
                            created_by=user_id,
                            created_at=datetime.fromisoformat(workflow_data.get("created_at", datetime.utcnow().isoformat())),
                            metadata=workflow_data.get("metadata", {})
                        )
                        db.add(workflow)
                        stats["workflows_created"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Failed to create workflow: {e}")
                
                # Process knowledge entries
                for knowledge_data in project_data.get("knowledge", []):
                    try:
                        entry = KnowledgeEntryDB(
                            id=str(uuid.uuid4()),
                            title=knowledge_data.get("title", "Imported Knowledge"),
                            content=knowledge_data.get("content", ""),
                            type=knowledge_data.get("type", "reference"),
                            category=knowledge_data.get("category", "imported"),
                            tags=knowledge_data.get("tags", []) + ["imported"],
                            source=knowledge_data.get("source", "project_import"),
                            created_by=user_id,
                            created_at=datetime.fromisoformat(knowledge_data.get("created_at", datetime.utcnow().isoformat())),
                            metadata=knowledge_data.get("metadata", {})
                        )
                        db.add(entry)
                        
                        # Index for RAG
                        await self.rag_service.index_knowledge_entry(entry)
                        stats["knowledge_entries_created"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Failed to create knowledge entry: {e}")
                
                await db.commit()
            
            logger.info(f"Project data ingestion completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to ingest project data: {e}")
            return {"error": str(e)}
    
    async def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        try:
            async with get_db() as db:
                # Count records
                knowledge_count = await db.scalar(select(func.count(KnowledgeEntryDB.id)))
                indexed_knowledge = await db.scalar(select(func.count(KnowledgeEntryDB.id)).where(KnowledgeEntryDB.embedding.is_not(None)))
                
                message_count = await db.scalar(select(func.count(AssistantMessageDB.id)))
                indexed_messages = await db.scalar(select(func.count(AssistantMessageDB.id)).where(AssistantMessageDB.embedding.is_not(None)))
                
                file_count = await db.scalar(select(func.count(FileMetadataDB.id)))
                task_count = await db.scalar(select(func.count(TaskDB.id)))
                workflow_count = await db.scalar(select(func.count(WorkflowDB.id)))
                
                return {
                    "knowledge_entries": {
                        "total": knowledge_count,
                        "indexed": indexed_knowledge,
                        "index_percentage": (indexed_knowledge / knowledge_count * 100) if knowledge_count > 0 else 0
                    },
                    "messages": {
                        "total": message_count,
                        "indexed": indexed_messages,
                        "index_percentage": (indexed_messages / message_count * 100) if message_count > 0 else 0
                    },
                    "files": file_count,
                    "tasks": task_count,
                    "workflows": workflow_count,
                    "total_indexed_items": indexed_knowledge + indexed_messages
                }
                
        except Exception as e:
            logger.error(f"Failed to get ingestion stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check data ingestion service health."""
        try:
            rag_health = await self.rag_service.health_check()
            
            return {
                "status": "healthy",
                "supported_formats": list(self.supported_formats.keys()),
                "rag_service": rag_health.get("status", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Data ingestion service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }