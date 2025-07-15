"""
Core Agent Framework Classes

This module provides the foundational classes for the multi-agent system,
including base agent nodes, execution contexts, graph management, and
orchestration primitives for coordinating AI agents.
"""

from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import yaml
import logging

from apps.backend.memory.models import User, TaskRecord
from apps.backend.memory.memory_store import get_relevant_memories
from apps.backend.core.settings import settings


logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Types of agents in the system."""
    LLM = "llm"
    SEARCH = "search"
    HUMAN = "human"
    ROUTER = "router"
    TOOL = "tool"


class AgentStatus(str, Enum):
    """Agent operational status."""
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    OFFLINE = "offline"


@dataclass
class ExecutionContext:
    """
    Shared context passed between agents during task execution.
    
    Maintains state, memory access, and coordination information
    throughout multi-agent workflows.
    """
    task_id: str
    user_id: str
    parameters: Dict[str, Any]
    memory_enabled: bool = True
    memories: List[Any] = field(default_factory=list)
    agent_outputs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    token_usage: Dict[str, int] = field(default_factory=dict)
    
    async def load_relevant_memories(self, query: str, limit: int = 5):
        """Load relevant memories from the knowledge base."""
        if self.memory_enabled:
            self.memories = await get_relevant_memories(
                user_id=self.user_id,
                query=query,
                limit=limit
            )
    
    def add_agent_output(self, agent_id: str, output: Any):
        """Store output from an agent for use by subsequent agents."""
        self.agent_outputs[agent_id] = output
        
    def get_agent_output(self, agent_id: str) -> Optional[Any]:
        """Retrieve output from a previous agent in the workflow."""
        return self.agent_outputs.get(agent_id)
        
    def update_token_usage(self, agent_id: str, tokens: int):
        """Track token usage per agent for cost monitoring."""
        self.token_usage[agent_id] = self.token_usage.get(agent_id, 0) + tokens


@dataclass
class AgentResponse:
    """Standardized response format from all agents."""
    content: Any
    success: bool
    agent_id: str
    tokens_used: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    requires_approval: bool = False
    confidence: float = 1.0


class AgentNode(ABC):
    """
    Abstract base class for all agent nodes in the graph.
    
    Defines the interface that all agents must implement for
    integration into the multi-agent workflow system.
    """
    
    def __init__(
        self,
        node_id: str,
        name: str,
        agent_type: AgentType,
        capabilities: List[str],
        config: Dict[str, Any]
    ):
        self.node_id = node_id
        self.name = name
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.config = config
        self.status = AgentStatus.READY
        self.visualization_position = config.get("position", {"x": 0, "y": 0})
        self.category = config.get("category", "general")
        
    @abstractmethod
    async def execute(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """
        Execute the agent's primary function.
        
        Must be implemented by all concrete agent classes.
        """
        pass
        
    async def validate_input(self, context: ExecutionContext) -> bool:
        """Validate that the agent can process the given context."""
        return True
        
    async def estimate_cost(self, prompt: str) -> float:
        """Estimate the cost of executing with the given prompt."""
        # Default implementation based on token estimation
        estimated_tokens = len(prompt.split()) * 1.3  # Rough estimate
        return estimated_tokens * 0.00001  # Default token price
        
    def can_handle(self, task_type: str) -> bool:
        """Check if this agent can handle a specific task type."""
        return task_type in self.capabilities


@dataclass
class GraphEdge:
    """Represents a connection between agent nodes."""
    source: str
    target: str
    condition: Optional[str] = None
    edge_type: str = "sequential"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate_condition(self, context: ExecutionContext) -> bool:
        """Evaluate if this edge should be traversed."""
        if not self.condition:
            return True
            
        # Simple condition evaluation - in production, use a proper expression evaluator
        try:
            # Create evaluation namespace with context data
            namespace = {
                "task_type": context.parameters.get("task_type"),
                "requires_approval": context.metadata.get("requires_approval", False),
                "confidence": context.metadata.get("confidence", 1.0),
                "estimated_cost": context.metadata.get("estimated_cost", 0),
                "cost_threshold": settings.COST_THRESHOLD_USD
            }
            
            # Safely evaluate condition
            return eval(self.condition, {"__builtins__": {}}, namespace)
        except Exception as e:
            logger.warning(f"Failed to evaluate edge condition: {e}")
            return False


class AgentGraph:
    """
    Manages the multi-agent workflow graph.
    
    Loads configuration, maintains node registry, and orchestrates
    agent execution according to defined workflows.
    """
    
    def __init__(self):
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: List[GraphEdge] = []
        self.workflows: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self.version: str = "1.0"
        self.layout_algorithm: str = "hierarchical"
        
    async def load_from_yaml(self, yaml_path: str):
        """Load graph configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            
        self.config = config
        self.version = config.get("version", "1.0")
        
        # Load nodes
        await self._load_nodes(config.get("nodes", {}))
        
        # Load edges
        self._load_edges(config.get("edges", []))
        
        # Load workflows
        self.workflows = config.get("workflows", {})
        
    async def _load_nodes(self, nodes_config: Dict[str, Any]):
        """Initialize agent nodes from configuration."""
        for node_id, node_config in nodes_config.items():
            agent_type = AgentType(node_config["type"])
            
            # Dynamically load agent class
            if agent_type == AgentType.LLM:
                agent_class_path = node_config["agent_class"]
                # Import and instantiate the agent class
                # In production, use importlib for dynamic loading
                
            # Create node instance (simplified for example)
            node = AgentNode(
                node_id=node_id,
                name=node_config.get("id", node_id),
                agent_type=agent_type,
                capabilities=node_config.get("capabilities", []),
                config=node_config
            )
            
            self.nodes[node_id] = node
            
    def _load_edges(self, edges_config: List[Dict[str, Any]]):
        """Load edges from configuration."""
        for edge_config in edges_config:
            edge = GraphEdge(
                source=edge_config["source"],
                target=edge_config["target"],
                condition=edge_config.get("condition"),
                edge_type=edge_config.get("type", "sequential"),
                metadata=edge_config.get("metadata", {})
            )
            self.edges.append(edge)
            
    def get_next_nodes(self, current_node: str, context: ExecutionContext) -> List[str]:
        """Determine next nodes to execute based on current state."""
        next_nodes = []
        
        for edge in self.edges:
            if edge.source == current_node and edge.evaluate_condition(context):
                next_nodes.append(edge.target)
                
        return next_nodes
        
    async def execute_workflow(
        self,
        workflow_name: str,
        context: ExecutionContext
    ) -> List[AgentResponse]:
        """Execute a predefined workflow."""
        if workflow_name not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_name}")
            
        workflow = self.workflows[workflow_name]
        responses = []
        
        for step in workflow["steps"]:
            node_id = step["node"]
            action = step["action"]
            
            if node_id not in self.nodes:
                raise ValueError(f"Unknown node in workflow: {node_id}")
                
            node = self.nodes[node_id]
            
            # Execute agent with action
            response = await node.execute(
                context=context,
                prompt=f"Action: {action}",
                action=action
            )
            
            responses.append(response)
            context.add_agent_output(node_id, response.content)
            
            # Check if approval is required
            if response.requires_approval:
                # Handle approval flow
                await self._handle_approval_requirement(context, response)
                
        return responses
        
    async def _handle_approval_requirement(
        self,
        context: ExecutionContext,
        response: AgentResponse
    ):
        """Handle human approval requirements in workflow."""
        # Implementation would create approval request and wait
        pass


# Global graph instance
_agent_graph: Optional[AgentGraph] = None


async def initialize_agent_graph():
    """Initialize the global agent graph from configuration."""
    global _agent_graph
    _agent_graph = AgentGraph()
    await _agent_graph.load_from_yaml("apps/backend/agents/langgraph.yaml")
    logger.info("Agent graph initialized successfully")


async def get_agent_graph() -> AgentGraph:
    """Get the initialized agent graph instance."""
    if _agent_graph is None:
        await initialize_agent_graph()
    return _agent_graph


async def get_agent_status(node: AgentNode) -> Dict[str, Any]:
    """Get current status and health of an agent node."""
    # In production, this would check actual agent availability
    return {
        "health": node.status.value,
        "is_available": node.status == AgentStatus.READY,
        "rate_limit_remaining": 1000,  # Mock value
        "rate_limit_reset": None,
        "average_latency_ms": 250  # Mock value
    }
