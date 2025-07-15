"""Task and project management service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union

from loguru import logger
from sqlalchemy import select, desc, and_, or_, func
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.config import settings
from models.db import TaskDB, User
from models.assistant import Task
from utils.audit import AuditLogger


class TaskManager:
    """Comprehensive task and project management system."""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.task_cache: Dict[str, Task] = {}
        self.cache_ttl = timedelta(minutes=15)
    
    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        status: str = "pending",
        priority: str = "medium",
        assigned_to: Optional[str] = None,
        created_by: int = 1,
        due_date: Optional[datetime] = None,
        tags: List[str] = None,
        dependencies: List[str] = None,
        parent_task_id: Optional[str] = None
    ) -> Task:
        """Create a new task."""
        try:
            task_id = str(uuid.uuid4())
            
            # Create database task
            db_task = TaskDB(
                id=task_id,
                title=title,
                description=description,
                status=status,
                priority=priority,
                assigned_to=assigned_to,
                created_by=created_by,
                due_date=due_date,
                tags=tags or [],
                dependencies=dependencies or [],
                metadata={}
            )
            
            async with get_db() as db:
                db.add(db_task)
                await db.commit()
                
                # Handle parent task relationship
                if parent_task_id:
                    await self._add_subtask(parent_task_id, task_id)
                
                # Log task creation
                await self.audit_logger.log_action(
                    user_id=created_by,
                    action="task_created",
                    resource_type="task",
                    resource_id=task_id,
                    details={
                        "title": title,
                        "priority": priority,
                        "assigned_to": assigned_to
                    }
                )
                
                # Convert to domain model
                task = self._db_to_domain(db_task)
                
                # Cache task
                self.task_cache[task_id] = task
                
                logger.info(f"Created task {task_id}: {title}")
                return task
                
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        try:
            # Check cache first
            if task_id in self.task_cache:
                return self.task_cache[task_id]
            
            async with get_db() as db:
                result = await db.execute(
                    select(TaskDB).where(TaskDB.id == task_id)
                )
                
                db_task = result.scalar_one_or_none()
                
                if not db_task:
                    return None
                
                # Convert to domain model
                task = self._db_to_domain(db_task)
                
                # Cache task
                self.task_cache[task_id] = task
                
                return task
                
        except Exception as e:
            logger.error(f"Error getting task {task_id}: {e}")
            return None
    
    async def update_task(
        self,
        task_id: str,
        updates: Dict[str, Any],
        updated_by: int = 1
    ) -> Optional[Task]:
        """Update a task."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(TaskDB).where(TaskDB.id == task_id)
                )
                
                db_task = result.scalar_one_or_none()
                
                if not db_task:
                    return None
                
                # Store original values for audit
                original_values = {
                    "status": db_task.status,
                    "priority": db_task.priority,
                    "assigned_to": db_task.assigned_to
                }
                
                # Apply updates
                for key, value in updates.items():
                    if hasattr(db_task, key):
                        setattr(db_task, key, value)
                
                # Update timestamp
                db_task.updated_at = datetime.utcnow()
                
                # Handle completion
                if updates.get("status") == "completed":
                    db_task.completed_at = datetime.utcnow()
                
                await db.commit()
                
                # Log update
                await self.audit_logger.log_action(
                    user_id=updated_by,
                    action="task_updated",
                    resource_type="task",
                    resource_id=task_id,
                    details={
                        "updates": updates,
                        "original_values": original_values
                    }
                )
                
                # Convert to domain model
                task = self._db_to_domain(db_task)
                
                # Update cache
                self.task_cache[task_id] = task
                
                logger.info(f"Updated task {task_id}")
                return task
                
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            raise
    
    async def delete_task(self, task_id: str, deleted_by: int = 1) -> bool:
        """Delete a task."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(TaskDB).where(TaskDB.id == task_id)
                )
                
                db_task = result.scalar_one_or_none()
                
                if not db_task:
                    return False
                
                # Remove from parent task's subtasks
                if db_task.metadata.get("parent_task_id"):
                    await self._remove_subtask(db_task.metadata["parent_task_id"], task_id)
                
                # Handle subtasks
                if db_task.subtasks:
                    for subtask_id in db_task.subtasks:
                        await self.delete_task(subtask_id, deleted_by)
                
                # Remove from cache
                self.task_cache.pop(task_id, None)
                
                # Delete from database
                await db.delete(db_task)
                await db.commit()
                
                # Log deletion
                await self.audit_logger.log_action(
                    user_id=deleted_by,
                    action="task_deleted",
                    resource_type="task",
                    resource_id=task_id,
                    details={
                        "title": db_task.title,
                        "status": db_task.status
                    }
                )
                
                logger.info(f"Deleted task {task_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            return False
    
    async def list_tasks(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        due_before: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[Task]:
        """List tasks with filtering and sorting."""
        try:
            async with get_db() as db:
                query = select(TaskDB)
                
                # Apply filters
                filters = []
                
                if user_id:
                    filters.append(TaskDB.created_by == user_id)
                
                if status:
                    filters.append(TaskDB.status == status)
                
                if priority:
                    filters.append(TaskDB.priority == priority)
                
                if assigned_to:
                    filters.append(TaskDB.assigned_to == assigned_to)
                
                if due_before:
                    filters.append(TaskDB.due_date <= due_before)
                
                if tags:
                    for tag in tags:
                        filters.append(TaskDB.tags.contains([tag]))
                
                if filters:
                    query = query.where(and_(*filters))
                
                # Apply sorting
                if sort_by and hasattr(TaskDB, sort_by):
                    order_column = getattr(TaskDB, sort_by)
                    if sort_order.lower() == "desc":
                        query = query.order_by(desc(order_column))
                    else:
                        query = query.order_by(order_column)
                
                # Apply pagination
                query = query.limit(limit).offset(offset)
                
                result = await db.execute(query)
                db_tasks = result.scalars().all()
                
                # Convert to domain models
                tasks = [self._db_to_domain(db_task) for db_task in db_tasks]
                
                return tasks
                
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return []
    
    async def get_task_dependencies(self, task_id: str) -> List[Task]:
        """Get all dependencies for a task."""
        try:
            task = await self.get_task(task_id)
            if not task or not task.dependencies:
                return []
            
            dependencies = []
            for dep_id in task.dependencies:
                dep_task = await self.get_task(dep_id)
                if dep_task:
                    dependencies.append(dep_task)
            
            return dependencies
            
        except Exception as e:
            logger.error(f"Error getting task dependencies: {e}")
            return []
    
    async def get_task_subtasks(self, task_id: str) -> List[Task]:
        """Get all subtasks for a task."""
        try:
            task = await self.get_task(task_id)
            if not task or not task.subtasks:
                return []
            
            subtasks = []
            for subtask_id in task.subtasks:
                subtask = await self.get_task(subtask_id)
                if subtask:
                    subtasks.append(subtask)
            
            return subtasks
            
        except Exception as e:
            logger.error(f"Error getting task subtasks: {e}")
            return []
    
    async def get_overdue_tasks(
        self,
        user_id: Optional[int] = None
    ) -> List[Task]:
        """Get overdue tasks."""
        now = datetime.utcnow()
        return await self.list_tasks(
            user_id=user_id,
            due_before=now,
            status="pending",
            sort_by="due_date",
            sort_order="asc"
        )
    
    async def get_upcoming_tasks(
        self,
        user_id: Optional[int] = None,
        days_ahead: int = 7
    ) -> List[Task]:
        """Get upcoming tasks."""
        now = datetime.utcnow()
        future_date = now + timedelta(days=days_ahead)
        
        return await self.list_tasks(
            user_id=user_id,
            due_before=future_date,
            status="pending",
            sort_by="due_date",
            sort_order="asc"
        )
    
    async def get_task_statistics(
        self,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get task statistics."""
        try:
            async with get_db() as db:
                base_query = select(TaskDB)
                
                if user_id:
                    base_query = base_query.where(TaskDB.created_by == user_id)
                
                # Total tasks
                total_result = await db.execute(
                    select(func.count(TaskDB.id)).select_from(base_query.subquery())
                )
                total_tasks = total_result.scalar()
                
                # Tasks by status
                status_result = await db.execute(
                    select(TaskDB.status, func.count(TaskDB.id))
                    .select_from(base_query.subquery())
                    .group_by(TaskDB.status)
                )
                
                status_counts = dict(status_result.fetchall())
                
                # Tasks by priority
                priority_result = await db.execute(
                    select(TaskDB.priority, func.count(TaskDB.id))
                    .select_from(base_query.subquery())
                    .group_by(TaskDB.priority)
                )
                
                priority_counts = dict(priority_result.fetchall())
                
                # Overdue tasks
                overdue_tasks = await self.get_overdue_tasks(user_id)
                
                # Completion rate
                completed_tasks = status_counts.get("completed", 0)
                completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
                
                return {
                    "total_tasks": total_tasks,
                    "by_status": status_counts,
                    "by_priority": priority_counts,
                    "overdue_count": len(overdue_tasks),
                    "completion_rate": completion_rate,
                    "pending_tasks": status_counts.get("pending", 0),
                    "in_progress_tasks": status_counts.get("in_progress", 0)
                }
                
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {}
    
    async def search_tasks(
        self,
        query: str,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> List[Task]:
        """Search tasks by title and description."""
        try:
            async with get_db() as db:
                search_query = select(TaskDB).where(
                    or_(
                        TaskDB.title.ilike(f"%{query}%"),
                        TaskDB.description.ilike(f"%{query}%")
                    )
                )
                
                if user_id:
                    search_query = search_query.where(TaskDB.created_by == user_id)
                
                search_query = search_query.limit(limit)
                
                result = await db.execute(search_query)
                db_tasks = result.scalars().all()
                
                # Convert to domain models
                tasks = [self._db_to_domain(db_task) for db_task in db_tasks]
                
                return tasks
                
        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []
    
    async def bulk_update_tasks(
        self,
        task_ids: List[str],
        updates: Dict[str, Any],
        updated_by: int = 1
    ) -> List[Task]:
        """Bulk update multiple tasks."""
        try:
            updated_tasks = []
            
            for task_id in task_ids:
                task = await self.update_task(task_id, updates, updated_by)
                if task:
                    updated_tasks.append(task)
            
            # Log bulk update
            await self.audit_logger.log_action(
                user_id=updated_by,
                action="task_bulk_updated",
                resource_type="task",
                details={
                    "task_count": len(task_ids),
                    "updates": updates
                }
            )
            
            return updated_tasks
            
        except Exception as e:
            logger.error(f"Error bulk updating tasks: {e}")
            return []
    
    async def create_task_template(
        self,
        name: str,
        template_data: Dict[str, Any],
        created_by: int = 1
    ) -> str:
        """Create a task template."""
        try:
            template_id = str(uuid.uuid4())
            
            # Store template in system config or dedicated table
            async with get_db() as db:
                from models.db import SystemConfigDB
                
                config = SystemConfigDB(
                    id=template_id,
                    key=f"task_template_{name}",
                    value=template_data,
                    description=f"Task template: {name}",
                    updated_by=created_by
                )
                
                db.add(config)
                await db.commit()
                
                logger.info(f"Created task template {name}")
                return template_id
                
        except Exception as e:
            logger.error(f"Error creating task template: {e}")
            raise
    
    async def create_task_from_template(
        self,
        template_name: str,
        overrides: Dict[str, Any] = None,
        created_by: int = 1
    ) -> Optional[Task]:
        """Create a task from a template."""
        try:
            async with get_db() as db:
                from models.db import SystemConfigDB
                
                result = await db.execute(
                    select(SystemConfigDB).where(
                        SystemConfigDB.key == f"task_template_{template_name}"
                    )
                )
                
                template_config = result.scalar_one_or_none()
                
                if not template_config:
                    logger.warning(f"Task template {template_name} not found")
                    return None
                
                # Merge template data with overrides
                task_data = template_config.value.copy()
                if overrides:
                    task_data.update(overrides)
                
                # Create task
                task = await self.create_task(
                    title=task_data.get("title", f"Task from {template_name}"),
                    description=task_data.get("description"),
                    status=task_data.get("status", "pending"),
                    priority=task_data.get("priority", "medium"),
                    assigned_to=task_data.get("assigned_to"),
                    created_by=created_by,
                    tags=task_data.get("tags", [])
                )
                
                return task
                
        except Exception as e:
            logger.error(f"Error creating task from template: {e}")
            return None
    
    async def shutdown(self):
        """Shutdown the task manager."""
        # Clear cache
        self.task_cache.clear()
        logger.info("Task manager shutdown complete")
    
    # Helper methods
    def _db_to_domain(self, db_task: TaskDB) -> Task:
        """Convert database model to domain model."""
        return Task(
            id=db_task.id,
            title=db_task.title,
            description=db_task.description,
            status=db_task.status,
            priority=db_task.priority,
            assigned_to=db_task.assigned_to,
            created_by=db_task.created_by,
            created_at=db_task.created_at,
            updated_at=db_task.updated_at,
            due_date=db_task.due_date,
            completed_at=db_task.completed_at,
            tags=db_task.tags,
            dependencies=db_task.dependencies,
            subtasks=db_task.subtasks,
            attachments=db_task.attachments,
            metadata=db_task.metadata
        )
    
    async def _add_subtask(self, parent_task_id: str, subtask_id: str):
        """Add a subtask to a parent task."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(TaskDB).where(TaskDB.id == parent_task_id)
                )
                
                parent_task = result.scalar_one_or_none()
                
                if parent_task:
                    if not parent_task.subtasks:
                        parent_task.subtasks = []
                    
                    if subtask_id not in parent_task.subtasks:
                        parent_task.subtasks.append(subtask_id)
                        await db.commit()
                        
                        # Update subtask metadata
                        result = await db.execute(
                            select(TaskDB).where(TaskDB.id == subtask_id)
                        )
                        
                        subtask = result.scalar_one_or_none()
                        if subtask:
                            if not subtask.metadata:
                                subtask.metadata = {}
                            subtask.metadata["parent_task_id"] = parent_task_id
                            await db.commit()
                            
        except Exception as e:
            logger.error(f"Error adding subtask: {e}")
    
    async def _remove_subtask(self, parent_task_id: str, subtask_id: str):
        """Remove a subtask from a parent task."""
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(TaskDB).where(TaskDB.id == parent_task_id)
                )
                
                parent_task = result.scalar_one_or_none()
                
                if parent_task and parent_task.subtasks:
                    if subtask_id in parent_task.subtasks:
                        parent_task.subtasks.remove(subtask_id)
                        await db.commit()
                        
        except Exception as e:
            logger.error(f"Error removing subtask: {e}")