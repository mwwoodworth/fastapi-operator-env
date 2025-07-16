"""
Generate product documentation task implementation.
Creates comprehensive documentation for digital products and templates.
"""

import logging
from typing import Dict, Any, AsyncIterator, List
from datetime import datetime
import json

from ..agents.claude_agent import ClaudeAgent
from ..agents.codex_agent import CodexAgent
from ..agents.base import AgentContext
from ..memory.memory_store import MemoryStore
from .base_task import BaseTask, TaskResult

logger = logging.getLogger(__name__)

# Task identifier for registration
TASK_ID = "generate_product_docs"


class GenerateProductDocsTask(BaseTask):
    """
    Generates comprehensive product documentation for BrainOps digital products.
    
    This task:
    1. Analyzes product features and functionality
    2. Creates user guides and tutorials
    3. Generates API documentation if applicable
    4. Produces quick start guides
    5. Creates troubleshooting documentation
    """
    
    # Task metadata
    METADATA = {
        "category": "documentation",
        "requires_approval": False,
        "estimated_duration_seconds": 240,
        "documentation_types": ["user_guide", "api_docs", "quick_start", "troubleshooting"]
    }
    
    def __init__(self):
        super().__init__(task_id=TASK_ID)
        self.claude_agent = ClaudeAgent()
        self.codex_agent = CodexAgent()
        self.memory_store = MemoryStore()
        
    async def run(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute product documentation generation.
        
        Args:
            context: Must include:
                - product_name: Name of the product
                - product_type: Type of product (template, automation, tool, etc.)
                - features: List of product features
                - target_audience: Who will use the product
                - documentation_types: List of doc types to generate
                - technical_details: Optional technical specifications
                
        Returns:
            TaskResult with generated documentation
        """
        try:
            # Validate required context
            self._validate_context(context)
            
            # Extract parameters
            product_name = context['product_name']
            product_type = context['product_type']
            features = context['features']
            audience = context['target_audience']
            doc_types = context.get('documentation_types', ['user_guide', 'quick_start'])
            
            # Step 1: Analyze product structure and features
            product_analysis = await self._analyze_product(
                product_name, product_type, features, 
                context.get('technical_details', {})
            )
            
            # Step 2: Generate documentation for each type
            documentation = {}
            for doc_type in doc_types:
                if doc_type in self.METADATA['documentation_types']:
                    doc_content = await self._generate_documentation(
                        doc_type, product_name, product_analysis, audience
                    )
                    documentation[doc_type] = doc_content
            
            # Step 3: Generate code examples if technical product
            if product_type in ['automation', 'api', 'integration']:
                code_examples = await self._generate_code_examples(
                    product_name, features, context.get('technical_details', {})
                )
                documentation['code_examples'] = code_examples
            
            # Step 4: Create documentation index/TOC
            doc_index = self._create_documentation_index(documentation)
            
            # Step 5: Format for different output formats
            formatted_docs = await self._format_documentation(
                documentation, context.get('output_formats', ['markdown'])
            )
            
            # Save documentation to memory
            await self._save_documentation(product_name, formatted_docs)
            
            return TaskResult(
                success=True,
                data={
                    "product_name": product_name,
                    "documentation": formatted_docs,
                    "documentation_index": doc_index,
                    "types_generated": list(documentation.keys()),
                    "word_count": self._calculate_word_count(documentation),
                    "generated_at": datetime.utcnow().isoformat()
                },
                message=f"Successfully generated documentation for {product_name}"
            )
            
        except Exception as e:
            logger.error(f"Documentation generation failed for '{context.get('product_name')}': {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message=f"Documentation generation failed: {str(e)}"
            )
    
    async def stream(self, context: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream documentation generation progress.
        """
        try:
            # Validate
            yield {"stage": "validating", "message": "Validating product information"}
            self._validate_context(context)
            
            # Analyze product
            yield {"stage": "analyzing", "message": "Analyzing product features and structure"}
            product_analysis = await self._analyze_product(
                context['product_name'],
                context['product_type'],
                context['features'],
                context.get('technical_details', {})
            )
            yield {"stage": "analysis_complete", "message": "Product analysis complete"}
            
            # Generate each documentation type
            doc_types = context.get('documentation_types', ['user_guide', 'quick_start'])
            for i, doc_type in enumerate(doc_types):
                yield {
                    "stage": "generating_doc",
                    "message": f"Generating {doc_type}",
                    "progress": f"{i+1}/{len(doc_types)}"
                }
            
            # Complete
            yield {
                "stage": "completed",
                "message": "Documentation generation complete",
                "summary": {
                    "types_generated": doc_types,
                    "total_documents": len(doc_types)
                }
            }
            
        except Exception as e:
            yield {
                "stage": "error",
                "message": f"Error: {str(e)}",
                "error": str(e)
            }
    
    def _validate_context(self, context: Dict[str, Any]) -> None:
        """Validate required context fields."""
        required_fields = ['product_name', 'product_type', 'features', 'target_audience']
        missing = [field for field in required_fields if field not in context]
        
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
            
        # Validate features is a list
        if not isinstance(context['features'], list) or not context['features']:
            raise ValueError("Features must be a non-empty list")
            
        # Validate documentation types
        if 'documentation_types' in context:
            invalid_types = [
                t for t in context['documentation_types']
                if t not in self.METADATA['documentation_types']
            ]
            if invalid_types:
                raise ValueError(f"Invalid documentation types: {', '.join(invalid_types)}")
    
    async def _analyze_product(
        self,
        product_name: str,
        product_type: str,
        features: List[str],
        technical_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze product to understand documentation needs."""
        # Create analysis prompt for Claude
        analysis_prompt = f"""
Analyze the following product to determine documentation requirements:

Product Name: {product_name}
Product Type: {product_type}
Features:
{chr(10).join(f'- {feature}' for feature in features)}

Technical Details:
{json.dumps(technical_details, indent=2) if technical_details else 'Not provided'}

Please analyze and provide:
1. Key concepts users need to understand
2. Common use cases and workflows
3. Potential pain points or confusion areas
4. Prerequisites or requirements
5. Integration points with other systems
6. Best practices for usage

Focus on what would be most helpful for creating comprehensive documentation.
"""
        
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=analysis_prompt
        )
        
        result = await self.claude_agent.execute(agent_context)
        
        # Parse analysis into structured format
        return {
            "product_name": product_name,
            "product_type": product_type,
            "features": features,
            "analysis": result.content,
            "key_concepts": self._extract_key_concepts(result.content),
            "use_cases": self._extract_use_cases(result.content)
        }
    
    async def _generate_documentation(
        self,
        doc_type: str,
        product_name: str,
        product_analysis: Dict[str, Any],
        audience: str
    ) -> Dict[str, Any]:
        """Generate specific type of documentation."""
        # Map documentation types to templates
        template_map = {
            "user_guide": self._user_guide_template,
            "api_docs": self._api_docs_template,
            "quick_start": self._quick_start_template,
            "troubleshooting": self._troubleshooting_template
        }
        
        template_func = template_map.get(doc_type, self._user_guide_template)
        template = template_func(product_name, product_analysis, audience)
        
        # Generate documentation with Claude
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=template
        )
        
        result = await self.claude_agent.execute(agent_context)
        
        return {
            "type": doc_type,
            "content": result.content,
            "metadata": {
                "product": product_name,
                "audience": audience,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _generate_code_examples(
        self,
        product_name: str,
        features: List[str],
        technical_details: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate code examples using Codex."""
        code_examples = {}
        
        # Generate examples for key features
        for feature in features[:5]:  # Limit to top 5 features
            # Load code generation template
            with open('apps/backend/tasks/prompt_templates/codex/code_generation.md', 'r') as f:
                template = f.read()
            
            agent_context = AgentContext(
                task_id=self.task_id,
                user_input=template.format(
                    task_type="example",
                    target_language=technical_details.get('language', 'python'),
                    integration_points=product_name,
                    platform=technical_details.get('platform', 'generic'),
                    dependencies=json.dumps(technical_details.get('dependencies', [])),
                    performance_requirements="N/A",
                    security_constraints="Standard best practices",
                    language_style_guide="PEP 8" if technical_details.get('language') == 'python' else "Standard",
                    input_specification=f"Demonstrate {feature} functionality",
                    output_specification="Working example code",
                    integration_context=f"Using {product_name} - {feature}",
                    testing_requirements="Include basic error handling",
                    performance_notes="Focus on clarity over optimization",
                    sanitization_requirements="User inputs",
                    auth_method="As appropriate",
                    encryption_needs="None",
                    code_structure_template=f"# Example: {feature}\n# TODO: Implement",
                    additional_notes=f"Create a clear example showing how to use the {feature} feature"
                )
            )
            
            result = await self.codex_agent.execute(agent_context)
            code_examples[feature] = result.content
        
        return code_examples
    
    def _create_documentation_index(self, documentation: Dict[str, Any]) -> Dict[str, Any]:
        """Create table of contents/index for documentation."""
        index = {
            "title": "Documentation Index",
            "sections": []
        }
        
        # Add each documentation type to index
        for doc_type, content in documentation.items():
            if doc_type == 'code_examples':
                section = {
                    "title": "Code Examples",
                    "type": "examples",
                    "items": list(content.keys())
                }
            else:
                section = {
                    "title": self._format_doc_title(doc_type),
                    "type": doc_type,
                    "preview": self._get_preview(content.get('content', ''))
                }
            
            index['sections'].append(section)
        
        return index
    
    async def _format_documentation(
        self,
        documentation: Dict[str, Any],
        output_formats: List[str]
    ) -> Dict[str, Any]:
        """Format documentation for different output formats."""
        formatted = {}
        
        for format_type in output_formats:
            if format_type == "markdown":
                formatted["markdown"] = self._format_as_markdown(documentation)
            elif format_type == "html":
                formatted["html"] = self._format_as_html(documentation)
            elif format_type == "pdf":
                # PDF generation would require additional library
                formatted["pdf_ready"] = self._prepare_for_pdf(documentation)
        
        return formatted
    
    async def _save_documentation(
        self,
        product_name: str,
        documentation: Dict[str, Any]
    ) -> None:
        """Save documentation to memory store."""
        await self.memory_store.save_memory_entry(
            namespace="product_documentation",
            key=f"docs_{product_name}_{datetime.utcnow().timestamp()}",
            content={
                "product_name": product_name,
                "documentation": documentation,
                "created_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "status": "published"
            }
        )
    
    # Template methods
    def _user_guide_template(
        self,
        product_name: str,
        analysis: Dict[str, Any],
        audience: str
    ) -> str:
        """Template for user guide documentation."""
        return f"""
Create a comprehensive user guide for {product_name}.

Target Audience: {audience}

Product Analysis:
{analysis['analysis']}

The user guide should include:
1. Introduction and Overview
2. Getting Started
3. Core Features (detailed walkthrough)
4. Advanced Features
5. Best Practices
6. Common Workflows
7. Tips and Tricks
8. Frequently Asked Questions

Make it friendly, comprehensive, and easy to follow with clear examples.
Include screenshots placeholders where visual aids would be helpful.
"""
    
    def _api_docs_template(
        self,
        product_name: str,
        analysis: Dict[str, Any],
        audience: str
    ) -> str:
        """Template for API documentation."""
        return f"""
Create API documentation for {product_name}.

Target Audience: {audience} (developers)

Features to document:
{chr(10).join(f'- {feature}' for feature in analysis['features'])}

Include:
1. API Overview and Architecture
2. Authentication
3. Endpoints (with request/response examples)
4. Error Handling
5. Rate Limits
6. Code Examples in multiple languages
7. Webhooks (if applicable)
8. Testing

Use standard API documentation format with clear examples.
"""
    
    def _quick_start_template(
        self,
        product_name: str,
        analysis: Dict[str, Any],
        audience: str
    ) -> str:
        """Template for quick start guide."""
        return f"""
Create a quick start guide for {product_name} that gets users up and running in 5 minutes or less.

Target Audience: {audience}

Key Features to Cover:
{chr(10).join(f'- {feature}' for feature in analysis['features'][:3])}

Structure:
1. What is {product_name}?
2. Prerequisites (if any)
3. 5-Minute Setup
4. Your First Task/Project
5. Next Steps
6. Where to Get Help

Make it extremely concise, action-oriented, and achievement-focused.
"""
    
    def _troubleshooting_template(
        self,
        product_name: str,
        analysis: Dict[str, Any],
        audience: str
    ) -> str:
        """Template for troubleshooting documentation."""
        return f"""
Create troubleshooting documentation for {product_name}.

Target Audience: {audience}

Based on the product analysis, identify and document:
1. Common Issues and Solutions
2. Error Messages and Meanings
3. Diagnostic Steps
4. Performance Optimization Tips
5. How to Get Support
6. Known Limitations

Format each issue as:
- Problem Description
- Symptoms
- Cause
- Solution Steps
- Prevention Tips

Make it easy to search and scan for specific issues.
"""
    
    # Helper methods
    def _extract_key_concepts(self, analysis: str) -> List[str]:
        """Extract key concepts from analysis."""
        # Simple extraction - would use NLP in production
        concepts = []
        if "concept" in analysis.lower():
            # Extract lines mentioning concepts
            lines = analysis.split('\n')
            for line in lines:
                if "concept" in line.lower() or "understand" in line.lower():
                    concepts.append(line.strip())
        return concepts[:5]  # Top 5 concepts
    
    def _extract_use_cases(self, analysis: str) -> List[str]:
        """Extract use cases from analysis."""
        use_cases = []
        if "use case" in analysis.lower() or "workflow" in analysis.lower():
            lines = analysis.split('\n')
            for line in lines:
                if any(term in line.lower() for term in ["use case", "workflow", "scenario"]):
                    use_cases.append(line.strip())
        return use_cases[:5]
    
    def _format_doc_title(self, doc_type: str) -> str:
        """Format documentation type as title."""
        return doc_type.replace('_', ' ').title()
    
    def _get_preview(self, content: str, length: int = 150) -> str:
        """Get preview of content."""
        if len(content) > length:
            return content[:length] + "..."
        return content
    
    def _calculate_word_count(self, documentation: Dict[str, Any]) -> int:
        """Calculate total word count across all documentation."""
        total_words = 0
        for doc in documentation.values():
            if isinstance(doc, dict) and 'content' in doc:
                total_words += len(doc['content'].split())
            elif isinstance(doc, str):
                total_words += len(doc.split())
        return total_words
    
    def _format_as_markdown(self, documentation: Dict[str, Any]) -> str:
        """Format all documentation as combined markdown."""
        markdown = f"# {documentation.get('product_name', 'Product')} Documentation\n\n"
        
        for doc_type, content in documentation.items():
            if doc_type == 'code_examples':
                markdown += "## Code Examples\n\n"
                for feature, code in content.items():
                    markdown += f"### {feature}\n\n```\n{code}\n```\n\n"
            elif isinstance(content, dict) and 'content' in content:
                markdown += f"## {self._format_doc_title(doc_type)}\n\n"
                markdown += content['content'] + "\n\n"
        
        return markdown
    
    def _format_as_html(self, documentation: Dict[str, Any]) -> str:
        """Format documentation as HTML."""
        # Simple HTML conversion - would use proper markdown parser in production
        html = "<html><head><title>Documentation</title></head><body>"
        html += "<h1>Product Documentation</h1>"
        
        for doc_type, content in documentation.items():
            if isinstance(content, dict) and 'content' in content:
                html += f"<h2>{self._format_doc_title(doc_type)}</h2>"
                html += f"<div>{content['content'].replace(chr(10), '<br>')}</div>"
        
        html += "</body></html>"
        return html
    
    def _prepare_for_pdf(self, documentation: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare documentation structure for PDF generation."""
        return {
            "title": "Product Documentation",
            "sections": [
                {
                    "title": self._format_doc_title(doc_type),
                    "content": content.get('content', '') if isinstance(content, dict) else str(content)
                }
                for doc_type, content in documentation.items()
            ],
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "format": "pdf_ready"
            }
        }