"""
Make.com webhook handler and scenario trigger integration.
Enables external automation platforms to trigger BrainOps tasks via secure webhooks.
"""

import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import HTTPException, Request, Header, BackgroundTasks

from ..core.settings import settings
from ..memory.memory_store import MemoryStore
from ..tasks import task_registry
from ..agents.base import AgentGraph

logger = logging.getLogger(__name__)


class MakeWebhookHandler:
    """
    Handles incoming webhooks from Make.com scenarios.
    Validates requests and triggers appropriate BrainOps tasks.
    """
    
    def __init__(self, memory_store: MemoryStore, agent_graph: AgentGraph):
        self.memory_store = memory_store
        self.agent_graph = agent_graph
        self.webhook_secret = settings.make_webhook_secret
        
    async def handle_webhook(
        self,
        request: Request,
        background_tasks: BackgroundTasks,
        x_hook_signature: Optional[str] = Header(None)
    ) -> Dict[str, Any]:
        """
        Process incoming Make.com webhook requests.
        
        Args:
            request: FastAPI request containing webhook payload
            background_tasks: FastAPI background task queue
            x_hook_signature: HMAC signature for request validation
            
        Returns:
            Response confirming webhook receipt and task trigger status
        """
        # Parse request body
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON payload from Make.com: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
            
        # Validate webhook signature if secret is configured
        if self.webhook_secret:
            if not await self._validate_signature(request, x_hook_signature):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
                
        # Extract task configuration from payload
        task_config = self._extract_task_config(payload)
        
        # Log webhook receipt to memory
        await self._log_webhook_event(payload, task_config)
        
        # Trigger task execution in background
        if task_config:
            background_tasks.add_task(
                self._execute_task,
                task_config,
                payload
            )
            
            return {
                "status": "accepted",
                "message": "Task queued for execution",
                "task_type": task_config.get('task_type'),
                "webhook_id": payload.get('webhook_id')
            }
        else:
            return {
                "status": "ignored",
                "message": "No valid task configuration found",
                "webhook_id": payload.get('webhook_id')
            }
            
    async def _validate_signature(
        self,
        request: Request,
        signature: Optional[str]
    ) -> bool:
        """
        Validate webhook signature using HMAC-SHA256.
        
        Args:
            request: FastAPI request object
            signature: Provided signature header
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not signature:
            logger.warning("Missing webhook signature")
            return False
            
        # Get raw request body
        body = await request.body()
        
        # Calculate expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison)
        return hmac.compare_digest(signature, expected_signature)
        
    def _extract_task_config(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract task configuration from Make.com webhook payload.
        
        Make.com scenarios should send payloads in this format:
        {
            "task_type": "generate_roof_estimate",
            "parameters": {...},
            "webhook_id": "unique_id",
            "scenario_name": "optional_name"
        }
        
        Args:
            payload: Webhook payload from Make.com
            
        Returns:
            Task configuration dict or None if invalid
        """
        task_type = payload.get('task_type')
        if not task_type:
            logger.warning("Webhook payload missing task_type")
            return None
            
        # Validate task type exists in registry
        if task_type not in task_registry:
            logger.warning(f"Unknown task type: {task_type}")
            return None
            
        return {
            'task_type': task_type,
            'parameters': payload.get('parameters', {}),
            'webhook_id': payload.get('webhook_id'),
            'scenario_name': payload.get('scenario_name'),
            'metadata': {
                'source': 'make.com',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
        
    async def _execute_task(
        self,
        task_config: Dict[str, Any],
        original_payload: Dict[str, Any]
    ) -> None:
        """
        Execute BrainOps task triggered by Make.com webhook.
        
        Args:
            task_config: Extracted task configuration
            original_payload: Original webhook payload for context
        """
        task_type = task_config['task_type']
        parameters = task_config['parameters']
        
        try:
            # Get task class from registry
            task_class = task_registry.get(task_type)
            if not task_class:
                logger.error(f"Task not found in registry: {task_type}")
                return
                
            # Create task instance and execute
            task = task_class()
            result = await task.run(parameters)
            
            # Store execution result in memory
            await self._log_task_execution(task_config, result, "success")
            
            # If webhook specified a callback URL, send result
            callback_url = original_payload.get('callback_url')
            if callback_url:
                await self._send_callback(callback_url, result)
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await self._log_task_execution(task_config, str(e), "failed")
            
            # Send error callback if URL provided
            callback_url = original_payload.get('callback_url')
            if callback_url:
                await self._send_callback(
                    callback_url,
                    {"error": str(e), "status": "failed"}
                )
                
    async def _log_webhook_event(
        self,
        payload: Dict[str, Any],
        task_config: Optional[Dict[str, Any]]
    ) -> None:
        """Log incoming webhook event to memory store."""
        await self.memory_store.save_memory_entry(
            namespace="make_webhooks",
            key=f"webhook_{payload.get('webhook_id', 'unknown')}_{datetime.utcnow().timestamp()}",
            content={
                'payload': payload,
                'task_config': task_config,
                'received_at': datetime.utcnow().isoformat(),
                'valid_task': task_config is not None
            }
        )
        
    async def _log_task_execution(
        self,
        task_config: Dict[str, Any],
        result: Any,
        status: str
    ) -> None:
        """Log task execution result to memory store."""
        await self.memory_store.save_memory_entry(
            namespace="make_task_executions",
            key=f"execution_{task_config.get('webhook_id', 'unknown')}_{datetime.utcnow().timestamp()}",
            content={
                'task_config': task_config,
                'result': result if status == "success" else None,
                'error': result if status == "failed" else None,
                'status': status,
                'executed_at': datetime.utcnow().isoformat()
            }
        )
        
    async def _send_callback(self, callback_url: str, data: Dict[str, Any]) -> None:
        """
        Send task execution result back to Make.com scenario.
        
        Args:
            callback_url: URL to send results to
            data: Result data to send
        """
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    callback_url,
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Callback to {callback_url} failed with status {response.status}"
                        )
        except Exception as e:
            logger.error(f"Failed to send callback to {callback_url}: {e}")


class MakeScenarioTrigger:
    """
    Utility class for triggering Make.com scenarios from BrainOps.
    Allows bi-directional integration with Make.com automations.
    """
    
    def __init__(self):
        self.webhook_base_url = settings.make_webhook_base_url
        
    async def trigger_scenario(
        self,
        scenario_webhook_id: str,
        data: Dict[str, Any],
        wait_for_response: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Trigger a Make.com scenario via webhook.
        
        Args:
            scenario_webhook_id: The webhook ID for the target scenario
            data: Data to send to the scenario
            wait_for_response: Whether to wait for scenario completion
            
        Returns:
            Response from Make.com if wait_for_response is True
        """
        import aiohttp
        
        webhook_url = f"{self.webhook_base_url}/{scenario_webhook_id}"
        
        # Add metadata to help with debugging
        payload = {
            **data,
            "_brainops_metadata": {
                "triggered_at": datetime.utcnow().isoformat(),
                "wait_for_response": wait_for_response
            }
        }
        
        try:
            timeout = aiohttp.ClientTimeout(
                total=300 if wait_for_response else 30  # 5 min if waiting, 30s otherwise
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        if wait_for_response:
                            return await response.json()
                        else:
                            return {"status": "triggered", "webhook_id": scenario_webhook_id}
                    else:
                        logger.error(
                            f"Failed to trigger Make.com scenario: {response.status}"
                        )
                        return None
                        
        except aiohttp.ClientTimeout:
            logger.error(f"Timeout triggering Make.com scenario {scenario_webhook_id}")
            return None
        except Exception as e:
            logger.error(f"Error triggering Make.com scenario: {e}")
            return None
            
    async def batch_trigger_scenarios(
        self,
        triggers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Trigger multiple Make.com scenarios in parallel.
        
        Args:
            triggers: List of dicts with 'webhook_id' and 'data' keys
            
        Returns:
            List of results for each trigger attempt
        """
        import asyncio
        
        tasks = [
            self.trigger_scenario(
                trigger['webhook_id'],
                trigger['data'],
                trigger.get('wait_for_response', False)
            )
            for trigger in triggers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "webhook_id": triggers[i]['webhook_id'],
                    "status": "error",
                    "error": str(result)
                })
            else:
                processed_results.append(result or {
                    "webhook_id": triggers[i]['webhook_id'],
                    "status": "failed"
                })
                
        return processed_results