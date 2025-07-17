"""
Claude Agent Wrapper

This module provides the Claude (Anthropic) agent implementation for content
generation, documentation, and quality assurance tasks. Specializes in
high-quality written content with strong contextual understanding.
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import anthropic
import logging

from .base import AgentNode, AgentResponse, ExecutionContext, AgentType
from ..core.settings import settings
from ..memory.memory_store import get_prompt_template


logger = logging.getLogger(__name__)


class ClaudeAgent(AgentNode):
    """
    Claude agent for content generation and documentation tasks.
    
    Leverages Anthropic's Claude model for creating high-quality written
    content, documentation, and performing content quality assurance.
    """
    
    def __init__(self, node_id: str, name: str, config: Dict[str, Any]):
        super().__init__(
            node_id=node_id,
            name=name,
            agent_type=AgentType.LLM,
            capabilities=config.get("capabilities", []),
            config=config
        )
        
        # Initialize Anthropic client
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.claude_api_key
        )
        
        # Model configuration
        self.model = config.get("model", "claude-3-opus-20240229")
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4096)
        
        # Load system prompt template
        self.system_prompt_template = config.get("system_prompt_template")
        
    async def execute(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """
        Execute Claude for content generation tasks.
        
        Handles content creation, documentation, copywriting, and
        quality assurance based on the provided context and prompt.
        """
        try:
            # Build enhanced prompt with context
            enhanced_prompt = await self._build_enhanced_prompt(context, prompt)
            
            # Load system prompt from template
            system_prompt = await self._load_system_prompt(context)
            
            # Execute Claude API call with retry logic
            response = await self._call_claude_with_retry(
                system_prompt=system_prompt,
                user_prompt=enhanced_prompt,
                **kwargs
            )
            
            # Extract and process response
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            # Update context with token usage
            context.update_token_usage(self.node_id, tokens_used)
            
            # Analyze response for approval requirements
            requires_approval = self._check_approval_requirements(content, context)
            
            # Calculate confidence score based on response
            confidence = self._calculate_confidence(response, context)
            
            return AgentResponse(
                content=content,
                success=True,
                agent_id=self.node_id,
                tokens_used=tokens_used,
                metadata={
                    "model": self.model,
                    "temperature": self.temperature,
                    "finish_reason": response.stop_reason,
                    "response_id": response.id
                },
                requires_approval=requires_approval,
                confidence=confidence
            )
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"API Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in Claude agent: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def _build_enhanced_prompt(
        self,
        context: ExecutionContext,
        base_prompt: str
    ) -> str:
        """Build prompt with relevant context and memories."""
        enhanced_parts = []
        
        # Add task context
        enhanced_parts.append("=== TASK CONTEXT ===")
        enhanced_parts.append(f"Task ID: {context.task_id}")
        enhanced_parts.append(f"Task Type: {context.parameters.get('task_type', 'general')}")
        
        # Add relevant memories if enabled
        if context.memory_enabled and context.memories:
            enhanced_parts.append("\n=== RELEVANT CONTEXT ===")
            for memory in context.memories[:5]:  # Limit to top 5 memories
                enhanced_parts.append(f"- {memory.title}: {memory.content[:200]}...")
        
        # Add outputs from previous agents in workflow
        if context.agent_outputs:
            enhanced_parts.append("\n=== PREVIOUS AGENT OUTPUTS ===")
            for agent_id, output in context.agent_outputs.items():
                enhanced_parts.append(f"[{agent_id}]: {str(output)[:500]}...")
        
        # Add the main prompt
        enhanced_parts.append(f"\n=== CURRENT REQUEST ===\n{base_prompt}")
        
        return "\n".join(enhanced_parts)
    
    async def _load_system_prompt(self, context: ExecutionContext) -> str:
        """Load and customize system prompt from template."""
        if self.system_prompt_template:
            template = await get_prompt_template(self.system_prompt_template)
            
            # Customize template with context
            system_prompt = template.format(
                user_company=context.metadata.get("user_company", "BrainOps"),
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                capabilities=", ".join(self.capabilities)
            )
            
            return system_prompt
        
        # Default system prompt if no template specified
        return (
            "You are Claude, an AI assistant specialized in content creation, "
            "documentation, and quality assurance. You provide clear, accurate, "
            "and professionally written content tailored to the user's needs."
        )
    
    async def _call_claude_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """Call Claude API with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    **kwargs
                )
                return response
                
            except anthropic.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except anthropic.APIConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error, retrying... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    raise
    
    def _check_approval_requirements(self, content: str, context: ExecutionContext) -> bool:
        """
        Determine if the generated content requires human approval.
        
        Checks for sensitive content, low confidence, or explicit approval flags.
        """
        # Check if task type requires approval
        approval_required_types = ["publication", "external_communication", "legal_content"]
        if context.parameters.get("task_type") in approval_required_types:
            return True
        
        # Check for sensitive content markers
        sensitive_markers = ["DRAFT", "NEEDS REVIEW", "UNCERTAIN", "[APPROVAL REQUIRED]"]
        if any(marker in content.upper() for marker in sensitive_markers):
            return True
        
        # Check if explicitly requested
        if context.parameters.get("require_approval", False):
            return True
        
        return False
    
    def _calculate_confidence(self, response: Any, context: ExecutionContext) -> float:
        """
        Calculate confidence score for the generated content.
        
        Based on response characteristics and context alignment.
        """
        confidence = 1.0
        
        # Reduce confidence if response was truncated
        if response.stop_reason == "max_tokens":
            confidence *= 0.8
        
        # Reduce confidence for certain task types
        uncertain_types = ["creative_writing", "strategy", "prediction"]
        if context.parameters.get("task_type") in uncertain_types:
            confidence *= 0.9
        
        # Boost confidence if response includes structured elements
        content = response.content[0].text
        if any(marker in content for marker in ["```", "1.", "###", "- [ ]"]):
            confidence *= 1.05
        
        # Cap confidence at 1.0
        return min(confidence, 1.0)
    
    async def estimate_cost(self, prompt: str) -> float:
        """Estimate cost for Claude API call."""
        # Claude pricing (as of 2024)
        # Input: $15 per million tokens
        # Output: $75 per million tokens
        
        # Rough token estimation
        input_tokens = len(prompt.split()) * 1.3
        estimated_output_tokens = self.max_tokens * 0.7  # Assume 70% usage
        
        input_cost = (input_tokens / 1_000_000) * 15
        output_cost = (estimated_output_tokens / 1_000_000) * 75
        
        return input_cost + output_cost
    
    async def validate_input(self, context: ExecutionContext) -> bool:
        """Validate that Claude can handle this context."""
        # Check for required parameters
        task_type = context.parameters.get("task_type")
        if not task_type:
            logger.warning("No task_type specified in context")
            return False
        
        # Verify task type is in capabilities
        if not self.can_handle(task_type):
            logger.warning(f"Claude cannot handle task type: {task_type}")
            return False
        
        # Check content length constraints
        content_length = context.parameters.get("content_length", 0)
        if content_length > 50000:  # Approximate character limit
            logger.warning("Content too long for Claude processing")
            return False
        
        return True
