"""
Autopublish content task implementation.
Generates, optimizes, and publishes content automatically using AI agents.
"""

import logging
from typing import Dict, Any, AsyncIterator, List
from datetime import datetime
import json

from ..agents.claude_agent import ClaudeAgent
from ..agents.gemini_agent import GeminiAgent
from ..agents.base import AgentContext
from ..memory.memory_store import MemoryStore
from .base_task import BaseTask, TaskResult

logger = logging.getLogger(__name__)

# Task identifier for registration
TASK_ID = "autopublish_content"


class AutopublishContentTask(BaseTask):
    """
    Automatically generates and publishes content based on topic and audience.
    
    This task orchestrates:
    1. Content generation using Claude
    2. SEO optimization using Gemini
    3. Publishing to specified platforms
    4. Performance tracking setup
    """
    
    # Task metadata
    METADATA = {
        "category": "content",
        "requires_approval": False,
        "estimated_duration_seconds": 120,
        "supported_platforms": ["blog", "social", "email"]
    }
    
    def __init__(self):
        super().__init__(task_id=TASK_ID)
        self.claude_agent = ClaudeAgent()
        self.gemini_agent = GeminiAgent()
        self.memory_store = MemoryStore()
        
    async def run(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute content generation and publishing workflow.
        
        Args:
            context: Must include:
                - topic: Content topic
                - audience: Target audience description
                - seo_keywords: List of target keywords
                - publish_to: List of platforms to publish to
                - content_type: Type of content (article, social, email)
                - tone: Optional tone/voice specification
                
        Returns:
            TaskResult with generated and published content
        """
        try:
            # Validate required context
            self._validate_context(context)
            
            # Extract parameters
            topic = context['topic']
            audience = context['audience']
            seo_keywords = context.get('seo_keywords', [])
            publish_platforms = context.get('publish_to', ['blog'])
            content_type = context.get('content_type', 'article')
            
            # Step 1: Generate content with Claude
            content_result = await self._generate_content(
                topic, audience, content_type, context.get('tone')
            )
            
            # Step 2: Optimize for SEO with Gemini
            if seo_keywords and 'blog' in publish_platforms:
                optimized_content = await self._optimize_for_seo(
                    content_result['content'],
                    seo_keywords,
                    topic
                )
            else:
                optimized_content = content_result
            
            # Step 3: Format for each platform
            formatted_content = await self._format_for_platforms(
                optimized_content,
                publish_platforms
            )
            
            # Step 4: Publish to platforms
            publish_results = await self._publish_content(
                formatted_content,
                publish_platforms,
                context
            )
            
            # Step 5: Store in memory for tracking
            await self._save_published_content(
                topic,
                formatted_content,
                publish_results
            )
            
            return TaskResult(
                success=True,
                data={
                    "topic": topic,
                    "content": optimized_content,
                    "formatted_versions": formatted_content,
                    "publish_results": publish_results,
                    "seo_metadata": optimized_content.get('seo_metadata', {})
                },
                message=f"Successfully generated and published content for: {topic}"
            )
            
        except Exception as e:
            logger.error(f"Autopublish failed for topic '{context.get('topic')}': {e}")
            return TaskResult(
                success=False,
                error=str(e),
                message=f"Content generation failed: {str(e)}"
            )
    
    async def stream(self, context: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream content generation progress updates.
        """
        try:
            # Validate context
            yield {"stage": "validating", "message": "Validating input parameters"}
            self._validate_context(context)
            
            # Generate content
            yield {"stage": "generating_content", "message": "Generating content with AI"}
            content_result = await self._generate_content(
                context['topic'],
                context['audience'],
                context.get('content_type', 'article'),
                context.get('tone')
            )
            yield {
                "stage": "content_generated",
                "message": "Content generation complete",
                "preview": content_result['content'][:200] + "..."
            }
            
            # SEO optimization
            if context.get('seo_keywords') and 'blog' in context.get('publish_to', []):
                yield {"stage": "optimizing_seo", "message": "Optimizing content for SEO"}
                optimized = await self._optimize_for_seo(
                    content_result['content'],
                    context['seo_keywords'],
                    context['topic']
                )
                yield {
                    "stage": "seo_complete",
                    "message": "SEO optimization complete",
                    "keywords_integrated": len(context['seo_keywords'])
                }
            else:
                optimized = content_result
                
            # Format for platforms
            yield {"stage": "formatting", "message": "Formatting for target platforms"}
            formatted = await self._format_for_platforms(
                optimized,
                context.get('publish_to', ['blog'])
            )
            
            # Publish
            yield {"stage": "publishing", "message": "Publishing to platforms"}
            publish_results = await self._publish_content(
                formatted,
                context.get('publish_to', ['blog']),
                context
            )
            
            # Complete
            yield {
                "stage": "completed",
                "message": "Content published successfully",
                "summary": {
                    "platforms": list(publish_results.keys()),
                    "word_count": len(optimized['content'].split())
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
        required_fields = ['topic', 'audience']
        missing = [field for field in required_fields if field not in context]
        
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
            
        # Validate publish_to platforms
        if 'publish_to' in context:
            invalid_platforms = [
                p for p in context['publish_to'] 
                if p not in self.METADATA['supported_platforms']
            ]
            if invalid_platforms:
                raise ValueError(
                    f"Unsupported platforms: {', '.join(invalid_platforms)}"
                )
    
    async def _generate_content(
        self,
        topic: str,
        audience: str,
        content_type: str,
        tone: str = None
    ) -> Dict[str, Any]:
        """Generate content using Claude."""
        # Load appropriate template
        template_path = f"apps/backend/tasks/prompt_templates/claude/{content_type}_template.md"
        try:
            with open(template_path, 'r') as f:
                template = f.read()
        except FileNotFoundError:
            # Use default template if specific one doesn't exist
            with open('apps/backend/tasks/prompt_templates/claude/sop_template.md', 'r') as f:
                template = f.read()
        
        # Prepare context for Claude
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=template.format(
                task_objective=f"Create {content_type} content about {topic}",
                audience_profile=audience,
                output_format=content_type,
                content_length=self._get_content_length(content_type),
                deliverables=f"Complete {content_type} ready for publication",
                input_data=f"Topic: {topic}\nTone: {tone or 'Professional, informative'}",
                integration_points="SEO optimization, platform formatting",
                additional_context=f"Content type: {content_type}"
            )
        )
        
        # Generate content
        result = await self.claude_agent.execute(agent_context)
        
        return {
            "content": result.content,
            "metadata": result.metadata,
            "content_type": content_type
        }
    
    async def _optimize_for_seo(
        self,
        content: str,
        keywords: List[str],
        topic: str
    ) -> Dict[str, Any]:
        """Optimize content for SEO using Gemini."""
        # Load SEO optimization template
        with open('apps/backend/tasks/prompt_templates/gemini/seo_optimization.md', 'r') as f:
            template = f.read()
        
        # Prepare context for Gemini
        agent_context = AgentContext(
            task_id=self.task_id,
            user_input=template.format(
                optimization_goal="Improve search visibility and ranking",
                content_type="article",
                target_keywords=", ".join(keywords),
                search_intent="informational",
                primary_keyword=keywords[0] if keywords else topic,
                lsi_keywords=", ".join(keywords[1:]) if len(keywords) > 1 else "",
                target_word_count="1500-2000",
                competitor_data="[Analysis pending]",
                user_pain_point=f"Understanding {topic}",
                related_resources=f"Other {topic} articles",
                additional_schema_properties='{"author": "BrainOps"}',
                schema_type="Article",
                target_locations="United States",
                local_keywords="",
                image_keywords=keywords[0] if keywords else topic,
                primary_cta="Learn more about our solutions",
                secondary_cta="Schedule a consultation",
                trust_elements="Industry expertise, proven results",
                additional_seo_context=f"Original content:\n\n{content}"
            )
        )
        
        # Optimize content
        result = await self.gemini_agent.execute(agent_context)
        
        # Parse SEO metadata from result
        seo_metadata = self._extract_seo_metadata(result.content)
        
        return {
            "content": result.content,
            "seo_metadata": seo_metadata,
            "keywords_integrated": keywords
        }
    
    async def _format_for_platforms(
        self,
        content: Dict[str, Any],
        platforms: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Format content for different publishing platforms."""
        formatted = {}
        
        for platform in platforms:
            if platform == "blog":
                formatted["blog"] = {
                    "title": self._extract_title(content['content']),
                    "body": content['content'],
                    "excerpt": self._create_excerpt(content['content']),
                    "meta_description": content.get('seo_metadata', {}).get('description', ''),
                    "tags": content.get('keywords_integrated', [])
                }
            elif platform == "social":
                formatted["social"] = {
                    "post": self._create_social_post(content['content']),
                    "hashtags": self._generate_hashtags(content.get('keywords_integrated', [])),
                    "platform_variants": {
                        "twitter": self._truncate_for_twitter(content['content']),
                        "linkedin": self._format_for_linkedin(content['content']),
                        "facebook": self._format_for_facebook(content['content'])
                    }
                }
            elif platform == "email":
                formatted["email"] = {
                    "subject": self._extract_title(content['content']),
                    "preview_text": self._create_excerpt(content['content'], 100),
                    "body_html": self._convert_to_email_html(content['content']),
                    "body_text": self._convert_to_plain_text(content['content'])
                }
        
        return formatted
    
    async def _publish_content(
        self,
        formatted_content: Dict[str, Dict[str, Any]],
        platforms: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish content to specified platforms.
        For now, this simulates publishing - integrate with actual platforms later.
        """
        publish_results = {}
        
        for platform in platforms:
            if platform not in formatted_content:
                continue
                
            # Simulate publishing (replace with actual API calls)
            publish_results[platform] = {
                "status": "published",
                "url": f"https://example.com/{platform}/{context['topic'].lower().replace(' ', '-')}",
                "published_at": datetime.utcnow().isoformat(),
                "platform_id": f"{platform}_{datetime.utcnow().timestamp()}"
            }
            
            logger.info(f"Published content to {platform}")
        
        return publish_results
    
    async def _save_published_content(
        self,
        topic: str,
        content: Dict[str, Any],
        publish_results: Dict[str, Any]
    ) -> None:
        """Save published content to memory for tracking and analytics."""
        await self.memory_store.save_memory_entry(
            namespace="published_content",
            key=f"content_{topic}_{datetime.utcnow().timestamp()}",
            content={
                "topic": topic,
                "content": content,
                "publish_results": publish_results,
                "published_at": datetime.utcnow().isoformat(),
                "performance_metrics": {
                    "views": 0,
                    "engagement": 0,
                    "conversions": 0
                }
            }
        )
    
    # Helper methods for content processing
    def _get_content_length(self, content_type: str) -> str:
        """Get recommended content length for type."""
        lengths = {
            "article": "1500-2000 words",
            "social": "100-280 characters",
            "email": "150-300 words"
        }
        return lengths.get(content_type, "appropriate length")
    
    def _extract_title(self, content: str) -> str:
        """Extract title from content."""
        lines = content.strip().split('\n')
        for line in lines:
            if line.strip():
                return line.strip('#').strip()
        return "Untitled"
    
    def _create_excerpt(self, content: str, length: int = 160) -> str:
        """Create excerpt from content."""
        # Remove markdown formatting
        clean_content = content.replace('#', '').replace('*', '').replace('-', '')
        words = clean_content.split()[:30]
        excerpt = ' '.join(words)
        
        if len(excerpt) > length:
            excerpt = excerpt[:length-3] + "..."
        
        return excerpt
    
    def _extract_seo_metadata(self, optimized_content: str) -> Dict[str, Any]:
        """Extract SEO metadata from optimized content."""
        # Simple extraction - enhance based on Gemini output format
        return {
            "title": self._extract_title(optimized_content),
            "description": self._create_excerpt(optimized_content),
            "keywords": [],  # Would be extracted from Gemini response
            "schema_type": "Article"
        }
    
    def _create_social_post(self, content: str) -> str:
        """Create social media post from content."""
        excerpt = self._create_excerpt(content, 200)
        return f"{excerpt}\n\nRead more: [link]"
    
    def _generate_hashtags(self, keywords: List[str]) -> List[str]:
        """Generate hashtags from keywords."""
        return [f"#{kw.replace(' ', '')}" for kw in keywords[:5]]
    
    def _truncate_for_twitter(self, content: str) -> str:
        """Format content for Twitter/X."""
        excerpt = self._create_excerpt(content, 250)
        return f"{excerpt}... [thread]"
    
    def _format_for_linkedin(self, content: str) -> str:
        """Format content for LinkedIn."""
        return self._create_excerpt(content, 300)
    
    def _format_for_facebook(self, content: str) -> str:
        """Format content for Facebook."""
        return self._create_excerpt(content, 400)
    
    def _convert_to_email_html(self, content: str) -> str:
        """Convert markdown content to email HTML."""
        # Simple conversion - would use markdown library in production
        html = content.replace('\n\n', '</p><p>')
        html = f"<p>{html}</p>"
        html = html.replace('# ', '<h1>').replace('\n', '</h1>\n')
        return html
    
    def _convert_to_plain_text(self, content: str) -> str:
        """Convert content to plain text."""
        return content.replace('#', '').replace('*', '').replace('_', '')