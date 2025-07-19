"""
LangGraph Multi-Agent Orchestration System

Production-ready orchestration for complex multi-agent workflows with:
- State persistence and recovery
- Error handling and retries
- Context passing between agents
- Parallel and sequential execution
- Monitoring and observability
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Type
from enum import Enum
import traceback
from functools import wraps

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver, CheckpointTuple
from langgraph.pregel import Channel

from ..db.business_models import User
from ..core.database import get_db
from ..core.logging import get_logger
from ..memory.backend_memory_store import BackendMemoryStore
from ..services.notifications import NotificationService
from .claude_agent import ClaudeAgent
from .base import BaseAgent, AgentResponse


logger = get_logger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AgentRole(str, Enum):
    """Predefined agent roles for common tasks."""
    ANALYZER = "analyzer"
    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"


class WorkflowState(BaseModel):
    """State maintained throughout workflow execution."""
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: str = "start"
    context: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class AgentNode:
    """Wrapper for an agent in the workflow."""
    
    def __init__(
        self,
        agent: BaseAgent,
        role: AgentRole,
        max_retries: int = 3,
        timeout: int = 300
    ):
        self.agent = agent
        self.role = role
        self.max_retries = max_retries
        self.timeout = timeout
    
    async def execute(
        self,
        state: WorkflowState,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute agent with retry logic and error handling."""
        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            try:
                # Add timeout
                result = await asyncio.wait_for(
                    self._execute_agent(state, input_data),
                    timeout=self.timeout
                )
                return result
                
            except asyncio.TimeoutError:
                last_error = f"Agent execution timed out after {self.timeout}s"
                logger.warning(f"Timeout in {self.role} agent: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Error in {self.role} agent: {e}", exc_info=True)
                
            retries += 1
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)  # Exponential backoff
        
        # Record error in state
        state.errors.append({
            "agent": self.role.value,
            "error": last_error,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        raise Exception(f"Agent {self.role} failed after {retries} retries: {last_error}")
    
    async def _execute_agent(
        self,
        state: WorkflowState,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the actual agent logic."""
        # Prepare messages with context
        messages = [
            SystemMessage(content=f"You are acting as a {self.role.value} agent in a multi-agent workflow."),
            SystemMessage(content=f"Workflow context: {json.dumps(state.context)}"),
            HumanMessage(content=input_data.get("prompt", ""))
        ]
        
        # Add relevant previous results
        if state.results:
            messages.append(
                SystemMessage(content=f"Previous results: {json.dumps(state.results)}")
            )
        
        # Execute agent
        response = await self.agent.agenerate(
            messages=messages,
            metadata={
                "workflow_id": state.workflow_id,
                "step": state.current_step,
                "role": self.role.value
            }
        )
        
        # Extract result
        result = {
            "content": response.generations[0][0].text,
            "metadata": response.llm_output or {},
            "agent_role": self.role.value,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Update state
        state.messages.append({
            "role": self.role.value,
            "content": result["content"],
            "timestamp": result["timestamp"]
        })
        
        return result


class LangGraphOrchestrator:
    """
    Production-ready multi-agent orchestration system.
    
    Features:
    - Complex workflow definition and execution
    - State persistence and recovery
    - Error handling and retries
    - Parallel and sequential agent execution
    - Monitoring and observability
    """
    
    def __init__(
        self,
        memory_store: Optional[BackendMemoryStore] = None,
        notification_service: Optional[NotificationService] = None
    ):
        self.memory_store = memory_store or BackendMemoryStore()
        self.notification_service = notification_service or NotificationService()
        self.checkpointer = MemorySaver()
        self.workflows: Dict[str, StateGraph] = {}
        self.active_executions: Dict[str, WorkflowState] = {}
        
    def create_workflow(
        self,
        workflow_id: str,
        workflow_definition: Dict[str, Any]
    ) -> StateGraph:
        """Create a workflow from definition."""
        # Create state graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        nodes = workflow_definition.get("nodes", {})
        for node_id, node_config in nodes.items():
            agent_class = self._get_agent_class(node_config["agent_type"])
            agent = agent_class(**node_config.get("agent_config", {}))
            
            node = AgentNode(
                agent=agent,
                role=AgentRole(node_config["role"]),
                max_retries=node_config.get("max_retries", 3),
                timeout=node_config.get("timeout", 300)
            )
            
            workflow.add_node(node_id, self._create_node_function(node))
        
        # Add edges
        edges = workflow_definition.get("edges", [])
        for edge in edges:
            if edge["type"] == "direct":
                workflow.add_edge(edge["from"], edge["to"])
            elif edge["type"] == "conditional":
                workflow.add_conditional_edges(
                    edge["from"],
                    self._create_condition_function(edge["condition"]),
                    edge["routes"]
                )
        
        # Set entry point
        workflow.set_entry_point(workflow_definition.get("entry_point", "start"))
        
        # Compile
        compiled = workflow.compile(checkpointer=self.checkpointer)
        self.workflows[workflow_id] = compiled
        
        return compiled
    
    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None,
        timeout: Optional[int] = 3600
    ) -> WorkflowState:
        """Execute a workflow with full error handling and persistence."""
        # Initialize state
        state = WorkflowState(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            context=input_data.get("context", {}),
            metadata={
                "user_id": user_id,
                "input": input_data,
                "start_time": datetime.utcnow().isoformat()
            }
        )
        
        self.active_executions[workflow_id] = state
        
        try:
            # Get workflow
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_workflow_steps(workflow, state, input_data),
                timeout=timeout
            )
            
            # Update final state
            state.status = WorkflowStatus.COMPLETED
            state.metadata["end_time"] = datetime.utcnow().isoformat()
            state.metadata["duration"] = (
                datetime.utcnow() - datetime.fromisoformat(state.metadata["start_time"])
            ).total_seconds()
            
            # Persist to memory store
            await self._persist_workflow_state(state)
            
            # Send completion notification
            if user_id and self.notification_service:
                await self.notification_service.notify_user(
                    user_id,
                    "Workflow Completed",
                    f"Workflow {workflow_id} completed successfully"
                )
            
            return state
            
        except asyncio.TimeoutError:
            state.status = WorkflowStatus.FAILED
            state.errors.append({
                "error": "Workflow execution timeout",
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.error(f"Workflow {workflow_id} timed out")
            
        except Exception as e:
            state.status = WorkflowStatus.FAILED
            state.errors.append({
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.error(f"Workflow {workflow_id} failed: {e}", exc_info=True)
            
        finally:
            # Always persist final state
            await self._persist_workflow_state(state)
            
            # Clean up
            self.active_executions.pop(workflow_id, None)
        
        return state
    
    async def _execute_workflow_steps(
        self,
        workflow: StateGraph,
        state: WorkflowState,
        input_data: Dict[str, Any]
    ) -> WorkflowState:
        """Execute workflow steps with checkpointing."""
        config = {"configurable": {"thread_id": state.workflow_id}}
        
        # Stream execution
        async for event in workflow.astream(
            {"input": input_data, "state": state},
            config=config
        ):
            # Update state with each step
            if isinstance(event, dict):
                for key, value in event.items():
                    if key == "state":
                        state = value
                    elif key in state.results:
                        state.results[key].update(value)
                    else:
                        state.results[key] = value
            
            # Checkpoint after each step
            await self._checkpoint_state(state)
        
        return state
    
    async def resume_workflow(
        self,
        workflow_id: str,
        from_checkpoint: Optional[str] = None
    ) -> WorkflowState:
        """Resume a paused or failed workflow from checkpoint."""
        # Load state from checkpoint
        state = await self._load_workflow_state(workflow_id, from_checkpoint)
        
        if not state:
            raise ValueError(f"No checkpoint found for workflow {workflow_id}")
        
        # Update status
        state.status = WorkflowStatus.RUNNING
        state.metadata["resumed_at"] = datetime.utcnow().isoformat()
        
        # Get workflow
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Resume execution from last step
        return await self.execute_workflow(
            workflow_id,
            state.metadata.get("input", {}),
            state.metadata.get("user_id")
        )
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        state = self.active_executions.get(workflow_id)
        
        if not state:
            return False
        
        state.status = WorkflowStatus.CANCELLED
        state.metadata["cancelled_at"] = datetime.utcnow().isoformat()
        
        await self._persist_workflow_state(state)
        self.active_executions.pop(workflow_id, None)
        
        return True
    
    def create_analysis_workflow(self) -> str:
        """Create a predefined analysis workflow."""
        workflow_id = f"analysis_{uuid.uuid4()}"
        
        definition = {
            "nodes": {
                "analyze": {
                    "agent_type": "claude",
                    "role": "analyzer",
                    "agent_config": {"model": "claude-3-opus-20240229"}
                },
                "plan": {
                    "agent_type": "claude",
                    "role": "planner",
                    "agent_config": {"model": "claude-3-sonnet-20240229"}
                },
                "execute": {
                    "agent_type": "claude",
                    "role": "executor",
                    "agent_config": {"model": "claude-3-sonnet-20240229"}
                },
                "review": {
                    "agent_type": "claude",
                    "role": "reviewer",
                    "agent_config": {"model": "claude-3-opus-20240229"}
                }
            },
            "edges": [
                {"type": "direct", "from": "analyze", "to": "plan"},
                {"type": "direct", "from": "plan", "to": "execute"},
                {"type": "direct", "from": "execute", "to": "review"},
                {
                    "type": "conditional",
                    "from": "review",
                    "condition": "needs_revision",
                    "routes": {
                        "true": "plan",
                        "false": END
                    }
                }
            ],
            "entry_point": "analyze"
        }
        
        self.create_workflow(workflow_id, definition)
        return workflow_id
    
    def create_parallel_research_workflow(self) -> str:
        """Create a workflow with parallel agent execution."""
        workflow_id = f"research_{uuid.uuid4()}"
        
        definition = {
            "nodes": {
                "coordinator": {
                    "agent_type": "claude",
                    "role": "coordinator",
                    "agent_config": {"model": "claude-3-opus-20240229"}
                },
                "researcher1": {
                    "agent_type": "claude",
                    "role": "specialist",
                    "agent_config": {"model": "claude-3-sonnet-20240229"}
                },
                "researcher2": {
                    "agent_type": "claude",
                    "role": "specialist",
                    "agent_config": {"model": "claude-3-sonnet-20240229"}
                },
                "researcher3": {
                    "agent_type": "claude",
                    "role": "specialist",
                    "agent_config": {"model": "claude-3-haiku-20240307"}
                },
                "synthesizer": {
                    "agent_type": "claude",
                    "role": "reviewer",
                    "agent_config": {"model": "claude-3-opus-20240229"}
                }
            },
            "edges": [
                {"type": "direct", "from": "coordinator", "to": "researcher1"},
                {"type": "direct", "from": "coordinator", "to": "researcher2"},
                {"type": "direct", "from": "coordinator", "to": "researcher3"},
                {"type": "direct", "from": "researcher1", "to": "synthesizer"},
                {"type": "direct", "from": "researcher2", "to": "synthesizer"},
                {"type": "direct", "from": "researcher3", "to": "synthesizer"}
            ],
            "entry_point": "coordinator"
        }
        
        self.create_workflow(workflow_id, definition)
        return workflow_id
    
    def _get_agent_class(self, agent_type: str) -> Type[BaseAgent]:
        """Get agent class by type."""
        agent_classes = {
            "claude": ClaudeAgent,
            # Add more agent types as needed
        }
        
        agent_class = agent_classes.get(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return agent_class
    
    def _create_node_function(self, node: AgentNode) -> Callable:
        """Create a node function for the workflow."""
        async def node_function(state: Dict[str, Any]) -> Dict[str, Any]:
            workflow_state = WorkflowState(**state.get("state", {}))
            input_data = state.get("input", {})
            
            result = await node.execute(workflow_state, input_data)
            
            return {
                "state": workflow_state.dict(),
                node.role.value: result
            }
        
        return node_function
    
    def _create_condition_function(self, condition: str) -> Callable:
        """Create a condition function for conditional edges."""
        def condition_function(state: Dict[str, Any]) -> str:
            # Simple condition evaluation
            # In production, use a proper expression evaluator
            workflow_state = WorkflowState(**state.get("state", {}))
            
            if condition == "needs_revision":
                # Check if review found issues
                review_result = state.get("reviewer", {})
                content = review_result.get("content", "")
                return "true" if "revision needed" in content.lower() else "false"
            
            # Default
            return "false"
        
        return condition_function
    
    async def _persist_workflow_state(self, state: WorkflowState) -> None:
        """Persist workflow state to memory store."""
        await self.memory_store.add_memory(
            user_id=state.metadata.get("user_id", "system"),
            content=state.json(),
            metadata={
                "type": "workflow_state",
                "workflow_id": state.workflow_id,
                "status": state.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _checkpoint_state(self, state: WorkflowState) -> None:
        """Create a checkpoint of current state."""
        checkpoint_id = f"{state.workflow_id}_{state.current_step}_{datetime.utcnow().timestamp()}"
        
        await self.memory_store.add_memory(
            user_id=state.metadata.get("user_id", "system"),
            content=state.json(),
            metadata={
                "type": "workflow_checkpoint",
                "workflow_id": state.workflow_id,
                "checkpoint_id": checkpoint_id,
                "step": state.current_step,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _load_workflow_state(
        self,
        workflow_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[WorkflowState]:
        """Load workflow state from checkpoint."""
        memories = await self.memory_store.search_memories(
            user_id="system",
            query=workflow_id,
            filters={
                "type": "workflow_checkpoint" if checkpoint_id else "workflow_state",
                "workflow_id": workflow_id
            },
            limit=1
        )
        
        if memories:
            return WorkflowState(**json.loads(memories[0]["content"]))
        
        return None
    
    async def get_workflow_history(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get execution history for a workflow."""
        memories = await self.memory_store.search_memories(
            user_id="system",
            query=workflow_id,
            filters={"workflow_id": workflow_id},
            limit=limit
        )
        
        return [
            {
                "checkpoint_id": m["metadata"].get("checkpoint_id"),
                "step": m["metadata"].get("step"),
                "status": m["metadata"].get("status"),
                "timestamp": m["metadata"].get("timestamp"),
                "state": json.loads(m["content"])
            }
            for m in memories
        ]
    
    def get_active_workflows(self) -> Dict[str, WorkflowState]:
        """Get all currently active workflows."""
        return self.active_executions.copy()
    
    async def cleanup_old_checkpoints(self, days: int = 7) -> int:
        """Clean up old workflow checkpoints."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # This would need to be implemented in the memory store
        # For now, return 0
        return 0


# Singleton instance
orchestrator = LangGraphOrchestrator()


# Convenience functions
async def execute_analysis_workflow(
    prompt: str,
    context: Dict[str, Any] = None,
    user_id: Optional[str] = None
) -> WorkflowState:
    """Execute a standard analysis workflow."""
    workflow_id = orchestrator.create_analysis_workflow()
    
    return await orchestrator.execute_workflow(
        workflow_id,
        {
            "prompt": prompt,
            "context": context or {}
        },
        user_id=user_id
    )


async def execute_parallel_research(
    topics: List[str],
    context: Dict[str, Any] = None,
    user_id: Optional[str] = None
) -> WorkflowState:
    """Execute parallel research on multiple topics."""
    workflow_id = orchestrator.create_parallel_research_workflow()
    
    return await orchestrator.execute_workflow(
        workflow_id,
        {
            "prompt": f"Research these topics in parallel: {', '.join(topics)}",
            "topics": topics,
            "context": context or {}
        },
        user_id=user_id
    )