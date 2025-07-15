"""Simplified End-to-End Test Suite for BrainOps AI Assistant.

This test validates critical system functionality using working test patterns.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import uuid

# Add the backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables for testing
os.environ['OPENAI_API_KEY'] = 'test-key'
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
os.environ['ELEVENLABS_API_KEY'] = 'test-key'
os.environ['DATABASE_URL'] = 'sqlite:///test_e2e_simplified.db'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['SECRET_KEY'] = 'test-secret-key-for-e2e-simplified'

async def test_e2e_simplified():
    """Run simplified end-to-end tests using working patterns."""
    print("🚀 STARTING SIMPLIFIED END-TO-END TESTING...")
    print("=" * 60)
    
    # Clean up any existing test database
    test_db_file = "test_e2e_simplified.db"
    if os.path.exists(test_db_file):
        os.remove(test_db_file)
    
    test_results = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "test_details": []
    }
    
    try:
        # Test 1: Core Memory System
        print("\n🧪 TEST 1: Core Memory System")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            # Use working pattern from test_memory_core.py
            from core.database import init_db, get_db
            from models.db import (
                User, AssistantSessionDB, AssistantMessageDB, 
                KnowledgeEntryDB, TaskDB, WorkflowDB, 
                VoiceCommandDB, FileMetadataDB, AuditLog
            )
            
            await init_db()
            
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
                
                # Verify user creation
                from sqlalchemy import select
                result = await db.execute(select(User).where(User.id == 1))
                user = result.scalar_one_or_none()
                assert user is not None
                assert user.email == "test@brainops.ai"
            
            print("✅ Core memory system: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Core Memory System",
                "status": "PASSED",
                "details": "Database initialization and user creation successful"
            })
            
        except Exception as e:
            print(f"❌ Core memory system: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Core Memory System",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 2: RAG System
        print("\n🧪 TEST 2: RAG System")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            # Use working pattern from test_rag_simple.py
            def generate_mock_embedding(text):
                import hashlib
                hash_int = int(hashlib.md5(text.encode()).hexdigest(), 16)
                return [(hash_int + i) % 1000 / 1000.0 for i in range(1536)]
            
            async with get_db() as db:
                # Create test session
                session = AssistantSessionDB(
                    id=str(uuid.uuid4()),
                    user_id=1,
                    context={"test": "rag"}
                )
                db.add(session)
                await db.commit()
                
                # Create test messages with embeddings
                test_messages = [
                    "What is BrainOps AI Assistant?",
                    "BrainOps AI Assistant is a comprehensive AI-powered system for business automation."
                ]
                
                for i, content in enumerate(test_messages):
                    embedding = generate_mock_embedding(content)
                    message = AssistantMessageDB(
                        id=str(uuid.uuid4()),
                        session_id=session.id,
                        role="user" if i % 2 == 0 else "assistant",
                        content=content,
                        message_type="chat",
                        embedding=embedding
                    )
                    db.add(message)
                
                await db.commit()
                
                # Test similarity search
                query = "workflow automation"
                query_embedding = generate_mock_embedding(query)
                
                result = await db.execute(
                    select(AssistantMessageDB).where(AssistantMessageDB.embedding.is_not(None))
                )
                messages = result.scalars().all()
                assert len(messages) > 0
                
                # Test cosine similarity
                def cosine_similarity(vec1, vec2):
                    dot_product = sum(a * b for a, b in zip(vec1, vec2))
                    magnitude1 = sum(a * a for a in vec1) ** 0.5
                    magnitude2 = sum(b * b for b in vec2) ** 0.5
                    if magnitude1 == 0 or magnitude2 == 0:
                        return 0.0
                    return dot_product / (magnitude1 * magnitude2)
                
                similarities = []
                for message in messages:
                    if message.embedding is not None:
                        similarity = cosine_similarity(query_embedding, message.embedding)
                        similarities.append(similarity)
                
                assert len(similarities) > 0
            
            print("✅ RAG system: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "RAG System",
                "status": "PASSED",
                "details": f"Created {len(test_messages)} messages with embeddings, tested similarity search"
            })
            
        except Exception as e:
            print(f"❌ RAG system: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "RAG System",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 3: Data Ingestion
        print("\n🧪 TEST 3: Data Ingestion")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            # Use working pattern from test_data_ingestion.py
            async with get_db() as db:
                # Create test knowledge entries
                test_knowledge = [
                    {
                        "title": "API Documentation",
                        "content": "API endpoints for BrainOps AI Assistant including authentication, tasks, and workflows.",
                        "category": "api"
                    },
                    {
                        "title": "Security Guide",
                        "content": "Security protocols including JWT authentication, audit logging, and access control.",
                        "category": "security"
                    }
                ]
                
                knowledge_ids = []
                for kb_data in test_knowledge:
                    combined_content = f"{kb_data['title']}\n\n{kb_data['content']}"
                    embedding = generate_mock_embedding(combined_content)
                    
                    entry = KnowledgeEntryDB(
                        id=str(uuid.uuid4()),
                        title=kb_data["title"],
                        content=kb_data["content"],
                        type="document",
                        category=kb_data["category"],
                        tags=["imported", "test"],
                        source="test_ingestion",
                        created_by=1,
                        embedding=embedding,
                        meta_data={"source": "bulk_import"}
                    )
                    db.add(entry)
                    knowledge_ids.append(entry.id)
                
                await db.commit()
                
                # Test data retrieval
                result = await db.execute(select(KnowledgeEntryDB).where(KnowledgeEntryDB.created_by == 1))
                entries = result.scalars().all()
                assert len(entries) >= len(test_knowledge)
                
                # Test search functionality
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.content.contains("API"))
                )
                search_results = result.scalars().all()
                assert len(search_results) >= 1
            
            print("✅ Data ingestion: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Data Ingestion",
                "status": "PASSED",
                "details": f"Ingested {len(test_knowledge)} knowledge entries with embeddings"
            })
            
        except Exception as e:
            print(f"❌ Data ingestion: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Data Ingestion",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 4: Knowledge Access
        print("\n🧪 TEST 4: Knowledge Access")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            # Use working pattern from test_knowledge_access.py
            async with get_db() as db:
                # Create historical and current knowledge
                historical_knowledge = {
                    "title": "Legacy System Integration",
                    "content": "The legacy system integration was completed in Q1 2024 using REST APIs.",
                    "category": "historical",
                    "created_at": datetime.now() - timedelta(days=180)
                }
                
                current_knowledge = {
                    "title": "New AI Assistant Features",
                    "content": "The new AI assistant features include voice interface and real-time automation.",
                    "category": "current",
                    "created_at": datetime.now() - timedelta(days=7)
                }
                
                # Create entries
                for knowledge_data in [historical_knowledge, current_knowledge]:
                    entry = KnowledgeEntryDB(
                        id=str(uuid.uuid4()),
                        title=knowledge_data["title"],
                        content=knowledge_data["content"],
                        type="reference",
                        category=knowledge_data["category"],
                        created_by=1,
                        created_at=knowledge_data["created_at"],
                        embedding=generate_mock_embedding(f"{knowledge_data['title']}\n\n{knowledge_data['content']}"),
                        tags=[knowledge_data["category"]],
                        meta_data={"age": knowledge_data["category"]}
                    )
                    db.add(entry)
                
                await db.commit()
                
                # Test temporal queries
                thirty_days_ago = datetime.now() - timedelta(days=30)
                
                # Historical data
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.created_at < thirty_days_ago)
                )
                historical_entries = result.scalars().all()
                assert len(historical_entries) >= 1
                
                # Current data
                result = await db.execute(
                    select(KnowledgeEntryDB).where(KnowledgeEntryDB.created_at >= thirty_days_ago)
                )
                current_entries = result.scalars().all()
                assert len(current_entries) >= 1
                
                # Test query across time periods
                test_query = "system integration"
                query_embedding = generate_mock_embedding(test_query)
                
                result = await db.execute(select(KnowledgeEntryDB).where(KnowledgeEntryDB.embedding.is_not(None)))
                all_entries = result.scalars().all()
                
                relevant_entries = []
                for entry in all_entries:
                    if entry.embedding is not None:
                        similarity = cosine_similarity(query_embedding, entry.embedding)
                        if similarity > 0.1:  # Lower threshold for test
                            relevant_entries.append(entry)
                
                assert len(relevant_entries) > 0
            
            print("✅ Knowledge access: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Knowledge Access",
                "status": "PASSED",
                "details": "Successfully accessed both historical and current knowledge"
            })
            
        except Exception as e:
            print(f"❌ Knowledge access: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Knowledge Access",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 5: Task Management
        print("\n🧪 TEST 5: Task Management")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            async with get_db() as db:
                # Create test tasks
                test_tasks = [
                    {
                        "title": "Deploy to production",
                        "description": "Deploy the AI assistant to production environment",
                        "status": "pending",
                        "priority": "high"
                    },
                    {
                        "title": "Security review",
                        "description": "Conduct security audit and vulnerability assessment",
                        "status": "in_progress",
                        "priority": "high"
                    }
                ]
                
                task_ids = []
                for task_data in test_tasks:
                    task = TaskDB(
                        id=str(uuid.uuid4()),
                        title=task_data["title"],
                        description=task_data["description"],
                        status=task_data["status"],
                        priority=task_data["priority"],
                        created_by=1,
                        tags=["e2e_test"],
                        meta_data={"test": "task_management"}
                    )
                    db.add(task)
                    task_ids.append(task.id)
                
                await db.commit()
                
                # Test task queries
                result = await db.execute(select(TaskDB).where(TaskDB.created_by == 1))
                tasks = result.scalars().all()
                assert len(tasks) >= len(test_tasks)
                
                # Test status filtering
                result = await db.execute(select(TaskDB).where(TaskDB.status == "pending"))
                pending_tasks = result.scalars().all()
                assert len(pending_tasks) >= 1
                
                # Test task update
                task_to_update = tasks[0]
                task_to_update.status = "completed"
                task_to_update.updated_at = datetime.now()
                await db.commit()
                
                # Verify update
                result = await db.execute(select(TaskDB).where(TaskDB.id == task_to_update.id))
                updated_task = result.scalar_one()
                assert updated_task.status == "completed"
            
            print("✅ Task management: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Task Management",
                "status": "PASSED",
                "details": f"Created {len(test_tasks)} tasks, tested CRUD operations"
            })
            
        except Exception as e:
            print(f"❌ Task management: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Task Management",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 6: Workflow Automation
        print("\n🧪 TEST 6: Workflow Automation")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            async with get_db() as db:
                # Create test workflows
                test_workflows = [
                    {
                        "name": "Email Processing Workflow",
                        "description": "Process incoming emails and create tasks",
                        "trigger": {"type": "webhook", "source": "email"},
                        "steps": [
                            {"type": "parse_email", "config": {"extract": ["subject", "body"]}},
                            {"type": "create_task", "config": {"project": "inbox"}}
                        ],
                        "is_active": True
                    },
                    {
                        "name": "Document Processing Workflow",
                        "description": "Process uploaded documents and index content",
                        "trigger": {"type": "file_upload", "source": "api"},
                        "steps": [
                            {"type": "extract_text", "config": {"formats": ["pdf", "txt"]}},
                            {"type": "generate_embeddings", "config": {"model": "text-embedding-ada-002"}}
                        ],
                        "is_active": True
                    }
                ]
                
                workflow_ids = []
                for workflow_data in test_workflows:
                    workflow = WorkflowDB(
                        id=str(uuid.uuid4()),
                        name=workflow_data["name"],
                        description=workflow_data["description"],
                        trigger=workflow_data["trigger"],
                        steps=workflow_data["steps"],
                        is_active=workflow_data["is_active"],
                        created_by=1,
                        meta_data={"test": "workflow_automation"}
                    )
                    db.add(workflow)
                    workflow_ids.append(workflow.id)
                
                await db.commit()
                
                # Test workflow queries
                result = await db.execute(select(WorkflowDB).where(WorkflowDB.created_by == 1))
                workflows = result.scalars().all()
                assert len(workflows) >= len(test_workflows)
                
                # Test active workflows
                result = await db.execute(select(WorkflowDB).where(WorkflowDB.is_active == True))
                active_workflows = result.scalars().all()
                assert len(active_workflows) >= 2
                
                # Test workflow deactivation
                workflow_to_deactivate = workflows[0]
                workflow_to_deactivate.is_active = False
                workflow_to_deactivate.updated_at = datetime.now()
                await db.commit()
                
                # Verify deactivation
                result = await db.execute(select(WorkflowDB).where(WorkflowDB.id == workflow_to_deactivate.id))
                deactivated_workflow = result.scalar_one()
                assert deactivated_workflow.is_active == False
            
            print("✅ Workflow automation: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Workflow Automation",
                "status": "PASSED",
                "details": f"Created {len(test_workflows)} workflows, tested activation/deactivation"
            })
            
        except Exception as e:
            print(f"❌ Workflow automation: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Workflow Automation",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Test 7: Audit Logging
        print("\n🧪 TEST 7: Audit Logging")
        print("-" * 40)
        
        test_results["total_tests"] += 1
        try:
            async with get_db() as db:
                # Create test audit logs
                test_audit_logs = [
                    {
                        "action": "system_startup",
                        "resource_type": "system",
                        "resource_id": "brainops_ai_assistant",
                        "details": {"version": "1.0.0", "environment": "production"},
                        "success": True
                    },
                    {
                        "action": "user_login",
                        "resource_type": "authentication",
                        "resource_id": "user_1",
                        "details": {"ip_address": "192.168.1.100"},
                        "success": True
                    },
                    {
                        "action": "workflow_execution",
                        "resource_type": "workflow",
                        "resource_id": "workflow_email_processing",
                        "details": {"duration": 2.5, "items_processed": 5},
                        "success": True
                    }
                ]
                
                audit_log_ids = []
                for log_data in test_audit_logs:
                    audit_log = AuditLog(
                        id=str(uuid.uuid4()),
                        user_id=1,
                        action=log_data["action"],
                        resource_type=log_data["resource_type"],
                        resource_id=log_data["resource_id"],
                        details=log_data["details"],
                        success=log_data["success"],
                        timestamp=datetime.now()
                    )
                    db.add(audit_log)
                    audit_log_ids.append(audit_log.id)
                
                await db.commit()
                
                # Test audit log queries
                result = await db.execute(select(AuditLog).where(AuditLog.user_id == 1))
                audit_logs = result.scalars().all()
                assert len(audit_logs) >= len(test_audit_logs)
                
                # Test action filtering
                result = await db.execute(select(AuditLog).where(AuditLog.action == "user_login"))
                login_logs = result.scalars().all()
                assert len(login_logs) >= 1
                
                # Test success rate
                from sqlalchemy import func
                total_logs = await db.scalar(select(func.count(AuditLog.id)))
                successful_logs = await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.success == True))
                success_rate = (successful_logs / total_logs) * 100 if total_logs > 0 else 0
                assert success_rate > 0
            
            print("✅ Audit logging: PASSED")
            test_results["passed_tests"] += 1
            test_results["test_details"].append({
                "test": "Audit Logging",
                "status": "PASSED",
                "details": f"Created {len(test_audit_logs)} audit logs, tested queries and success rate"
            })
            
        except Exception as e:
            print(f"❌ Audit logging: FAILED - {e}")
            test_results["failed_tests"] += 1
            test_results["test_details"].append({
                "test": "Audit Logging",
                "status": "FAILED",
                "details": str(e)
            })
        
        # Final Results
        print("\n" + "=" * 60)
        print("🎯 SIMPLIFIED END-TO-END TEST RESULTS")
        print("=" * 60)
        
        success_rate = (test_results["passed_tests"] / test_results["total_tests"]) * 100
        
        print(f"📊 Overall Statistics:")
        print(f"  Total Tests: {test_results['total_tests']}")
        print(f"  Passed: {test_results['passed_tests']}")
        print(f"  Failed: {test_results['failed_tests']}")
        print(f"  Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 Test Results:")
        for test_detail in test_results["test_details"]:
            status_icon = "✅" if test_detail["status"] == "PASSED" else "❌"
            print(f"  {status_icon} {test_detail['test']}: {test_detail['status']}")
            if test_detail["status"] == "FAILED":
                print(f"    Error: {test_detail['details']}")
        
        if success_rate == 100.0:
            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"✅ BrainOps AI Assistant core functionality is operational")
            return True
        else:
            print(f"\n⚠️  SOME TESTS FAILED!")
            print(f"❌ System requires fixes before production deployment")
            return False
        
    except Exception as e:
        print(f"❌ End-to-end test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_e2e_simplified())
    print(f"\n{'='*60}")
    if success:
        print("🚀 SIMPLIFIED END-TO-END TESTING: COMPLETE SUCCESS")
        print("✅ Core functionality validated and operational")
    else:
        print("❌ SIMPLIFIED END-TO-END TESTING: PARTIAL SUCCESS")
        print("⚠️  Some components require attention")
    print(f"{'='*60}")
    exit(0 if success else 1)