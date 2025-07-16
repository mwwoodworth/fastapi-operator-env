"""
Codex/GPT-4 Agent Wrapper

This module provides the OpenAI GPT-4/Codex agent implementation for code
generation, technical automation, and operational tasks. Specializes in
creating functional code, system designs, and technical implementations.
"""

from typing import Dict, Any, List, Optional, Tuple
import asyncio
from datetime import datetime
import openai
from openai import AsyncOpenAI
import json
import logging

from .base import AgentNode, AgentResponse, ExecutionContext, AgentType
from ..core.settings import settings
from ..memory.memory_store import get_prompt_template


logger = logging.getLogger(__name__)


class CodexAgent(AgentNode):
    """
    GPT-4/Codex agent for technical implementation and automation.
    
    Leverages OpenAI's models for code generation, automation design,
    technical documentation, and debugging complex systems.
    """
    
    def __init__(self, node_id: str, name: str, config: Dict[str, Any]):
        super().__init__(
            node_id=node_id,
            name=name,
            agent_type=AgentType.LLM,
            capabilities=config.get("capabilities", []),
            config=config
        )
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        
        # Model configuration
        self.model = config.get("model", "gpt-4-turbo-preview")
        self.temperature = config.get("temperature", 0.1)  # Lower temp for code
        self.max_tokens = config.get("max_tokens", 8192)
        
        # Load system prompt template
        self.system_prompt_template = config.get("system_prompt_template")
        
        # Code-specific settings
        self.enable_function_calling = config.get("enable_function_calling", True)
        self.code_execution_timeout = config.get("code_execution_timeout", 30)
        
    async def execute(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """
        Execute GPT-4/Codex for technical implementation tasks.
        
        Handles code generation, automation design, debugging, and
        technical problem-solving based on context and requirements.
        """
        try:
            # Determine execution mode based on task type
            task_type = context.parameters.get("task_type", "general")
            
            if task_type in ["code_generation", "automation_design"]:
                response = await self._execute_code_generation(context, prompt, **kwargs)
            elif task_type == "debugging":
                response = await self._execute_debugging(context, prompt, **kwargs)
            elif task_type == "technical_documentation":
                response = await self._execute_technical_docs(context, prompt, **kwargs)
            else:
                response = await self._execute_general(context, prompt, **kwargs)
                
            return response
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"API Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in Codex agent: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"Unexpected error: {str(e)}"
            )
    
    async def _execute_code_generation(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute code generation with structured output."""
        # Build specialized prompt for code generation
        code_prompt = await self._build_code_prompt(context, prompt)
        
        # Define function schema for structured code output
        functions = [
            {
                "name": "generate_code",
                "description": "Generate code with metadata",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The generated code"
                        },
                        "language": {
                            "type": "string",
                            "description": "Programming language"
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required dependencies/imports"
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Brief explanation of the code"
                        },
                        "test_cases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Example test cases"
                        }
                    },
                    "required": ["code", "language"]
                }
            }
        ]
        
        # Call OpenAI with function calling
        response = await self._call_openai_with_retry(
            prompt=code_prompt,
            functions=functions if self.enable_function_calling else None,
            function_call={"name": "generate_code"} if self.enable_function_calling else None
        )
        
        # Parse structured response
        if self.enable_function_calling and response.choices[0].message.function_call:
            function_args = json.loads(response.choices[0].message.function_call.arguments)
            content = function_args
        else:
            content = response.choices[0].message.content
            
        tokens_used = response.usage.total_tokens
        context.update_token_usage(self.node_id, tokens_used)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "execution_mode": "code_generation",
                "language": content.get("language") if isinstance(content, dict) else "unknown"
            },
            requires_approval=self._requires_code_approval(content),
            confidence=0.95  # High confidence for deterministic code
        )
    
    async def _execute_debugging(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute debugging analysis with detailed insights."""
        # Extract code and error information from context
        code_to_debug = context.parameters.get("code", "")
        error_message = context.parameters.get("error", "")
        stack_trace = context.parameters.get("stack_trace", "")
        
        # Build debugging prompt
        debug_prompt = f"""
        Debug the following code issue:
        
        CODE:
        ```
        {code_to_debug}
        ```
        
        ERROR MESSAGE:
        {error_message}
        
        STACK TRACE:
        {stack_trace}
        
        {prompt}
        
        Provide:
        1. Root cause analysis
        2. Fixed code
        3. Explanation of the fix
        4. Prevention recommendations
        """
        
        response = await self._call_openai_with_retry(prompt=debug_prompt)
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        context.update_token_usage(self.node_id, tokens_used)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "execution_mode": "debugging",
                "error_type": self._classify_error(error_message)
            },
            confidence=0.9
        )
    
    async def _execute_technical_docs(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Generate technical documentation with proper structure."""
        # Load documentation template
        doc_template = await get_prompt_template("codex/technical_documentation.md")
        
        # Build documentation prompt
        doc_prompt = doc_template.format(
            code_context=context.agent_outputs.get("code", ""),
            requirements=prompt,
            project_name=context.parameters.get("project_name", "Project")
        )
        
        response = await self._call_openai_with_retry(
            prompt=doc_prompt,
            temperature=0.3  # Slightly higher for documentation
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        context.update_token_usage(self.node_id, tokens_used)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "execution_mode": "technical_documentation",
                "format": "markdown"
            },
            confidence=0.95
        )
    
    async def _execute_general(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute general technical tasks."""
        # Build enhanced prompt with technical context
        enhanced_prompt = await self._build_technical_prompt(context, prompt)
        
        response = await self._call_openai_with_retry(prompt=enhanced_prompt)
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        context.update_token_usage(self.node_id, tokens_used)
        
        return AgentResponse(
            content=content,
            success=True,
            agent_id=self.node_id,
            tokens_used=tokens_used,
            metadata={
                "model": self.model,
                "execution_mode": "general"
            },
            confidence=0.85
        )
    
    async def _build_code_prompt(self, context: ExecutionContext, base_prompt: str) -> str:
        """Build specialized prompt for code generation."""
        parts = []
        
        # Add technical specifications
        if "specifications" in context.parameters:
            parts.append("=== TECHNICAL SPECIFICATIONS ===")
            parts.append(context.parameters["specifications"])
        
        # Add existing code context
        if "existing_code" in context.parameters:
            parts.append("\n=== EXISTING CODE CONTEXT ===")
            parts.append(context.parameters["existing_code"])
        
        # Add technology stack
        if "tech_stack" in context.parameters:
            parts.append("\n=== TECHNOLOGY STACK ===")
            parts.append(", ".join(context.parameters["tech_stack"]))
        
        # Add the main request
        parts.append(f"\n=== CODE GENERATION REQUEST ===\n{base_prompt}")
        
        # Add output requirements
        parts.append("\n=== OUTPUT REQUIREMENTS ===")
        parts.append("- Include necessary imports/dependencies")
        parts.append("- Add inline comments for complex logic")
        parts.append("- Follow best practices and conventions")
        parts.append("- Make code production-ready")
        
        return "\n".join(parts)
    
    async def _build_technical_prompt(self, context: ExecutionContext, base_prompt: str) -> str:
        """Build enhanced prompt for technical tasks."""
        parts = []
        
        # Add system context
        parts.append("=== SYSTEM CONTEXT ===")
        parts.append(f"Environment: {context.parameters.get('environment', 'production')}")
        parts.append(f"Platform: {context.parameters.get('platform', 'cross-platform')}")
        
        # Add constraints
        if "constraints" in context.parameters:
            parts.append("\n=== CONSTRAINTS ===")
            for constraint in context.parameters["constraints"]:
                parts.append(f"- {constraint}")
        
        # Add the main prompt
        parts.append(f"\n=== REQUEST ===\n{base_prompt}")
        
        return "\n".join(parts)
    
    async def _call_openai_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """Call OpenAI API with retry logic."""
        # Load system prompt
        system_prompt = await self._load_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    functions=kwargs.get("functions"),
                    function_call=kwargs.get("function_call"),
                    **{k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens", "functions", "function_call"]}
                )
                return response
                
            except openai.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 5
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except openai.APIConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error, retrying... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(2)
                else:
                    raise
    
    async def _load_system_prompt(self) -> str:
        """Load system prompt for technical tasks."""
        if self.system_prompt_template:
            template = await get_prompt_template(self.system_prompt_template)
            return template
        
        return (
            "You are an expert software engineer and automation specialist. "
            "You write clean, efficient, and well-documented code. "
            "You follow best practices and consider security, performance, and maintainability. "
            "When debugging, you provide thorough analysis and clear explanations."
        )
    
    def _requires_code_approval(self, content: Any) -> bool:
        """Check if generated code requires approval before deployment."""
        if isinstance(content, dict):
            code = content.get("code", "")
        else:
            code = str(content)
            
        # Check for risky operations
        risky_operations = [
            "subprocess", "exec", "eval", "os.system",
            "DELETE", "DROP TABLE", "TRUNCATE",
            "rm -rf", "del /f"
        ]
        
        return any(op in code for op in risky_operations)
    
    def _classify_error(self, error_message: str) -> str:
        """Classify the type of error for better debugging."""
        error_lower = error_message.lower()
        
        if "syntax" in error_lower:
            return "syntax_error"
        elif "type" in error_lower:
            return "type_error"
        elif "import" in error_lower or "module" in error_lower:
            return "import_error"
        elif "index" in error_lower or "key" in error_lower:
            return "access_error"
        elif "connection" in error_lower or "timeout" in error_lower:
            return "network_error"
        else:
            return "runtime_error"
    
    async def estimate_cost(self, prompt: str) -> float:
        """Estimate cost for OpenAI API call."""
        # GPT-4 pricing (as of 2024)
        # Input: $30 per million tokens
        # Output: $60 per million tokens
        
        input_tokens = len(prompt.split()) * 1.3
        estimated_output_tokens = self.max_tokens * 0.5  # Conservative estimate
        
        input_cost = (input_tokens / 1_000_000) * 30
        output_cost = (estimated_output_tokens / 1_000_000) * 60
        
        return input_cost + output_cost
