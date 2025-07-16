"""
Gemini Agent Wrapper

This module provides the Google Gemini agent implementation for strategic
analysis, SEO optimization, and content enhancement tasks. Specializes in
market insights, trend analysis, and multi-modal content processing.
"""

from typing import Dict, Any, List, Optional, Union
import asyncio
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import logging

from .base import AgentNode, AgentResponse, ExecutionContext, AgentType
from ..core.settings import settings
from ..memory.memory_store import get_prompt_template


logger = logging.getLogger(__name__)


class GeminiAgent(AgentNode):
    """
    Gemini agent for strategic intelligence and content optimization.
    
    Leverages Google's Gemini model for market analysis, SEO optimization,
    trend identification, and multi-modal content understanding.
    """
    
    def __init__(self, node_id: str, name: str, config: Dict[str, Any]):
        super().__init__(
            node_id=node_id,
            name=name,
            agent_type=AgentType.LLM,
            capabilities=config.get("capabilities", []),
            config=config
        )
        
        # Configure Gemini API
        genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
        
        # Model configuration
        self.model_name = config.get("model", "gemini-pro")
        self.temperature = config.get("temperature", 0.5)
        self.max_tokens = config.get("max_tokens", 2048)
        
        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
                "top_p": 0.95,
                "top_k": 40
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
        # Load system prompt template
        self.system_prompt_template = config.get("system_prompt_template")
        
        # SEO and analysis specific settings
        self.enable_web_grounding = config.get("enable_web_grounding", True)
        self.analysis_depth = config.get("analysis_depth", "comprehensive")
        
    async def execute(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """
        Execute Gemini for strategic analysis and optimization tasks.
        
        Handles market analysis, SEO optimization, trend identification,
        and strategic planning based on context and requirements.
        """
        try:
            # Determine execution mode based on task type
            task_type = context.parameters.get("task_type", "general")
            
            if task_type == "market_analysis":
                response = await self._execute_market_analysis(context, prompt, **kwargs)
            elif task_type == "seo_optimization":
                response = await self._execute_seo_optimization(context, prompt, **kwargs)
            elif task_type == "trend_identification":
                response = await self._execute_trend_analysis(context, prompt, **kwargs)
            elif task_type == "strategic_planning":
                response = await self._execute_strategic_planning(context, prompt, **kwargs)
            else:
                response = await self._execute_general_analysis(context, prompt, **kwargs)
                
            return response
            
        except Exception as e:
            logger.error(f"Gemini execution error: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"Execution error: {str(e)}"
            )
    
    async def _execute_market_analysis(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute comprehensive market analysis."""
        # Build market analysis prompt
        analysis_prompt = await self._build_market_analysis_prompt(context, prompt)
        
        # Execute with Gemini
        response = await self._call_gemini_with_retry(analysis_prompt)
        
        # Parse response for structured insights
        content = self._parse_market_insights(response.text)
        
        # Estimate token usage (Gemini doesn't provide exact counts)
        estimated_tokens = self._estimate_tokens(analysis_prompt, response.text)
        context.update_token_usage(self.node_id, estimated_tokens)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=estimated_tokens,
            metadata={
                "model": self.model_name,
                "execution_mode": "market_analysis",
                "analysis_depth": self.analysis_depth,
                "insights_count": len(content.get("insights", []))
            },
            confidence=0.85
        )
    
    async def _execute_seo_optimization(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute SEO optimization analysis."""
        # Extract content to optimize
        content_to_optimize = context.parameters.get("content", "")
        target_keywords = context.parameters.get("keywords", [])
        target_audience = context.parameters.get("audience", "general")
        
        # Build SEO optimization prompt
        seo_prompt = f"""
        Perform comprehensive SEO optimization analysis:
        
        CONTENT TO OPTIMIZE:
        {content_to_optimize}
        
        TARGET KEYWORDS:
        {', '.join(target_keywords)}
        
        TARGET AUDIENCE:
        {target_audience}
        
        {prompt}
        
        Provide:
        1. SEO score (0-100)
        2. Keyword density analysis
        3. Readability assessment
        4. Meta tag recommendations
        5. Content structure improvements
        6. Internal/external linking suggestions
        7. Schema markup recommendations
        """
        
        response = await self._call_gemini_with_retry(seo_prompt)
        
        # Structure SEO recommendations
        content = self._structure_seo_recommendations(response.text)
        
        estimated_tokens = self._estimate_tokens(seo_prompt, response.text)
        context.update_token_usage(self.node_id, estimated_tokens)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=estimated_tokens,
            metadata={
                "model": self.model_name,
                "execution_mode": "seo_optimization",
                "keyword_count": len(target_keywords),
                "seo_score": content.get("seo_score", 0)
            },
            confidence=0.9
        )
    
    async def _execute_trend_analysis(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute trend identification and analysis."""
        # Build trend analysis prompt with temporal context
        trend_prompt = await self._build_trend_analysis_prompt(context, prompt)
        
        # Execute analysis
        response = await self._call_gemini_with_retry(trend_prompt)
        
        # Extract and structure trends
        content = self._extract_trends(response.text)
        
        estimated_tokens = self._estimate_tokens(trend_prompt, response.text)
        context.update_token_usage(self.node_id, estimated_tokens)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=estimated_tokens,
            metadata={
                "model": self.model_name,
                "execution_mode": "trend_analysis",
                "trends_identified": len(content.get("trends", [])),
                "time_horizon": context.parameters.get("time_horizon", "6_months")
            },
            confidence=0.8  # Trends are inherently uncertain
        )
    
    async def _execute_strategic_planning(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute strategic planning and recommendations."""
        # Gather strategic context
        business_context = {
            "objectives": context.parameters.get("objectives", []),
            "constraints": context.parameters.get("constraints", []),
            "resources": context.parameters.get("resources", {}),
            "timeline": context.parameters.get("timeline", "12_months"),
            "risk_tolerance": context.parameters.get("risk_tolerance", "moderate")
        }
        
        # Build strategic planning prompt
        strategy_prompt = self._build_strategy_prompt(business_context, prompt)
        
        response = await self._call_gemini_with_retry(strategy_prompt)
        
        # Structure strategic recommendations
        content = self._structure_strategic_plan(response.text)
        
        estimated_tokens = self._estimate_tokens(strategy_prompt, response.text)
        context.update_token_usage(self.node_id, estimated_tokens)
        
        # Strategic decisions require approval
        requires_approval = context.parameters.get("strategic_impact") == "high"
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=estimated_tokens,
            metadata={
                "model": self.model_name,
                "execution_mode": "strategic_planning",
                "strategy_horizon": business_context["timeline"],
                "risk_level": business_context["risk_tolerance"]
            },
            requires_approval=requires_approval,
            confidence=0.75  # Strategic planning has inherent uncertainty
        )
    
    async def _execute_general_analysis(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute general analysis tasks."""
        # Build enhanced prompt with analytical context
        enhanced_prompt = await self._build_analytical_prompt(context, prompt)
        
        response = await self._call_gemini_with_retry(enhanced_prompt)
        
        content = response.text
        estimated_tokens = self._estimate_tokens(enhanced_prompt, content)
        context.update_token_usage(self.node_id, estimated_tokens)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=estimated_tokens,
            metadata={
                "model": self.model_name,
                "execution_mode": "general_analysis"
            },
            confidence=0.85
        )
    
    async def _build_market_analysis_prompt(
        self,
        context: ExecutionContext,
        base_prompt: str
    ) -> str:
        """Build comprehensive market analysis prompt."""
        parts = []
        
        # Add market context
        parts.append("=== MARKET ANALYSIS CONTEXT ===")
        parts.append(f"Industry: {context.parameters.get('industry', 'General')}")
        parts.append(f"Geographic Focus: {context.parameters.get('geography', 'Global')}")
        parts.append(f"Time Period: {context.parameters.get('time_period', 'Current')}")
        
        # Add competitive landscape
        if "competitors" in context.parameters:
            parts.append("\n=== COMPETITIVE LANDSCAPE ===")
            for competitor in context.parameters["competitors"]:
                parts.append(f"- {competitor}")
        
        # Add analysis objectives
        parts.append("\n=== ANALYSIS OBJECTIVES ===")
        parts.append(base_prompt)
        
        # Add output requirements
        parts.append("\n=== REQUIRED INSIGHTS ===")
        parts.append("1. Market size and growth projections")
        parts.append("2. Key trends and drivers")
        parts.append("3. Competitive dynamics")
        parts.append("4. Opportunities and threats")
        parts.append("5. Strategic recommendations")
        
        return "\n".join(parts)
    
    async def _build_trend_analysis_prompt(
        self,
        context: ExecutionContext,
        base_prompt: str
    ) -> str:
        """Build trend analysis prompt with temporal context."""
        parts = []
        
        # Add temporal context
        parts.append("=== TREND ANALYSIS PARAMETERS ===")
        parts.append(f"Analysis Period: {context.parameters.get('time_horizon', '6_months')}")
        parts.append(f"Data Sources: {', '.join(context.parameters.get('data_sources', ['market data']))}")
        parts.append(f"Industry Focus: {context.parameters.get('industry', 'General')}")
        
        # Add historical context if available
        if context.memories:
            parts.append("\n=== HISTORICAL CONTEXT ===")
            for memory in context.memories[:3]:
                parts.append(f"- {memory.title}: {memory.content[:100]}...")
        
        # Add main request
        parts.append(f"\n=== TREND IDENTIFICATION REQUEST ===\n{base_prompt}")
        
        return "\n".join(parts)
    
    def _build_strategy_prompt(
        self,
        business_context: Dict[str, Any],
        base_prompt: str
    ) -> str:
        """Build strategic planning prompt."""
        parts = []
        
        # Add business context
        parts.append("=== STRATEGIC PLANNING CONTEXT ===")
        parts.append(f"Timeline: {business_context['timeline']}")
        parts.append(f"Risk Tolerance: {business_context['risk_tolerance']}")
        
        # Add objectives
        parts.append("\n=== BUSINESS OBJECTIVES ===")
        for obj in business_context["objectives"]:
            parts.append(f"- {obj}")
        
        # Add constraints
        parts.append("\n=== CONSTRAINTS ===")
        for constraint in business_context["constraints"]:
            parts.append(f"- {constraint}")
        
        # Add main request
        parts.append(f"\n=== STRATEGIC PLANNING REQUEST ===\n{base_prompt}")
        
        return "\n".join(parts)
    
    async def _build_analytical_prompt(
        self,
        context: ExecutionContext,
        base_prompt: str
    ) -> str:
        """Build enhanced analytical prompt."""
        # Load system prompt if available
        system_context = ""
        if self.system_prompt_template:
            system_context = await get_prompt_template(self.system_prompt_template)
        
        parts = [system_context] if system_context else []
        
        # Add analytical context
        parts.append("=== ANALYTICAL CONTEXT ===")
        parts.append(f"Analysis Type: {context.parameters.get('analysis_type', 'general')}")
        parts.append(f"Depth: {self.analysis_depth}")
        
        # Add the main request
        parts.append(f"\n=== ANALYSIS REQUEST ===\n{base_prompt}")
        
        return "\n".join(parts)
    
    async def _call_gemini_with_retry(
        self,
        prompt: str,
        max_retries: int = 3
    ) -> Any:
        """Call Gemini API with retry logic."""
        for attempt in range(max_retries):
            try:
                # Generate content with Gemini
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt
                )
                
                # Check if response was blocked
                if not response.text:
                    logger.warning("Gemini response was blocked by safety filters")
                    raise Exception("Response blocked by safety filters")
                
                return response
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Gemini API error, retrying in {wait_time}s: {str(e)}")
                    await asyncio.sleep(wait_time)
                else:
                    raise
    
    def _parse_market_insights(self, response_text: str) -> Dict[str, Any]:
        """Parse market analysis response into structured insights."""
        # Simple parsing - in production, use more sophisticated NLP
        insights = {
            "market_size": self._extract_metric(response_text, "market size"),
            "growth_rate": self._extract_metric(response_text, "growth rate"),
            "insights": self._extract_bullet_points(response_text),
            "opportunities": self._extract_section(response_text, "opportunities"),
            "threats": self._extract_section(response_text, "threats"),
            "recommendations": self._extract_section(response_text, "recommendations")
        }
        return insights
    
    def _structure_seo_recommendations(self, response_text: str) -> Dict[str, Any]:
        """Structure SEO optimization recommendations."""
        # Extract SEO score if mentioned
        seo_score = 75  # Default
        if "seo score" in response_text.lower():
            # Simple extraction - improve in production
            import re
            score_match = re.search(r'seo score[:\s]+(\d+)', response_text.lower())
            if score_match:
                seo_score = int(score_match.group(1))
        
        return {
            "seo_score": seo_score,
            "recommendations": response_text,
            "priority_actions": self._extract_bullet_points(response_text)[:5]
        }
    
    def _extract_trends(self, response_text: str) -> Dict[str, Any]:
        """Extract and structure trend information."""
        return {
            "trends": self._extract_bullet_points(response_text),
            "analysis": response_text,
            "confidence_level": "moderate"  # Could be enhanced with sentiment analysis
        }
    
    def _structure_strategic_plan(self, response_text: str) -> Dict[str, Any]:
        """Structure strategic planning response."""
        return {
            "strategic_plan": response_text,
            "key_initiatives": self._extract_bullet_points(response_text)[:5],
            "timeline": self._extract_section(response_text, "timeline"),
            "success_metrics": self._extract_section(response_text, "metrics")
        }
    
    def _extract_metric(self, text: str, metric_name: str) -> Optional[str]:
        """Extract a specific metric from text."""
        # Simple implementation - enhance with NLP in production
        lines = text.split('\n')
        for line in lines:
            if metric_name.lower() in line.lower():
                return line.strip()
        return None
    
    def _extract_bullet_points(self, text: str) -> List[str]:
        """Extract bullet points from text."""
        points = []
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(('-', '•', '*', '1.', '2.', '3.')):
                points.append(line.lstrip('-•*0123456789. '))
        return points
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a named section from text."""
        # Simple section extraction - enhance in production
        lower_text = text.lower()
        section_start = lower_text.find(section_name.lower())
        if section_start == -1:
            return ""
        
        # Find next section or end
        section_text = text[section_start:]
        lines = section_text.split('\n')
        section_content = []
        
        for i, line in enumerate(lines[1:], 1):
            if line.strip() and line[0].isupper() and ':' in line:
                break
            section_content.append(line)
        
        return '\n'.join(section_content).strip()
    
    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """Estimate token usage for Gemini (doesn't provide exact counts)."""
        # Rough estimation: 1 token ≈ 4 characters
        total_chars = len(prompt) + len(response)
        return total_chars // 4
    
    async def estimate_cost(self, prompt: str) -> float:
        """Estimate cost for Gemini API call."""
        # Gemini pricing varies by model
        # Using approximate rates for Gemini Pro
        estimated_tokens = len(prompt.split()) * 1.3 + (self.max_tokens * 0.5)
        
        # Approximate cost per million tokens
        cost_per_million = 0.50  # Placeholder - check current pricing
        
        return (estimated_tokens / 1_000_000) * cost_per_million
