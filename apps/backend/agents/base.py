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

from ..memory.models import User, TaskRecord
from ..memory.memory_store import get_relevant_memories
from ..core.settings import settings


class AgentType(Enum):
    """Types of agents in the system."""
    LLM = "llm"
    TOOL = "tool"
    ORCHESTRATOR = "orchestrator"
    MEMORY = "memory"
    WORKFLOW = "workflow"


class ExecutionContext:
    """Execution context for agents."""
    pass


class AgentResponse:
    """Agent response wrapper."""
    pass


def get_agent_graph():
    """Get agent graph."""
    return {}


class AgentContext:
    """Agent context stub."""
    pass


class AgentGraph:
    """Agent graph stub."""
    pass


class AgentNode:
    """Agent node stub."""
    pass


def get_agent_status():
    """Get agent status stub."""
    return {"status": "active"}
