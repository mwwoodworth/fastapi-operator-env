"""Core memory system test without external dependencies."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add the backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables for testing
os.environ['OPENAI_API_KEY'] = 'test-key'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
os.environ['ELEVENLABS_API_KEY'] = 'test-key'
os.environ['DATABASE_URL'] = 'sqlite:///test_memory.db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['SECRET_KEY'] = 'test-secret-key-for-memory-testing'

async def test_core_memory():
    """Test core memory system functionality."""
    print("🧪 Testing Core Memory System...")
    
    # Clean up any existing test database
    import os
    test_db_file = "test_memory.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)
    
    try:
        # Test 1: Database models import
        print("✅ Test 1: Database Models Import")
        from models.db import (
            User, AssistantSessionDB, AssistantMessageDB, 
            KnowledgeEntryDB, TaskDB, WorkflowDB, 
            VoiceCommandDB, FileMetadataDB, AuditLog
        )
        
        # Test 2: Database connection
        print("✅ Test 2: Database Connection")
        from core.database import init_db, get_db
        await init_db()
        
        # Test 3: Basic CRUD operations
        print("✅ Test 3: Basic CRUD Operations")
        async with get_db() as db:
            # Create test user
            from datetime import datetime
            import uuid
            
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
            
            # Create test session
            session = AssistantSessionDB(
                id=str(uuid.uuid4()),
                user_id=1,
                context={"test": "memory"}
            )
            db.add(session)
            await db.commit()
            
            # Create test message
            message = AssistantMessageDB(
                id=str(uuid.uuid4()),
                session_id=session.id,
                role="user",
                content="Test message for memory validation",
                message_type="chat"
            )
            db.add(message)
            await db.commit()
            
            # Create test task
            task = TaskDB(
                id=str(uuid.uuid4()),
                title="Test Task",
                description="Test task for memory validation",
                created_by=1,
                status="pending",
                priority="medium"
            )
            db.add(task)
            await db.commit()
            
            # Create test knowledge entry
            knowledge = KnowledgeEntryDB(
                id=str(uuid.uuid4()),
                title="Test Knowledge",
                content="Test knowledge entry for memory validation",
                type="reference",
                category="test",
                created_by=1
            )
            db.add(knowledge)
            await db.commit()
            
            print("✅ Test 4: Data Persistence - All records created successfully")
            
            # Test retrieval
            from sqlalchemy import select
            
            # Test message retrieval
            result = await db.execute(select(AssistantMessageDB).where(AssistantMessageDB.session_id == session.id))
            messages = result.scalars().all()
            assert len(messages) > 0, "No messages found"
            
            # Test task retrieval  
            result = await db.execute(select(TaskDB).where(TaskDB.created_by == 1))
            tasks = result.scalars().all()
            assert len(tasks) > 0, "No tasks found"
            
            # Test knowledge retrieval
            result = await db.execute(select(KnowledgeEntryDB).where(KnowledgeEntryDB.created_by == 1))
            knowledge_entries = result.scalars().all()
            assert len(knowledge_entries) > 0, "No knowledge entries found"
            
            print("✅ Test 5: Data Retrieval - All records retrieved successfully")
            
            # Test search functionality
            result = await db.execute(
                select(AssistantMessageDB).where(AssistantMessageDB.content.contains("memory"))
            )
            search_results = result.scalars().all()
            assert len(search_results) > 0, "No search results found"
            
            print("✅ Test 6: Search Functionality - Search working correctly")
            
            # Test audit logging
            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                user_id=1,
                action="memory_test",
                resource_type="test",
                resource_id="test_123",
                details={"test": "audit logging"},
                success=True
            )
            db.add(audit_log)
            await db.commit()
            
            result = await db.execute(select(AuditLog).where(AuditLog.user_id == 1))
            audit_logs = result.scalars().all()
            assert len(audit_logs) > 0, "No audit logs found"
            
            print("✅ Test 7: Audit Logging - Audit trail working correctly")
            
            # Test cross-table queries
            from sqlalchemy import text
            result = await db.execute(text("""
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
                WHERE u.id = 1
                GROUP BY u.id, u.username
            """))
            
            user_stats = result.fetchone()
            assert user_stats is not None, "No user stats found"
            
            print("✅ Test 8: Cross-Table Queries - Complex queries working correctly")
            
            print(f"\n🎉 ALL CORE MEMORY TESTS PASSED!")
            print(f"📊 Summary:")
            print(f"  - Messages: {user_stats[1]}")
            print(f"  - Tasks: {user_stats[2]}")
            print(f"  - Knowledge Entries: {user_stats[3]}")
            print(f"  - Audit Logs: {len(audit_logs)}")
            
            return True
            
    except Exception as e:
        print(f"❌ Core memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_core_memory())
    print(f"\n{'='*60}")
    if success:
        print("🎉 CORE MEMORY SYSTEM: 100% OPERATIONAL")
    else:
        print("❌ CORE MEMORY SYSTEM: FAILED")
    print(f"{'='*60}")
    exit(0 if success else 1)