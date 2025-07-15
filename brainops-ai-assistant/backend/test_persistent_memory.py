"""Comprehensive test suite for persistent memory system validation."""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pytest
from sqlalchemy import select, func

from core.database import get_db, init_db
from models.db import (
    User, AssistantSessionDB, AssistantMessageDB, KnowledgeEntryDB,
    TaskDB, WorkflowDB, VoiceCommandDB, FileMetadataDB, AuditLog
)
from services.rag_service import RAGService
from services.data_ingestion_service import DataIngestionService
from services.embedding_service import EmbeddingService


class PersistentMemoryTestSuite:
    """Comprehensive test suite for persistent memory system."""
    
    def __init__(self):
        self.rag_service = RAGService()
        self.data_ingestion = DataIngestionService()
        self.embedding_service = EmbeddingService()
        self.test_user_id = None
        self.test_results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": [],
            "details": {}
        }
    
    async def initialize(self):
        """Initialize test suite."""
        await init_db()
        await self.rag_service.initialize()
        await self.data_ingestion.initialize()
        await self.embedding_service.initialize()
        
        # Create test user
        async with get_db() as db:
            test_user = User(
                id=1,
                email="test@brainops.ai",
                username="testuser",
                hashed_password="test_hash",
                full_name="Test User",
                is_active=True
            )
            db.add(test_user)
            await db.commit()
            self.test_user_id = test_user.id
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all persistent memory tests."""
        print("🧪 Starting Persistent Memory System Tests...")
        
        # Test 1: Database Connection and Tables
        await self._test_database_connectivity()
        
        # Test 2: Message Recording and Retrieval
        await self._test_message_recording()
        
        # Test 3: Task Recording and Retrieval
        await self._test_task_recording()
        
        # Test 4: File Operations Recording
        await self._test_file_operations_recording()
        
        # Test 5: Voice Command Recording
        await self._test_voice_command_recording()
        
        # Test 6: Knowledge Base Operations
        await self._test_knowledge_base_operations()
        
        # Test 7: Vector Search and RAG
        await self._test_vector_search_rag()
        
        # Test 8: Audit Logging
        await self._test_audit_logging()
        
        # Test 9: Cross-Reference Queries
        await self._test_cross_reference_queries()
        
        # Test 10: Data Persistence After Restart
        await self._test_data_persistence()
        
        return self.test_results
    
    async def _test_database_connectivity(self):
        """Test database connectivity and table structure."""
        test_name = "Database Connectivity"
        try:
            async with get_db() as db:
                # Test basic connectivity
                result = await db.execute("SELECT 1")
                assert result.scalar() == 1
                
                # Test pgvector extension
                result = await db.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                vector_enabled = result.scalar() is not None
                
                # Test table existence
                tables = [
                    "users", "assistant_sessions", "assistant_messages",
                    "knowledge_entries", "tasks", "workflows", "voice_commands",
                    "file_metadata", "audit_logs"
                ]
                
                for table in tables:
                    result = await db.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'")
                    assert result.scalar() == 1, f"Table {table} does not exist"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "vector_extension": vector_enabled,
                    "tables_verified": len(tables)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_message_recording(self):
        """Test message recording and retrieval."""
        test_name = "Message Recording"
        try:
            async with get_db() as db:
                # Create test session
                session = AssistantSessionDB(
                    id=str(uuid.uuid4()),
                    user_id=self.test_user_id,
                    context={"test": "message_recording"}
                )
                db.add(session)
                await db.commit()
                
                # Create test messages
                messages = [
                    {
                        "role": "user",
                        "content": "What is the weather like today?",
                        "message_type": "chat"
                    },
                    {
                        "role": "assistant",
                        "content": "I'd be happy to help you with weather information. Could you please specify your location?",
                        "message_type": "chat"
                    },
                    {
                        "role": "user",
                        "content": "Create a task to review the quarterly report",
                        "message_type": "command"
                    }
                ]
                
                message_ids = []
                for msg_data in messages:
                    message = AssistantMessageDB(
                        id=str(uuid.uuid4()),
                        session_id=session.id,
                        role=msg_data["role"],
                        content=msg_data["content"],
                        message_type=msg_data["message_type"],
                        metadata={"test": True}
                    )
                    db.add(message)
                    message_ids.append(message.id)
                
                await db.commit()
                
                # Test retrieval
                retrieved_messages = await db.execute(
                    select(AssistantMessageDB).where(AssistantMessageDB.session_id == session.id)
                )
                messages_list = retrieved_messages.scalars().all()
                
                assert len(messages_list) == 3, f"Expected 3 messages, got {len(messages_list)}"
                
                # Test indexing
                for message in messages_list:
                    await self.rag_service.index_message(message)
                
                # Test search
                search_results = await self.rag_service.search_conversations(
                    "weather", self.test_user_id, limit=5
                )
                
                assert len(search_results) > 0, "No search results found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "messages_created": len(messages_list),
                    "search_results": len(search_results)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_task_recording(self):
        """Test task recording and retrieval."""
        test_name = "Task Recording"
        try:
            async with get_db() as db:
                # Create test tasks
                tasks = [
                    {
                        "title": "Review quarterly financial report",
                        "description": "Analyze Q3 financial performance and identify key trends",
                        "status": "pending",
                        "priority": "high",
                        "tags": ["finance", "quarterly", "analysis"]
                    },
                    {
                        "title": "Update project documentation",
                        "description": "Ensure all project docs are current and comprehensive",
                        "status": "in_progress",
                        "priority": "medium",
                        "tags": ["documentation", "project"]
                    },
                    {
                        "title": "Schedule team meeting",
                        "description": "Coordinate with team members for weekly sync",
                        "status": "completed",
                        "priority": "low",
                        "tags": ["meeting", "coordination"]
                    }
                ]
                
                task_ids = []
                for task_data in tasks:
                    task = TaskDB(
                        id=str(uuid.uuid4()),
                        title=task_data["title"],
                        description=task_data["description"],
                        status=task_data["status"],
                        priority=task_data["priority"],
                        created_by=self.test_user_id,
                        tags=task_data["tags"],
                        metadata={"test": True}
                    )
                    db.add(task)
                    task_ids.append(task.id)
                
                await db.commit()
                
                # Test retrieval
                retrieved_tasks = await db.execute(
                    select(TaskDB).where(TaskDB.created_by == self.test_user_id)
                )
                tasks_list = retrieved_tasks.scalars().all()
                
                assert len(tasks_list) >= 3, f"Expected at least 3 tasks, got {len(tasks_list)}"
                
                # Test filtering
                high_priority_tasks = await db.execute(
                    select(TaskDB).where(
                        TaskDB.created_by == self.test_user_id,
                        TaskDB.priority == "high"
                    )
                )
                high_priority_list = high_priority_tasks.scalars().all()
                
                assert len(high_priority_list) >= 1, "No high priority tasks found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "tasks_created": len(tasks_list),
                    "high_priority_tasks": len(high_priority_list)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_file_operations_recording(self):
        """Test file operations recording."""
        test_name = "File Operations Recording"
        try:
            async with get_db() as db:
                # Create test file metadata
                files = [
                    {
                        "path": "/test/documents/quarterly_report.pdf",
                        "filename": "quarterly_report.pdf",
                        "size_bytes": 1024576,
                        "mime_type": "application/pdf",
                        "tags": ["finance", "quarterly", "report"]
                    },
                    {
                        "path": "/test/documents/meeting_notes.md",
                        "filename": "meeting_notes.md",
                        "size_bytes": 5120,
                        "mime_type": "text/markdown",
                        "tags": ["meeting", "notes"]
                    },
                    {
                        "path": "/test/code/automation_script.py",
                        "filename": "automation_script.py",
                        "size_bytes": 8192,
                        "mime_type": "text/x-python",
                        "tags": ["code", "automation", "python"]
                    }
                ]
                
                file_ids = []
                for file_data in files:
                    file_metadata = FileMetadataDB(
                        id=str(uuid.uuid4()),
                        path=file_data["path"],
                        filename=file_data["filename"],
                        size_bytes=file_data["size_bytes"],
                        mime_type=file_data["mime_type"],
                        created_by=self.test_user_id,
                        tags=file_data["tags"],
                        metadata={"test": True}
                    )
                    db.add(file_metadata)
                    file_ids.append(file_metadata.id)
                
                await db.commit()
                
                # Test retrieval
                retrieved_files = await db.execute(
                    select(FileMetadataDB).where(FileMetadataDB.created_by == self.test_user_id)
                )
                files_list = retrieved_files.scalars().all()
                
                assert len(files_list) >= 3, f"Expected at least 3 files, got {len(files_list)}"
                
                # Test filtering by mime type
                pdf_files = await db.execute(
                    select(FileMetadataDB).where(
                        FileMetadataDB.created_by == self.test_user_id,
                        FileMetadataDB.mime_type == "application/pdf"
                    )
                )
                pdf_list = pdf_files.scalars().all()
                
                assert len(pdf_list) >= 1, "No PDF files found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "files_created": len(files_list),
                    "pdf_files": len(pdf_list)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_voice_command_recording(self):
        """Test voice command recording."""
        test_name = "Voice Command Recording"
        try:
            async with get_db() as db:
                # Create test voice commands
                commands = [
                    {
                        "transcript": "Create a new task for reviewing the budget",
                        "confidence": 0.95,
                        "intent": "task_creation",
                        "entities": {"action": "create", "object": "task", "topic": "budget"}
                    },
                    {
                        "transcript": "Show me the latest financial reports",
                        "confidence": 0.88,
                        "intent": "file_query",
                        "entities": {"action": "show", "object": "reports", "type": "financial"}
                    },
                    {
                        "transcript": "Schedule a meeting with the development team",
                        "confidence": 0.92,
                        "intent": "scheduling",
                        "entities": {"action": "schedule", "object": "meeting", "participants": "development team"}
                    }
                ]
                
                command_ids = []
                for cmd_data in commands:
                    command = VoiceCommandDB(
                        id=str(uuid.uuid4()),
                        user_id=self.test_user_id,
                        transcript=cmd_data["transcript"],
                        confidence=cmd_data["confidence"],
                        intent=cmd_data["intent"],
                        entities=cmd_data["entities"],
                        processed_at=datetime.utcnow(),
                        processing_time_ms=250.0
                    )
                    db.add(command)
                    command_ids.append(command.id)
                
                await db.commit()
                
                # Test retrieval
                retrieved_commands = await db.execute(
                    select(VoiceCommandDB).where(VoiceCommandDB.user_id == self.test_user_id)
                )
                commands_list = retrieved_commands.scalars().all()
                
                assert len(commands_list) >= 3, f"Expected at least 3 commands, got {len(commands_list)}"
                
                # Test filtering by confidence
                high_confidence_commands = await db.execute(
                    select(VoiceCommandDB).where(
                        VoiceCommandDB.user_id == self.test_user_id,
                        VoiceCommandDB.confidence > 0.9
                    )
                )
                high_confidence_list = high_confidence_commands.scalars().all()
                
                assert len(high_confidence_list) >= 1, "No high confidence commands found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "commands_created": len(commands_list),
                    "high_confidence_commands": len(high_confidence_list)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_knowledge_base_operations(self):
        """Test knowledge base operations."""
        test_name = "Knowledge Base Operations"
        try:
            async with get_db() as db:
                # Create test knowledge entries
                entries = [
                    {
                        "title": "BrainOps Company Overview",
                        "content": "BrainOps is an AI-driven business automation company specializing in workflow optimization and intelligent process automation.",
                        "type": "reference",
                        "category": "company",
                        "tags": ["brainops", "overview", "automation"]
                    },
                    {
                        "title": "API Documentation Standards",
                        "content": "All API endpoints must follow REST principles, include proper authentication, and provide comprehensive documentation.",
                        "type": "procedure",
                        "category": "development",
                        "tags": ["api", "documentation", "standards"]
                    },
                    {
                        "title": "Security Best Practices",
                        "content": "Implement encryption, use secure authentication, validate all inputs, and maintain audit logs for all operations.",
                        "type": "procedure",
                        "category": "security",
                        "tags": ["security", "best-practices", "compliance"]
                    }
                ]
                
                entry_ids = []
                for entry_data in entries:
                    entry = KnowledgeEntryDB(
                        id=str(uuid.uuid4()),
                        title=entry_data["title"],
                        content=entry_data["content"],
                        type=entry_data["type"],
                        category=entry_data["category"],
                        tags=entry_data["tags"],
                        created_by=self.test_user_id,
                        metadata={"test": True}
                    )
                    db.add(entry)
                    entry_ids.append(entry.id)
                
                await db.commit()
                
                # Test indexing
                retrieved_entries = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.created_by == self.test_user_id)
                )
                entries_list = retrieved_entries.scalars().all()
                
                for entry in entries_list:
                    await self.rag_service.index_knowledge_entry(entry)
                
                # Test search
                search_results = await self.rag_service.search_knowledge_base(
                    "automation", category="company", limit=5
                )
                
                assert len(search_results) > 0, "No knowledge base search results found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "entries_created": len(entries_list),
                    "search_results": len(search_results)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_vector_search_rag(self):
        """Test vector search and RAG functionality."""
        test_name = "Vector Search and RAG"
        try:
            # Test contextual information retrieval
            context = await self.rag_service.get_contextual_information(
                "automation best practices", self.test_user_id
            )
            
            assert "sources" in context, "No sources in context"
            assert len(context["sources"]) > 0, "No contextual sources found"
            
            # Test contextual response generation
            response = await self.rag_service.generate_contextual_response(
                "What are the security best practices for API development?",
                self.test_user_id,
                context
            )
            
            assert "response" in response, "No response generated"
            assert len(response["response"]) > 0, "Empty response generated"
            
            self.test_results["details"][test_name] = {
                "status": "PASSED",
                "context_sources": len(context["sources"]),
                "response_length": len(response["response"])
            }
            self.test_results["tests_passed"] += 1
            print(f"✅ {test_name} - PASSED")
            
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_audit_logging(self):
        """Test audit logging functionality."""
        test_name = "Audit Logging"
        try:
            async with get_db() as db:
                # Create test audit logs
                logs = [
                    {
                        "action": "file_upload",
                        "resource_type": "file",
                        "resource_id": "test_file_123",
                        "details": {"filename": "test.pdf", "size": 1024}
                    },
                    {
                        "action": "task_created",
                        "resource_type": "task",
                        "resource_id": "task_456",
                        "details": {"title": "Review documentation", "priority": "high"}
                    },
                    {
                        "action": "workflow_executed",
                        "resource_type": "workflow",
                        "resource_id": "workflow_789",
                        "details": {"name": "Email notification", "status": "completed"}
                    }
                ]
                
                log_ids = []
                for log_data in logs:
                    audit_log = AuditLog(
                        id=str(uuid.uuid4()),
                        user_id=self.test_user_id,
                        action=log_data["action"],
                        resource_type=log_data["resource_type"],
                        resource_id=log_data["resource_id"],
                        details=log_data["details"],
                        success=True,
                        ip_address="127.0.0.1",
                        user_agent="test_agent"
                    )
                    db.add(audit_log)
                    log_ids.append(audit_log.id)
                
                await db.commit()
                
                # Test retrieval
                retrieved_logs = await db.execute(
                    select(AuditLog).where(AuditLog.user_id == self.test_user_id)
                )
                logs_list = retrieved_logs.scalars().all()
                
                assert len(logs_list) >= 3, f"Expected at least 3 audit logs, got {len(logs_list)}"
                
                # Test filtering by action
                file_logs = await db.execute(
                    select(AuditLog).where(
                        AuditLog.user_id == self.test_user_id,
                        AuditLog.action == "file_upload"
                    )
                )
                file_logs_list = file_logs.scalars().all()
                
                assert len(file_logs_list) >= 1, "No file upload logs found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "logs_created": len(logs_list),
                    "file_logs": len(file_logs_list)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_cross_reference_queries(self):
        """Test cross-reference queries across data types."""
        test_name = "Cross-Reference Queries"
        try:
            async with get_db() as db:
                # Test complex query joining multiple tables
                result = await db.execute("""
                    SELECT 
                        u.username,
                        COUNT(DISTINCT am.id) as message_count,
                        COUNT(DISTINCT t.id) as task_count,
                        COUNT(DISTINCT ke.id) as knowledge_count
                    FROM users u
                    LEFT JOIN assistant_sessions s ON u.id = s.user_id
                    LEFT JOIN assistant_messages am ON s.id = am.session_id
                    LEFT JOIN tasks t ON u.id = t.created_by
                    LEFT JOIN knowledge_entries ke ON u.id = ke.created_by
                    WHERE u.id = :user_id
                    GROUP BY u.id, u.username
                """, {"user_id": self.test_user_id})
                
                user_stats = result.fetchone()
                assert user_stats is not None, "No user stats found"
                
                # Test recent activity query
                result = await db.execute("""
                    SELECT 
                        'message' as type,
                        am.timestamp as created_at,
                        am.content as description
                    FROM assistant_messages am
                    JOIN assistant_sessions s ON am.session_id = s.id
                    WHERE s.user_id = :user_id
                    UNION ALL
                    SELECT 
                        'task' as type,
                        t.created_at,
                        t.title as description
                    FROM tasks t
                    WHERE t.created_by = :user_id
                    ORDER BY created_at DESC
                    LIMIT 10
                """, {"user_id": self.test_user_id})
                
                recent_activity = result.fetchall()
                assert len(recent_activity) > 0, "No recent activity found"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "message_count": user_stats[1],
                    "task_count": user_stats[2],
                    "knowledge_count": user_stats[3],
                    "recent_activity_items": len(recent_activity)
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def _test_data_persistence(self):
        """Test data persistence across sessions."""
        test_name = "Data Persistence"
        try:
            async with get_db() as db:
                # Count all data created during tests
                message_count = await db.scalar(
                    select(func.count(AssistantMessageDB.id))
                    .join(AssistantSessionDB)
                    .where(AssistantSessionDB.user_id == self.test_user_id)
                )
                
                task_count = await db.scalar(
                    select(func.count(TaskDB.id))
                    .where(TaskDB.created_by == self.test_user_id)
                )
                
                knowledge_count = await db.scalar(
                    select(func.count(KnowledgeEntryDB.id))
                    .where(KnowledgeEntryDB.created_by == self.test_user_id)
                )
                
                file_count = await db.scalar(
                    select(func.count(FileMetadataDB.id))
                    .where(FileMetadataDB.created_by == self.test_user_id)
                )
                
                voice_count = await db.scalar(
                    select(func.count(VoiceCommandDB.id))
                    .where(VoiceCommandDB.user_id == self.test_user_id)
                )
                
                audit_count = await db.scalar(
                    select(func.count(AuditLog.id))
                    .where(AuditLog.user_id == self.test_user_id)
                )
                
                # Verify all data is persistent
                assert message_count > 0, "Messages not persisted"
                assert task_count > 0, "Tasks not persisted"
                assert knowledge_count > 0, "Knowledge entries not persisted"
                assert file_count > 0, "File metadata not persisted"
                assert voice_count > 0, "Voice commands not persisted"
                assert audit_count > 0, "Audit logs not persisted"
                
                self.test_results["details"][test_name] = {
                    "status": "PASSED",
                    "total_records": {
                        "messages": message_count,
                        "tasks": task_count,
                        "knowledge": knowledge_count,
                        "files": file_count,
                        "voice_commands": voice_count,
                        "audit_logs": audit_count
                    }
                }
                self.test_results["tests_passed"] += 1
                print(f"✅ {test_name} - PASSED")
                
        except Exception as e:
            self.test_results["tests_failed"] += 1
            self.test_results["errors"].append(f"{test_name}: {str(e)}")
            self.test_results["details"][test_name] = {"status": "FAILED", "error": str(e)}
            print(f"❌ {test_name} - FAILED: {e}")
    
    def print_summary(self):
        """Print test summary."""
        total_tests = self.test_results["tests_passed"] + self.test_results["tests_failed"]
        success_rate = (self.test_results["tests_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"🧪 PERSISTENT MEMORY SYSTEM TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.test_results['tests_passed']} ✅")
        print(f"Failed: {self.test_results['tests_failed']} ❌")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.test_results["errors"]:
            print(f"\n❌ ERRORS:")
            for error in self.test_results["errors"]:
                print(f"  - {error}")
        
        if success_rate == 100:
            print(f"\n🎉 ALL TESTS PASSED! Persistent memory system is 100% operational.")
        else:
            print(f"\n⚠️  Some tests failed. Review errors above.")
        
        return success_rate == 100


async def main():
    """Run all persistent memory tests."""
    test_suite = PersistentMemoryTestSuite()
    
    try:
        await test_suite.initialize()
        results = await test_suite.run_all_tests()
        success = test_suite.print_summary()
        
        # Save results
        with open("persistent_memory_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        return success
        
    except Exception as e:
        print(f"❌ Test suite failed to initialize: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)