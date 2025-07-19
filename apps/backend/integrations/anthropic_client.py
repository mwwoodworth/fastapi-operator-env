"""
Anthropic (Claude) Integration Client
"""
import asyncio
from typing import Optional, List, Dict, Any, Union
import anthropic
from anthropic import AsyncAnthropic
from ..core.settings import settings
from ..core.logging import logger


class AnthropicClient:
    """Client for Anthropic API integration"""
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY if hasattr(settings, 'ANTHROPIC_API_KEY') else None
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None
        self.default_model = getattr(settings, 'ANTHROPIC_DEFAULT_MODEL', 'claude-3-opus-20240229')
        self.max_retries = 3
    
    async def create_message(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Create a message with Claude"""
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        model = model or self.default_model
        
        try:
            # Convert messages to Anthropic format if needed
            anthropic_messages = self._convert_messages(messages)
            
            response = await self.client.messages.create(
                model=model,
                messages=anthropic_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                **kwargs
            )
            return response
        except anthropic.RateLimitError as e:
            logger.error(f"Anthropic rate limit error: {str(e)}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Anthropic: {str(e)}")
            raise
    
    def _convert_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style messages to Anthropic format"""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                # System messages are handled separately in Anthropic
                continue
            
            # Convert role names
            role = msg["role"]
            if role == "user":
                role = "user"
            elif role == "assistant":
                role = "assistant"
            
            # Handle content
            content = msg.get("content", "")
            
            # Check if content is already in Anthropic format
            if isinstance(content, list):
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
        
        return anthropic_messages
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if not self.client:
            # Rough estimation if no client
            return len(text) // 4
        
        try:
            # Anthropic doesn't have a direct token counting API
            # Use rough estimation
            return len(text) // 4
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            return len(text) // 4
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """Estimate cost for API usage"""
        model = model or self.default_model
        
        # Pricing as of 2024 (per 1K tokens)
        pricing = {
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-2.1": {"input": 0.008, "output": 0.024},
            "claude-2": {"input": 0.008, "output": 0.024}
        }
        
        if model not in pricing:
            # Default to Opus pricing
            model_pricing = pricing["claude-3-opus-20240229"]
        else:
            model_pricing = pricing[model]
        
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    async def create_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs
    ):
        """Create a streaming completion"""
        if not self.client:
            raise ValueError("Anthropic API key not configured")
        
        model = model or self.default_model
        anthropic_messages = self._convert_messages(messages)
        
        try:
            async with self.client.messages.stream(
                model=model,
                messages=anthropic_messages,
                max_tokens=kwargs.get("max_tokens", 1000),
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Error in streaming completion: {str(e)}")
            raise