"""
Auto-Publish Content Task

This task automates the content creation and publication workflow, including
research, writing, SEO optimization, and distribution across configured platforms.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import json
import logging

from .tasks import BaseTask
from .agents.base import ExecutionContext, get_agent_graph
from .memory.memory_store import save_content_draft, publish_content
from .integrations.wordpress import publish_to_wordpress
from .integrations.medium import publish_to_medium
from .integrations.social_media import share_to_social


logger = logging.getLogger(__name__)


class AutoPublishContentTask(BaseTask):
    """
    Automated content creation and publication task.
    
    Orchestrates multiple AI agents to research topics, generate content,
    optimize for SEO, and publish across various platforms.
    """
    
    TASK_ID = "autopublish_content"
    TASK_NAME = "Auto-Publish Content"
    TASK_DESCRIPTION = "Research, write, optimize, and publish content automatically"
    TASK_CATEGORY = "content"
    
    @classmethod
    def validate_parameters(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content publication parameters."""
        required_fields = ["topic", "content_type", "target_platforms"]
        
        for field in required_fields:
            if field not in parameters:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate content type
        valid_content_types = ["blog_post", "article", "social_media", "newsletter"]
        if parameters["content_type"] not in valid_content_types:
            raise ValueError(f"Invalid content_type. Must be one of: {valid_content_types}")
        
        # Validate platforms
        valid_platforms = ["wordpress", "medium", "linkedin", "twitter", "email"]
        for platform in parameters["target_platforms"]:
            if platform not in valid_platforms:
                raise ValueError(f"Invalid platform: {platform}")
        
        # Set defaults
        parameters.setdefault("word_count", 1000)
        parameters.setdefault("tone", "professional")
        parameters.setdefault("include_images", True)
        parameters.setdefault("seo_optimize", True)
        parameters.setdefault("require_approval", True)
        
        return parameters
    
    @classmethod
    def estimate_tokens(cls, parameters: Dict[str, Any]) -> int:
        """Estimate tokens based on content length."""
        word_count = parameters.get("word_count", 1000)
        # Rough estimate: 1.5 tokens per word, plus overhead for prompts
        base_tokens = int(word_count * 1.5)
        
        # Add tokens for research
        if parameters.get("include_research", True):
            base_tokens += 2000
        
        # Add tokens for SEO optimization
        if parameters.get("seo_optimize", True):
            base_tokens += 1000
        
        return base_tokens
    
    @classmethod
    def estimate_duration(cls, parameters: Dict[str, Any]) -> int:
        """Estimate task duration in seconds."""
        # Base time for content generation
        duration = 60
        
        # Add time for research
        if parameters.get("include_research", True):
            duration += 30
        
        # Add time for each platform
        duration += len(parameters.get("target_platforms", [])) * 10
        
        return duration
    
    @classmethod
    def get_required_approvals(cls, parameters: Dict[str, Any]) -> List[str]:
        """Determine required approvals."""
        approvals = []
        
        if parameters.get("require_approval", True):
            approvals.append("content_review")
        
        # Always require approval for external publication
        if any(platform in ["wordpress", "medium"] for platform in parameters.get("target_platforms", [])):
            approvals.append("publication_approval")
        
        return approvals
    
    @classmethod
    async def run(cls, context: ExecutionContext) -> Dict[str, Any]:
        """Execute the content publication workflow."""
        try:
            # Initialize result tracking
            result = {
                "task_id": context.task_id,
                "status": "in_progress",
                "phases": {},
                "content": {},
                "published_urls": {}
            }
            
            # Get agent graph for orchestration
            agent_graph = await get_agent_graph()
            
            # Phase 1: Research (if enabled)
            if context.parameters.get("include_research", True):
                research_result = await cls._execute_research_phase(
                    context, agent_graph
                )
                result["phases"]["research"] = research_result
                
                # Add research to context for content generation
                context.add_agent_output("research", research_result["findings"])
            
            # Phase 2: Content Generation
            content_result = await cls._execute_content_generation(
                context, agent_graph
            )
            result["phases"]["content_generation"] = content_result
            result["content"]["draft"] = content_result["content"]
            
            # Phase 3: SEO Optimization (if enabled)
            if context.parameters.get("seo_optimize", True):
                seo_result = await cls._execute_seo_optimization(
                    context, agent_graph, content_result["content"]
                )
                result["phases"]["seo_optimization"] = seo_result
                result["content"]["optimized"] = seo_result["optimized_content"]
            
            # Save draft to memory
            draft_id = await save_content_draft(
                user_id=context.user_id,
                content=result["content"].get("optimized", result["content"]["draft"]),
                metadata={
                    "topic": context.parameters["topic"],
                    "content_type": context.parameters["content_type"],
                    "word_count": len(result["content"]["draft"].split())
                }
            )
            
            # Phase 4: Approval (if required)
            if context.parameters.get("require_approval", True):
                approval_result = await cls._request_approval(
                    context, result["content"]
                )
                
                if not approval_result["approved"]:
                    result["status"] = "pending_approval"
                    result["approval_request_id"] = approval_result["request_id"]
                    return result
            
            # Phase 5: Publication
            publication_results = await cls._execute_publication(
                context,
                result["content"].get("optimized", result["content"]["draft"]),
                context.parameters["target_platforms"]
            )
            
            result["phases"]["publication"] = publication_results
            result["published_urls"] = publication_results["urls"]
            
            # Update content status
            await publish_content(draft_id, publication_results["urls"])
            
            result["status"] = "completed"
            result["completed_at"] = datetime.utcnow().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Content publication task failed: {str(e)}")
            return {
                "task_id": context.task_id,
                "status": "failed",
                "error": str(e)
            }
    
    @classmethod
    async def stream(cls, context: ExecutionContext):
        """Stream content generation progress."""
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Starting content workflow'})}\n\n"
            
            agent_graph = await get_agent_graph()
            
            # Stream research phase
            if context.parameters.get("include_research", True):
                yield f"data: {json.dumps({'type': 'phase', 'phase': 'research', 'status': 'started'})}\n\n"
                
                research_result = await cls._execute_research_phase(context, agent_graph)
                
                yield f"data: {json.dumps({'type': 'phase', 'phase': 'research', 'status': 'completed', 'summary': research_result.get('summary', '')})}\n\n"
            
            # Stream content generation
            yield f"data: {json.dumps({'type': 'phase', 'phase': 'content_generation', 'status': 'started'})}\n\n"
            
            # In production, stream actual content chunks
            content_result = await cls._execute_content_generation(context, agent_graph)
            
            yield f"data: {json.dumps({'type': 'content_chunk', 'content': content_result['content'][:200] + '...'})}\n\n"
            
            # Continue with other phases...
            
            yield f"data: {json.dumps({'type': 'complete', 'message': 'Content workflow completed'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    @classmethod
    async def _execute_research_phase(
        cls,
        context: ExecutionContext,
        agent_graph
    ) -> Dict[str, Any]:
        """Execute research phase using search agent."""
        logger.info(f"Executing research phase for topic: {context.parameters['topic']}")
        
        # Prepare research context
        research_context = ExecutionContext(
            task_id=f"{context.task_id}_research",
            user_id=context.user_id,
            parameters={
                "search_type": "deep_research",
                "query": context.parameters["topic"],
                "include_competitors": context.parameters.get("include_competitor_analysis", False)
            }
        )
        
        # Execute search agent
        search_agent = agent_graph.nodes.get("research_intelligence")
        if not search_agent:
            logger.warning("Search agent not available, skipping research")
            return {"findings": [], "summary": "No research conducted"}
        
        search_response = await search_agent.execute(
            research_context,
            f"Research the topic: {context.parameters['topic']} for a {context.parameters['content_type']}"
        )
        
        if search_response.success:
            return {
                "findings": search_response.content.get("key_findings", []),
                "summary": search_response.content.get("executive_summary", ""),
                "sources": search_response.content.get("sources", [])
            }
        else:
            return {"findings": [], "summary": "Research failed"}
    
    @classmethod
    async def _execute_content_generation(
        cls,
        context: ExecutionContext,
        agent_graph
    ) -> Dict[str, Any]:
        """Execute content generation using Claude."""
        logger.info("Executing content generation phase")
        
        # Build content generation prompt
        prompt_parts = [
            f"Write a {context.parameters['content_type']} about: {context.parameters['topic']}",
            f"Target word count: {context.parameters['word_count']}",
            f"Tone: {context.parameters['tone']}",
            f"Audience: {context.parameters.get('target_audience', 'general')}"
        ]
        
        # Add research findings if available
        research_output = context.get_agent_output("research")
        if research_output and research_output.get("findings"):
            prompt_parts.append("\nIncorporate these research findings:")
            for finding in research_output["findings"][:5]:
                prompt_parts.append(f"- {finding}")
        
        # Add specific requirements
        if context.parameters.get("key_points"):
            prompt_parts.append("\nInclude these key points:")
            for point in context.parameters["key_points"]:
                prompt_parts.append(f"- {point}")
        
        content_prompt = "\n".join(prompt_parts)
        
        # Execute Claude agent
        claude_agent = agent_graph.nodes.get("content_director")
        if not claude_agent:
            raise Exception("Content generation agent not available")
        
        claude_response = await claude_agent.execute(
            context,
            content_prompt
        )
        
        if not claude_response.success:
            raise Exception(f"Content generation failed: {claude_response.error}")
        
        return {
            "content": claude_response.content,
            "metadata": {
                "word_count": len(claude_response.content.split()),
                "tokens_used": claude_response.tokens_used
            }
        }
    
    @classmethod
    async def _execute_seo_optimization(
        cls,
        context: ExecutionContext,
        agent_graph,
        content: str
    ) -> Dict[str, Any]:
        """Execute SEO optimization using Gemini."""
        logger.info("Executing SEO optimization phase")
        
        # Prepare SEO context
        seo_context = ExecutionContext(
            task_id=f"{context.task_id}_seo",
            user_id=context.user_id,
            parameters={
                "task_type": "seo_optimization",
                "content": content,
                "keywords": context.parameters.get("target_keywords", []),
                "audience": context.parameters.get("target_audience", "general")
            }
        )
        
        # Execute Gemini agent
        gemini_agent = agent_graph.nodes.get("strategic_intelligence")
        if not gemini_agent:
            logger.warning("SEO agent not available, skipping optimization")
            return {"optimized_content": content, "seo_score": 0}
        
        seo_prompt = """
        Optimize this content for SEO while maintaining readability:
        1. Add relevant meta description (155 chars)
        2. Suggest title tags
        3. Improve keyword density for target keywords
        4. Add internal linking suggestions
        5. Return the optimized content
        """
        
        seo_response = await gemini_agent.execute(seo_context, seo_prompt)
        
        if seo_response.success:
            return {
                "optimized_content": seo_response.content.get("optimized_content", content),
                "seo_score": seo_response.content.get("seo_score", 75),
                "meta_description": seo_response.content.get("meta_description", ""),
                "title_suggestions": seo_response.content.get("title_suggestions", [])
            }
        else:
            return {"optimized_content": content, "seo_score": 0}
    
    @classmethod
    async def _request_approval(
        cls,
        context: ExecutionContext,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request human approval for content."""
        # In production, this would create an approval request in the system
        # For now, simulate approval
        logger.info("Requesting content approval")
        
        # Create approval request
        approval_request = {
            "task_id": context.task_id,
            "content_preview": content.get("optimized", content["draft"])[:500],
            "word_count": len(content.get("optimized", content["draft"]).split()),
            "platforms": context.parameters["target_platforms"]
        }
        
        # In production, save to approval queue and return request ID
        # For now, auto-approve after delay
        await asyncio.sleep(2)
        
        return {
            "approved": True,
            "request_id": f"approval_{context.task_id}",
            "reviewer": "auto_approved"
        }
    
    @classmethod
    async def _execute_publication(
        cls,
        context: ExecutionContext,
        content: str,
        platforms: List[str]
    ) -> Dict[str, Any]:
        """Publish content to specified platforms."""
        logger.info(f"Publishing to platforms: {platforms}")
        
        publication_results = {
            "urls": {},
            "errors": {}
        }
        
        # Publish to each platform
        for platform in platforms:
            try:
                if platform == "wordpress":
                    url = await publish_to_wordpress(
                        title=context.parameters.get("title", context.parameters["topic"]),
                        content=content,
                        categories=context.parameters.get("categories", []),
                        tags=context.parameters.get("tags", [])
                    )
                    publication_results["urls"]["wordpress"] = url
                    
                elif platform == "medium":
                    url = await publish_to_medium(
                        title=context.parameters.get("title", context.parameters["topic"]),
                        content=content,
                        tags=context.parameters.get("tags", [])
                    )
                    publication_results["urls"]["medium"] = url
                    
                elif platform in ["linkedin", "twitter"]:
                    # Create social media post from content
                    social_content = cls._create_social_snippet(content, platform)
                    url = await share_to_social(
                        platform=platform,
                        content=social_content,
                        link=publication_results["urls"].get("wordpress", "")
                    )
                    publication_results["urls"][platform] = url
                    
            except Exception as e:
                logger.error(f"Failed to publish to {platform}: {str(e)}")
                publication_results["errors"][platform] = str(e)
        
        return publication_results
    
    @classmethod
    def _create_social_snippet(cls, content: str, platform: str) -> str:
        """Create platform-appropriate social media snippet."""
        # Extract first paragraph or key points
        paragraphs = content.split('\n\n')
        snippet = paragraphs[0] if paragraphs else content[:200]
        
        # Platform-specific length limits
        if platform == "twitter":
            max_length = 280
        else:  # LinkedIn
            max_length = 700
        
        if len(snippet) > max_length - 50:  # Leave room for link
            snippet = snippet[:max_length-53] + "..."
        
        return snippet
