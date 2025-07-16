"""
Generate Product Documentation Task

This task generates comprehensive product documentation using Claude,
tailored to BrainOps' specific content standards and industry focus.
"""

import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
import json
from datetime import datetime

from ..agents.claude_agent import ClaudeAgent
from ..memory.memory_store import MemoryStore
from ..core.logging import get_logger

logger = get_logger(__name__)

TASK_ID = "generate_product_docs"


async def run(
    context: Dict[str, Any],
    product_name: str,
    product_type: str,  # template, guide, checklist, etc.
    target_vertical: str,  # roofing, pm, automation, passive-income
    features: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    Generate comprehensive product documentation for BrainOps digital products.
    
    Args:
        context: Execution context with user info and settings
        product_name: Name of the product
        product_type: Type of product (template, guide, etc.)
        target_vertical: Business vertical this product serves
        features: Dictionary of product features and specifications
        
    Returns:
        Dict containing generated documentation and metadata
    """
    
    # Initialize Claude agent for content generation
    claude = ClaudeAgent()
    memory = MemoryStore()
    
    # Load product documentation template from memory
    template_prompt = await _load_prompt_template(product_type, target_vertical)
    
    # Retrieve relevant context from memory
    similar_products = await memory.search_similar_products(
        product_type=product_type,
        vertical=target_vertical,
        limit=3
    )
    
    # Build comprehensive prompt with context
    prompt = _build_documentation_prompt(
        template_prompt,
        product_name,
        product_type,
        target_vertical,
        features,
        similar_products
    )
    
    try:
        # Generate product documentation using Claude
        logger.info(f"Generating documentation for {product_name}")
        
        response = await claude.generate(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.7,
            system_prompt="You are a technical documentation expert for BrainOps, specializing in creating clear, actionable product documentation for commercial construction and automation professionals."
        )
        
        # Parse and structure the response
        documentation = _parse_documentation_response(response)
        
        # Store the generated documentation in memory
        await memory.store_product_documentation(
            product_name=product_name,
            product_type=product_type,
            vertical=target_vertical,
            documentation=documentation,
            context=context
        )
        
        # Generate SEO metadata using Gemini if needed
        if kwargs.get("generate_seo", True):
            from ..agents.gemini_agent import GeminiAgent
            gemini = GeminiAgent()
            
            seo_data = await gemini.generate_seo_metadata(
                content=documentation["main_content"],
                product_name=product_name,
                target_keywords=kwargs.get("target_keywords", [])
            )
            
            documentation["seo_metadata"] = seo_data
        
        return {
            "status": "success",
            "product_name": product_name,
            "documentation": documentation,
            "generated_at": datetime.utcnow().isoformat(),
            "task_id": TASK_ID
        }
        
    except Exception as e:
        logger.error(f"Error generating product documentation: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "task_id": TASK_ID
        }


async def stream(
    context: Dict[str, Any],
    **kwargs
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream documentation generation progress for real-time updates.
    """
    
    # Yield initial status
    yield {
        "type": "status",
        "message": "Initializing documentation generation...",
        "progress": 0
    }
    
    # This would integrate with Claude's streaming API
    # For now, we'll simulate progress updates
    steps = [
        ("Analyzing product specifications", 20),
        ("Loading documentation templates", 40),
        ("Generating main content", 60),
        ("Creating implementation guides", 80),
        ("Finalizing and formatting", 100)
    ]
    
    for step, progress in steps:
        await asyncio.sleep(1)  # Simulate processing time
        yield {
            "type": "progress",
            "message": step,
            "progress": progress
        }
    
    # Run the actual generation
    result = await run(context, **kwargs)
    yield {
        "type": "complete",
        "result": result
    }


async def _load_prompt_template(product_type: str, vertical: str) -> str:
    """
    Load the appropriate prompt template based on product type and vertical.
    """
    # In production, this would load from prompt_templates/claude/
    template_path = f"prompt_templates/claude/{vertical}_{product_type}_docs.md"
    
    # For now, return a base template
    return """
    Generate comprehensive product documentation for a {product_type} in the {vertical} industry.
    
    Follow BrainOps content standards:
    - Clear, actionable language for professionals under pressure
    - Focus on practical implementation
    - Include specific use cases and ROI metrics
    - Structure for quick scanning and reference
    """


def _build_documentation_prompt(
    template: str,
    product_name: str,
    product_type: str,
    vertical: str,
    features: Dict[str, Any],
    similar_products: list
) -> str:
    """
    Build a comprehensive prompt for documentation generation.
    """
    
    # Format the template with product details
    prompt = template.format(
        product_type=product_type,
        vertical=vertical
    )
    
    # Add product specifications
    prompt += f"\n\nProduct Name: {product_name}\n"
    prompt += "\nKey Features:\n"
    for feature, details in features.items():
        prompt += f"- {feature}: {details}\n"
    
    # Add context from similar products
    if similar_products:
        prompt += "\n\nReference similar successful products:\n"
        for product in similar_products:
            prompt += f"- {product.get('name', 'Unknown')}: {product.get('key_value_prop', '')}\n"
    
    return prompt


def _parse_documentation_response(response: str) -> Dict[str, Any]:
    """
    Parse Claude's response into structured documentation.
    """
    
    # In production, this would use more sophisticated parsing
    # For now, we'll structure the response into sections
    
    sections = {
        "main_content": response,
        "executive_summary": _extract_section(response, "Executive Summary"),
        "key_features": _extract_section(response, "Key Features"),
        "implementation_guide": _extract_section(response, "Implementation Guide"),
        "use_cases": _extract_section(response, "Use Cases"),
        "roi_metrics": _extract_section(response, "ROI Metrics"),
        "technical_specifications": _extract_section(response, "Technical Specifications")
    }
    
    return sections


def _extract_section(content: str, section_name: str) -> Optional[str]:
    """
    Extract a specific section from the documentation content.
    """
    # Simple extraction logic - in production would use regex or markdown parsing
    lines = content.split('\n')
    in_section = False
    section_content = []
    
    for line in lines:
        if section_name.lower() in line.lower() and line.startswith('#'):
            in_section = True
            continue
        elif in_section and line.startswith('#'):
            break
        elif in_section:
            section_content.append(line)
    
    return '\n'.join(section_content).strip() if section_content else None