"""
AI Agent Coordination Routes

This module manages multi-agent workflows, including task approval queues,
agent status monitoring, and pipeline orchestration for complex operations
that require multiple AI models working in sequence or parallel.
"""

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json

from apps.backend.core.security import get_current_user, verify_websocket_token
from apps.backend.memory.models import User, AgentStatus, ApprovalRequest, PipelineConfig
from apps.backend.agents.base import (
    AgentGraph,
    AgentNode,
    ExecutionContext,
    get_agent_graph,
    get_agent_status
)
from apps.backend.memory.memory_store import (
    get_pending_approvals,
    update_approval_status,
    log_agent_execution
)


router = APIRouter()


@router.get("/status")
async def get_agents_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get status of all configured agents and their availability.
    
    Returns health status, rate limits, and capabilities for each
    AI agent in the system.
    """
    # Get configured agent graph
    graph = await get_agent_graph()
    
    # Check status of each agent node
    agent_statuses = {}
    for node_id, node in graph.nodes.items():
        status = await get_agent_status(node)
        agent_statuses[node_id] = {
            "name": node.name,
            "type": node.agent_type,
            "status": status.health,
            "available": status.is_available,
            "rate_limit": {
                "remaining": status.rate_limit_remaining,
                "reset_at": status.rate_limit_reset.isoformat() if status.rate_limit_reset else None
            },
            "capabilities": node.capabilities,
            "average_latency_ms": status.average_latency_ms
        }
    
    return {
        "agents": agent_statuses,
        "graph_version": graph.version,
        "total_agents": len(agent_statuses),
        "healthy_agents": sum(1 for s in agent_statuses.values() if s["available"])
    }


@router.get("/inbox")
async def get_approval_inbox(
    status: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get pending approval requests from agent workflows.
    
    Returns items requiring human review before agents can proceed
    with high-stakes operations.
    """
    # Fetch pending approvals for user
    approvals = await get_pending_approvals(
        user_id=current_user.id,
        status=status,
        limit=limit
    )
    
    # Format approval requests with context
    formatted_approvals = []
    for approval in approvals:
        formatted_approvals.append({
            "approval_id": approval.id,
            "task_id": approval.task_id,
            "agent": approval.agent_name,
            "action": approval.action_description,
            "risk_level": approval.risk_level,
            "context": approval.context,
            "created_at": approval.created_at.isoformat(),
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
            "status": approval.status
        })
    
    return {
        "approvals": formatted_approvals,
        "total": len(formatted_approvals),
        "pending_count": sum(1 for a in formatted_approvals if a["status"] == "pending")
    }


@router.post("/approve/{approval_id}")
async def approve_action(
    approval_id: str,
    feedback: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Approve a pending agent action.
    
    Allows the agent workflow to proceed with the proposed action
    and optionally provides feedback for context refinement.
    """
    # Update approval status
    approval = await update_approval_status(
        approval_id=approval_id,
        user_id=current_user.id,
        status="approved",
        reviewer_notes=feedback,
        reviewed_at=datetime.utcnow()
    )
    
    if not approval:
        raise HTTPException(404, "Approval request not found or expired")
    
    # Notify waiting agent to proceed
    await notify_agent_decision(approval.task_id, approval_id, "approved")
    
    return {
        "approval_id": approval_id,
        "status": "approved",
        "message": "Action approved, agent proceeding",
        "task_id": approval.task_id
    }


@router.post("/reject/{approval_id}")
async def reject_action(
    approval_id: str,
    reason: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Reject a pending agent action.
    
    Prevents the agent from proceeding and provides reason for
    rejection to help refine future proposals.
    """
    # Update approval status with rejection
    approval = await update_approval_status(
        approval_id=approval_id,
        user_id=current_user.id,
        status="rejected",
        reviewer_notes=reason,
        reviewed_at=datetime.utcnow()
    )
    
    if not approval:
        raise HTTPException(404, "Approval request not found or expired")
    
    # Notify agent of rejection
    await notify_agent_decision(approval.task_id, approval_id, "rejected", reason)
    
    return {
        "approval_id": approval_id,
        "status": "rejected",
        "message": "Action rejected, agent will adjust approach",
        "reason": reason
    }


@router.post("/pipelines")
async def create_pipeline(
    name: str,
    description: str,
    agent_sequence: List[Dict[str, Any]],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a reusable multi-agent pipeline configuration.
    
    Defines a sequence of agents and their connections for
    complex workflows that can be triggered as a single unit.
    """
    # Validate agent sequence
    graph = await get_agent_graph()
    for step in agent_sequence:
        agent_id = step.get("agent_id")
        if agent_id not in graph.nodes:
            raise HTTPException(400, f"Unknown agent: {agent_id}")
    
    # Create pipeline configuration
    pipeline = PipelineConfig(
        name=name,
        description=description,
        user_id=current_user.id,
        agent_sequence=agent_sequence,
        created_at=datetime.utcnow(),
        is_active=True
    )
    
    # Save pipeline configuration
    saved_pipeline = await save_pipeline_config(pipeline)
    
    return {
        "pipeline_id": saved_pipeline.id,
        "name": saved_pipeline.name,
        "agent_count": len(agent_sequence),
        "message": "Pipeline created successfully"
    }


@router.get("/pipelines")
async def list_pipelines(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    List available agent pipeline configurations.
    
    Returns user's custom pipelines and system-provided templates
    for common multi-agent workflows.
    """
    # Get user pipelines
    user_pipelines = await get_user_pipelines(current_user.id)
    
    # Get system template pipelines
    system_pipelines = await get_system_pipelines()
    
    # Format pipeline list
    formatted_pipelines = []
    
    for pipeline in user_pipelines + system_pipelines:
        formatted_pipelines.append({
            "pipeline_id": pipeline.id,
            "name": pipeline.name,
            "description": pipeline.description,
            "agent_count": len(pipeline.agent_sequence),
            "is_system": pipeline.is_system,
            "created_at": pipeline.created_at.isoformat(),
            "last_run": pipeline.last_run.isoformat() if pipeline.last_run else None,
            "run_count": pipeline.run_count
        })
    
    return {
        "pipelines": formatted_pipelines,
        "user_pipelines": len(user_pipelines),
        "system_pipelines": len(system_pipelines)
    }


@router.websocket("/stream/{task_id}")
async def agent_stream(
    websocket: WebSocket,
    task_id: str,
    token: str
):
    """
    WebSocket endpoint for real-time agent execution streaming.
    
    Provides live updates on agent thinking, actions, and progress
    for transparency during complex multi-step operations.
    """
    # Verify WebSocket authentication
    user = await verify_websocket_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await websocket.accept()
    
    try:
        # Subscribe to agent execution events for this task
        event_queue = await subscribe_to_agent_events(task_id, user.id)
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Stream agent events as they occur
        while True:
            try:
                # Wait for next event with timeout
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=30.0  # 30 second heartbeat
                )
                
                if event is None:  # Termination signal
                    break
                
                # Send event to client
                await websocket.send_json({
                    "type": event.type,
                    "agent": event.agent_name,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat()
                })
                
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        # Client disconnected
        await unsubscribe_from_agent_events(task_id, user.id)
    except Exception as e:
        # Send error and close connection
        await websocket.send_json({
            "type": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })
        await websocket.close(code=4002, reason="Internal error")


@router.get("/graph/visualize")
async def visualize_agent_graph(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get agent graph structure for visualization.
    
    Returns nodes, edges, and metadata formatted for rendering
    the multi-agent workflow graph in the UI.
    """
    # Get current agent graph configuration
    graph = await get_agent_graph()
    
    # Format for visualization
    nodes = []
    edges = []
    
    for node_id, node in graph.nodes.items():
        nodes.append({
            "id": node_id,
            "label": node.name,
            "type": node.agent_type,
            "group": node.category,
            "capabilities": node.capabilities,
            "position": node.visualization_position
        })
    
    for edge in graph.edges:
        edges.append({
            "id": f"{edge.source}-{edge.target}",
            "source": edge.source,
            "target": edge.target,
            "label": edge.condition or "",
            "type": edge.edge_type
        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "layout": graph.layout_algorithm,
        "version": graph.version
    }


# Helper functions
async def notify_agent_decision(task_id: str, approval_id: str, decision: str, reason: str = None):
    """Notify waiting agent of approval decision."""
    # Implementation would send message to agent execution queue
    pass


async def subscribe_to_agent_events(task_id: str, user_id: str):
    """Subscribe to real-time agent execution events."""
    # Implementation would create event queue subscription
    return asyncio.Queue()


async def unsubscribe_from_agent_events(task_id: str, user_id: str):
    """Clean up agent event subscription."""
    # Implementation would remove event queue subscription
    pass
