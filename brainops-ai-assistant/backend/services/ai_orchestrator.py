"""AI Orchestrator for managing multiple AI models and interactions."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from enum import Enum

from loguru import logger
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from core.config import settings
from utils.audit import AuditLogger


class AIModel(str, Enum):
    """Supported AI models."""
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"


class AIProvider(str, Enum):
    """AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AIOrchestrator:
    """Orchestrate AI model interactions and manage model selection."""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.audit_logger = AuditLogger()
        
        # Model pricing (per 1K tokens)
        self.model_pricing = {
            AIModel.GPT_4_TURBO: {"input": 0.01, "output": 0.03},
            AIModel.GPT_4: {"input": 0.03, "output": 0.06},
            AIModel.GPT_3_5_TURBO: {"input": 0.0015, "output": 0.002},
            AIModel.CLAUDE_3_OPUS: {"input": 0.015, "output": 0.075},
            AIModel.CLAUDE_3_SONNET: {"input": 0.003, "output": 0.015},
            AIModel.CLAUDE_3_HAIKU: {"input": 0.00025, "output": 0.00125}
        }
        
        # Model capabilities
        self.model_capabilities = {
            AIModel.GPT_4_TURBO: {
                "context_length": 128000,
                "reasoning": "excellent",
                "coding": "excellent",
                "analysis": "excellent",
                "speed": "medium"
            },
            AIModel.GPT_4: {
                "context_length": 8192,
                "reasoning": "excellent",
                "coding": "excellent",
                "analysis": "excellent",
                "speed": "slow"
            },
            AIModel.GPT_3_5_TURBO: {
                "context_length": 4096,
                "reasoning": "good",
                "coding": "good",
                "analysis": "good",
                "speed": "fast"
            },
            AIModel.CLAUDE_3_OPUS: {
                "context_length": 200000,
                "reasoning": "excellent",
                "coding": "excellent",
                "analysis": "excellent",
                "speed": "slow"
            },
            AIModel.CLAUDE_3_SONNET: {
                "context_length": 200000,
                "reasoning": "very good",
                "coding": "very good",
                "analysis": "very good",
                "speed": "medium"
            },
            AIModel.CLAUDE_3_HAIKU: {
                "context_length": 200000,
                "reasoning": "good",
                "coding": "good",
                "analysis": "good",
                "speed": "fast"
            }
        }
        
        # Default model selection rules
        self.default_rules = {
            "chat": AIModel.GPT_4_TURBO,
            "code_review": AIModel.CLAUDE_3_OPUS,
            "analysis": AIModel.CLAUDE_3_SONNET,
            "quick_query": AIModel.GPT_3_5_TURBO,
            "long_document": AIModel.CLAUDE_3_OPUS,
            "reasoning": AIModel.GPT_4_TURBO
        }
    
    async def query(
        self,
        prompt: str,
        model: Optional[Union[str, AIModel]] = None,
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        query_type: str = "chat"
    ) -> Dict[str, Any]:
        """Execute an AI query with automatic model selection."""
        start_time = time.time()
        
        try:
            # Select model if not provided
            if not model:
                model = self._select_model(prompt, query_type, context)
            
            if isinstance(model, str):
                model = AIModel(model)
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if context:
                messages.extend(context)
            
            messages.append({"role": "user", "content": prompt})
            
            # Execute query based on provider
            provider = self._get_provider(model)
            
            if provider == AIProvider.OPENAI:
                response = await self._query_openai(model, messages, temperature, max_tokens)
            elif provider == AIProvider.ANTHROPIC:
                response = await self._query_anthropic(model, messages, temperature, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Calculate metrics
            duration = time.time() - start_time
            cost = self._calculate_cost(model, response.get("usage", {}))
            
            # Log the interaction
            await self.audit_logger.log_ai_interaction(
                user_id=user_id or 0,
                session_id=session_id or "direct",
                interaction_type=query_type,
                model=model.value,
                tokens_used=response.get("usage", {}).get("total_tokens"),
                cost=cost,
                duration_ms=duration * 1000,
                success=True
            )
            
            return {
                "response": response["content"],
                "model": model.value,
                "usage": response.get("usage", {}),
                "cost": cost,
                "duration_ms": duration * 1000,
                "provider": provider.value
            }
            
        except Exception as e:
            logger.error(f"AI query failed: {e}")
            
            # Log failed interaction
            await self.audit_logger.log_ai_interaction(
                user_id=user_id or 0,
                session_id=session_id or "direct",
                interaction_type=query_type,
                model=model.value if model else "unknown",
                duration_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e)
            )
            
            raise
    
    async def stream_query(
        self,
        prompt: str,
        model: Optional[Union[str, AIModel]] = None,
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        query_type: str = "chat"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream an AI query response."""
        start_time = time.time()
        
        try:
            # Select model if not provided
            if not model:
                model = self._select_model(prompt, query_type, context)
            
            if isinstance(model, str):
                model = AIModel(model)
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if context:
                messages.extend(context)
            
            messages.append({"role": "user", "content": prompt})
            
            # Execute streaming query
            provider = self._get_provider(model)
            full_response = ""
            
            if provider == AIProvider.OPENAI:
                async for chunk in self._stream_openai(model, messages, temperature, max_tokens):
                    full_response += chunk.get("content", "")
                    yield chunk
            elif provider == AIProvider.ANTHROPIC:
                async for chunk in self._stream_anthropic(model, messages, temperature, max_tokens):
                    full_response += chunk.get("content", "")
                    yield chunk
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Calculate final metrics
            duration = time.time() - start_time
            estimated_tokens = len(full_response.split()) * 1.3  # Rough estimate
            cost = self._calculate_cost(model, {"total_tokens": estimated_tokens})
            
            # Log the interaction
            await self.audit_logger.log_ai_interaction(
                user_id=user_id or 0,
                session_id=session_id or "direct",
                interaction_type=f"stream_{query_type}",
                model=model.value,
                tokens_used=int(estimated_tokens),
                cost=cost,
                duration_ms=duration * 1000,
                success=True
            )
            
        except Exception as e:
            logger.error(f"AI stream query failed: {e}")
            
            # Log failed interaction
            await self.audit_logger.log_ai_interaction(
                user_id=user_id or 0,
                session_id=session_id or "direct",
                interaction_type=f"stream_{query_type}",
                model=model.value if model else "unknown",
                duration_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e)
            )
            
            raise
    
    async def analyze_code(
        self,
        code: str,
        language: str = "python",
        analysis_type: str = "review",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Analyze code using the best model for code analysis."""
        system_prompt = f"""You are an expert code reviewer. Analyze the following {language} code and provide:

1. Code quality assessment
2. Potential bugs or issues
3. Performance optimizations
4. Security considerations
5. Best practices recommendations
6. Refactoring suggestions

Be specific and actionable in your feedback."""
        
        return await self.query(
            prompt=f"Please analyze this {language} code:\n\n```{language}\n{code}\n```",
            model=AIModel.CLAUDE_3_OPUS,
            system_prompt=system_prompt,
            query_type="code_review",
            user_id=user_id
        )
    
    async def generate_documentation(
        self,
        code: str,
        language: str = "python",
        doc_type: str = "docstring",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate documentation for code."""
        system_prompt = f"""You are a documentation expert. Generate comprehensive {doc_type} documentation for the provided {language} code.

Include:
- Clear description of functionality
- Parameter descriptions
- Return value descriptions
- Usage examples
- Error handling information"""
        
        return await self.query(
            prompt=f"Generate {doc_type} documentation for this {language} code:\n\n```{language}\n{code}\n```",
            model=AIModel.CLAUDE_3_SONNET,
            system_prompt=system_prompt,
            query_type="documentation",
            user_id=user_id
        )
    
    async def explain_error(
        self,
        error_message: str,
        code_context: Optional[str] = None,
        language: str = "python",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Explain an error and provide solutions."""
        system_prompt = f"""You are a debugging expert. Analyze the error message and provide:

1. Clear explanation of what the error means
2. Likely causes of the error
3. Step-by-step solutions
4. Prevention strategies
5. Code examples if helpful"""
        
        context_str = f"\n\nCode context:\n```{language}\n{code_context}\n```" if code_context else ""
        
        return await self.query(
            prompt=f"Explain this error and provide solutions:\n\n{error_message}{context_str}",
            model=AIModel.GPT_4_TURBO,
            system_prompt=system_prompt,
            query_type="error_explanation",
            user_id=user_id
        )
    
    async def summarize_document(
        self,
        document: str,
        summary_type: str = "brief",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Summarize a document."""
        system_prompt = f"""You are a document summarization expert. Create a {summary_type} summary of the provided document.

Include:
- Key points and main themes
- Important conclusions
- Action items if present
- Relevant details based on summary type"""
        
        # Use Claude for long documents
        model = AIModel.CLAUDE_3_OPUS if len(document) > 10000 else AIModel.CLAUDE_3_SONNET
        
        return await self.query(
            prompt=f"Please provide a {summary_type} summary of this document:\n\n{document}",
            model=model,
            system_prompt=system_prompt,
            query_type="summarization",
            user_id=user_id
        )
    
    async def get_model_recommendations(
        self,
        query_type: str,
        content_length: int,
        priority: str = "balanced"
    ) -> List[Dict[str, Any]]:
        """Get model recommendations for a specific use case."""
        recommendations = []
        
        for model, capabilities in self.model_capabilities.items():
            score = self._calculate_model_score(model, query_type, content_length, priority)
            
            recommendations.append({
                "model": model.value,
                "score": score,
                "capabilities": capabilities,
                "pricing": self.model_pricing[model],
                "suitable": score > 0.6
            })
        
        # Sort by score
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        return recommendations
    
    async def get_usage_statistics(
        self,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get AI usage statistics."""
        try:
            from datetime import timedelta
            from core.database import get_db
            from models.db import AuditLog
            from sqlalchemy import select, func
            
            since_date = datetime.utcnow() - timedelta(days=days)
            
            async with get_db() as db:
                query = select(AuditLog).where(
                    AuditLog.action == "ai_interaction",
                    AuditLog.timestamp >= since_date
                )
                
                if user_id:
                    query = query.where(AuditLog.user_id == user_id)
                
                result = await db.execute(query)
                logs = result.scalars().all()
                
                # Calculate statistics
                total_interactions = len(logs)
                total_tokens = sum(log.details.get("tokens_used", 0) for log in logs)
                total_cost = sum(log.details.get("cost_usd", 0) for log in logs)
                
                # By model
                model_usage = {}
                for log in logs:
                    model = log.details.get("model", "unknown")
                    if model not in model_usage:
                        model_usage[model] = {
                            "interactions": 0,
                            "tokens": 0,
                            "cost": 0
                        }
                    
                    model_usage[model]["interactions"] += 1
                    model_usage[model]["tokens"] += log.details.get("tokens_used", 0)
                    model_usage[model]["cost"] += log.details.get("cost_usd", 0)
                
                # By interaction type
                type_usage = {}
                for log in logs:
                    interaction_type = log.details.get("interaction_type", "unknown")
                    type_usage[interaction_type] = type_usage.get(interaction_type, 0) + 1
                
                return {
                    "period_days": days,
                    "total_interactions": total_interactions,
                    "total_tokens": total_tokens,
                    "total_cost_usd": total_cost,
                    "average_cost_per_interaction": total_cost / total_interactions if total_interactions > 0 else 0,
                    "by_model": model_usage,
                    "by_type": type_usage
                }
                
        except Exception as e:
            logger.error(f"Error getting usage statistics: {e}")
            return {}
    
    # Helper methods
    def _select_model(
        self,
        prompt: str,
        query_type: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> AIModel:
        """Select the best model for a query."""
        # Check default rules
        if query_type in self.default_rules:
            return self.default_rules[query_type]
        
        # Calculate content length
        content_length = len(prompt)
        if context:
            content_length += sum(len(msg.get("content", "")) for msg in context)
        
        # Use long context model for large content
        if content_length > 50000:
            return AIModel.CLAUDE_3_OPUS
        
        # Use fast model for simple queries
        if content_length < 1000 and query_type == "quick_query":
            return AIModel.GPT_3_5_TURBO
        
        # Default to balanced model
        return AIModel.GPT_4_TURBO
    
    def _get_provider(self, model: AIModel) -> AIProvider:
        """Get the provider for a model."""
        if model.value.startswith("gpt"):
            return AIProvider.OPENAI
        elif model.value.startswith("claude"):
            return AIProvider.ANTHROPIC
        else:
            raise ValueError(f"Unknown model: {model}")
    
    async def _query_openai(
        self,
        model: AIModel,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """Query OpenAI API."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=model.value,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            return {
                "content": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"OpenAI query failed: {e}")
            raise
    
    async def _query_anthropic(
        self,
        model: AIModel,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        """Query Anthropic API."""
        try:
            # Convert system message format
            system_prompt = None
            claude_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    claude_messages.append(msg)
            
            response = await self.anthropic_client.messages.create(
                model=model.value,
                max_tokens=max_tokens or 4000,
                temperature=temperature,
                system=system_prompt,
                messages=claude_messages
            )
            
            return {
                "content": response.content[0].text,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Anthropic query failed: {e}")
            raise
    
    async def _stream_openai(
        self,
        model: AIModel,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream OpenAI response."""
        try:
            stream = await self.openai_client.chat.completions.create(
                model=model.value,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {
                        "content": chunk.choices[0].delta.content,
                        "model": model.value,
                        "provider": "openai"
                    }
                    
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            raise
    
    async def _stream_anthropic(
        self,
        model: AIModel,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream Anthropic response."""
        try:
            # Convert system message format
            system_prompt = None
            claude_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_prompt = msg["content"]
                else:
                    claude_messages.append(msg)
            
            stream = await self.anthropic_client.messages.create(
                model=model.value,
                max_tokens=max_tokens or 4000,
                temperature=temperature,
                system=system_prompt,
                messages=claude_messages,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.type == "content_block_delta":
                    yield {
                        "content": chunk.delta.text,
                        "model": model.value,
                        "provider": "anthropic"
                    }
                    
        except Exception as e:
            logger.error(f"Anthropic stream failed: {e}")
            raise
    
    def _calculate_cost(self, model: AIModel, usage: Dict[str, Any]) -> float:
        """Calculate cost for a query."""
        if model not in self.model_pricing:
            return 0.0
        
        pricing = self.model_pricing[model]
        
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def _calculate_model_score(
        self,
        model: AIModel,
        query_type: str,
        content_length: int,
        priority: str
    ) -> float:
        """Calculate suitability score for a model."""
        capabilities = self.model_capabilities[model]
        pricing = self.model_pricing[model]
        
        score = 0.0
        
        # Context length suitability
        if content_length <= capabilities["context_length"]:
            score += 0.3
        else:
            score -= 0.5  # Penalize if content too long
        
        # Task-specific scoring
        task_scores = {
            "code_review": {"reasoning": 0.4, "coding": 0.4, "analysis": 0.2},
            "chat": {"reasoning": 0.3, "speed": 0.4, "analysis": 0.3},
            "analysis": {"analysis": 0.6, "reasoning": 0.4},
            "quick_query": {"speed": 0.7, "reasoning": 0.3}
        }
        
        if query_type in task_scores:
            weights = task_scores[query_type]
            for capability, weight in weights.items():
                capability_score = self._capability_to_score(capabilities.get(capability, "good"))
                score += weight * capability_score
        
        # Priority adjustments
        if priority == "cost":
            # Lower cost is better
            avg_cost = (pricing["input"] + pricing["output"]) / 2
            score += max(0, (0.1 - avg_cost) * 10)  # Normalize cost factor
        elif priority == "speed":
            speed_score = self._capability_to_score(capabilities.get("speed", "medium"))
            score += 0.3 * speed_score
        elif priority == "quality":
            reasoning_score = self._capability_to_score(capabilities.get("reasoning", "good"))
            score += 0.3 * reasoning_score
        
        return min(1.0, max(0.0, score))  # Clamp between 0 and 1
    
    def _capability_to_score(self, capability: str) -> float:
        """Convert capability string to numeric score."""
        capability_map = {
            "excellent": 1.0,
            "very good": 0.8,
            "good": 0.6,
            "medium": 0.5,
            "fair": 0.4,
            "poor": 0.2,
            "fast": 0.9,
            "slow": 0.3
        }
        return capability_map.get(capability, 0.5)