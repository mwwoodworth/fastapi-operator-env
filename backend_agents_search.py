"""
Search Agent Wrapper

This module provides the search agent implementation for web research,
fact verification, and real-time data retrieval. Integrates with Perplexity
or other search providers to gather current information.
"""

from typing import Dict, Any, List, Optional, Tuple
import asyncio
from datetime import datetime
import aiohttp
import json
import logging
from urllib.parse import quote_plus

from apps.backend.agents.base import AgentNode, AgentResponse, ExecutionContext, AgentType
from apps.backend.core.settings import settings
from apps.backend.memory.memory_store import get_prompt_template, save_search_results


logger = logging.getLogger(__name__)


class SearchAgent(AgentNode):
    """
    Search agent for real-time information retrieval and fact verification.
    
    Provides web search capabilities, fact checking, competitive research,
    and access to current data that may not be in the LLMs' training data.
    """
    
    def __init__(self, node_id: str, name: str, config: Dict[str, Any]):
        super().__init__(
            node_id=node_id,
            name=name,
            agent_type=AgentType.SEARCH,
            capabilities=config.get("capabilities", []),
            config=config
        )
        
        # Search provider configuration
        self.provider = config.get("provider", "perplexity")
        self.search_depth = config.get("search_depth", "comprehensive")
        self.max_results = config.get("max_results", 10)
        
        # API configuration based on provider
        if self.provider == "perplexity":
            self.api_key = settings.PERPLEXITY_API_KEY
            self.api_url = "https://api.perplexity.ai/search"
        elif self.provider == "serper":
            self.api_key = settings.SERPER_API_KEY
            self.api_url = "https://google.serper.dev/search"
        else:
            # Default to web scraping if no API provider
            self.api_key = None
            self.api_url = None
            
        # Search-specific settings
        self.verify_sources = config.get("verify_sources", True)
        self.include_citations = config.get("include_citations", True)
        
    async def execute(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """
        Execute search operations for information retrieval.
        
        Handles web searches, fact verification, competitive research,
        and real-time data gathering based on the query.
        """
        try:
            # Determine search intent from context
            search_type = context.parameters.get("search_type", "general")
            
            if search_type == "fact_check":
                response = await self._execute_fact_check(context, prompt, **kwargs)
            elif search_type == "competitive_research":
                response = await self._execute_competitive_research(context, prompt, **kwargs)
            elif search_type == "real_time_data":
                response = await self._execute_realtime_search(context, prompt, **kwargs)
            elif search_type == "deep_research":
                response = await self._execute_deep_research(context, prompt, **kwargs)
            else:
                response = await self._execute_general_search(context, prompt, **kwargs)
                
            return response
            
        except Exception as e:
            logger.error(f"Search agent error: {str(e)}")
            return AgentResponse(
                content=None,
                success=False,
                agent_id=self.node_id,
                error=f"Search error: {str(e)}"
            )
    
    async def _execute_fact_check(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute fact-checking search with source verification."""
        # Extract claim to verify
        claim = context.parameters.get("claim", prompt)
        
        # Build fact-checking query
        search_queries = self._generate_fact_check_queries(claim)
        
        # Execute multiple searches for comprehensive verification
        all_results = []
        for query in search_queries:
            results = await self._perform_search(query)
            all_results.extend(results)
        
        # Analyze results for fact verification
        verification_result = self._analyze_fact_check_results(claim, all_results)
        
        # Save search results for reference
        await save_search_results(
            user_id=context.user_id,
            query=claim,
            results=all_results,
            search_type="fact_check"
        )
        
        return AgentResponse(
            content=verification_result,
            success=True,
            agent_id=self.node_id,
            metadata={
                "search_type": "fact_check",
                "sources_checked": len(all_results),
                "verification_confidence": verification_result["confidence"]
            },
            confidence=verification_result["confidence"]
        )
    
    async def _execute_competitive_research(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute competitive research with structured analysis."""
        # Extract competitor information
        competitors = context.parameters.get("competitors", [])
        research_areas = context.parameters.get("research_areas", [
            "products", "pricing", "features", "market_position"
        ])
        
        # Build competitive research queries
        competitive_data = {}
        
        for competitor in competitors:
            competitive_data[competitor] = {}
            
            for area in research_areas:
                query = f"{competitor} {area} {datetime.now().year}"
                results = await self._perform_search(query)
                
                # Extract relevant information
                area_insights = self._extract_competitive_insights(
                    results, competitor, area
                )
                competitive_data[competitor][area] = area_insights
        
        # Generate competitive analysis report
        analysis = self._generate_competitive_analysis(competitive_data)
        
        return AgentResponse(
            content=analysis,
            success=True,
            agent_id=self.node_id,
            metadata={
                "search_type": "competitive_research",
                "competitors_analyzed": len(competitors),
                "research_areas": research_areas
            },
            confidence=0.85
        )
    
    async def _execute_realtime_search(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute real-time data search for current information."""
        # Add temporal markers to query
        time_sensitive_query = f"{prompt} {datetime.now().strftime('%B %Y')} latest current"
        
        # Perform search with recency bias
        results = await self._perform_search(
            time_sensitive_query,
            sort_by="date",
            time_range="month"
        )
        
        # Filter and rank by recency
        recent_results = self._filter_recent_results(results)
        
        # Structure real-time information
        realtime_data = {
            "query": prompt,
            "timestamp": datetime.utcnow().isoformat(),
            "data": self._structure_realtime_data(recent_results),
            "sources": self._format_citations(recent_results) if self.include_citations else []
        }
        
        return AgentResponse(
            content=realtime_data,
            success=True,
            agent_id=self.node_id,
            metadata={
                "search_type": "real_time_data",
                "results_count": len(recent_results),
                "time_range": "last_30_days"
            },
            confidence=0.9
        )
    
    async def _execute_deep_research(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute comprehensive deep research with multiple queries."""
        # Generate multiple research angles
        research_queries = self._generate_deep_research_queries(prompt, context)
        
        # Execute parallel searches for efficiency
        search_tasks = [
            self._perform_search(query, max_results=5)
            for query in research_queries
        ]
        
        all_results = await asyncio.gather(*search_tasks)
        
        # Flatten and deduplicate results
        combined_results = []
        seen_urls = set()
        
        for results in all_results:
            for result in results:
                if result["url"] not in seen_urls:
                    seen_urls.add(result["url"])
                    combined_results.append(result)
        
        # Synthesize comprehensive research report
        research_synthesis = self._synthesize_research(
            prompt, combined_results, context
        )
        
        # Save comprehensive research results
        await save_search_results(
            user_id=context.user_id,
            query=prompt,
            results=combined_results,
            search_type="deep_research"
        )
        
        return AgentResponse(
            content=research_synthesis,
            success=True,
            agent_id=self.node_id,
            metadata={
                "search_type": "deep_research",
                "queries_executed": len(research_queries),
                "unique_sources": len(combined_results),
                "synthesis_sections": len(research_synthesis.get("sections", []))
            },
            confidence=0.85
        )
    
    async def _execute_general_search(
        self,
        context: ExecutionContext,
        prompt: str,
        **kwargs
    ) -> AgentResponse:
        """Execute general web search."""
        # Perform standard search
        results = await self._perform_search(prompt)
        
        # Format results with snippets and metadata
        formatted_results = {
            "query": prompt,
            "results": [
                {
                    "title": r["title"],
                    "snippet": r["snippet"],
                    "url": r["url"],
                    "relevance_score": r.get("score", 0.5)
                }
                for r in results
            ],
            "total_results": len(results)
        }
        
        return AgentResponse(
            content=formatted_results,
            success=True,
            agent_id=self.node_id,
            metadata={
                "search_type": "general",
                "results_count": len(results)
            },
            confidence=0.9
        )
    
    async def _perform_search(
        self,
        query: str,
        max_results: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Execute search query using configured provider."""
        max_results = max_results or self.max_results
        
        if self.provider == "perplexity":
            return await self._search_perplexity(query, max_results, **kwargs)
        elif self.provider == "serper":
            return await self._search_serper(query, max_results, **kwargs)
        else:
            # Fallback to web scraping
            return await self._search_web_scrape(query, max_results, **kwargs)
    
    async def _search_perplexity(
        self,
        query: str,
        max_results: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search using Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": self.search_depth,
            "include_domains": kwargs.get("include_domains", []),
            "exclude_domains": kwargs.get("exclude_domains", [])
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_perplexity_results(data)
                else:
                    logger.error(f"Perplexity API error: {response.status}")
                    return []
    
    async def _search_serper(
        self,
        query: str,
        max_results: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search using Serper (Google) API."""
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": max_results,
            "gl": kwargs.get("country", "us"),
            "hl": kwargs.get("language", "en")
        }
        
        # Add time range if specified
        if "time_range" in kwargs:
            payload["tbs"] = self._get_time_range_param(kwargs["time_range"])
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_serper_results(data)
                else:
                    logger.error(f"Serper API error: {response.status}")
                    return []
    
    async def _search_web_scrape(
        self,
        query: str,
        max_results: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Fallback web scraping search (simplified)."""
        # In production, implement proper web scraping with BeautifulSoup/Scrapy
        logger.warning("Using fallback web scraping - results may be limited")
        
        # Placeholder implementation
        return [
            {
                "title": f"Result for: {query}",
                "snippet": "Web scraping fallback - implement proper scraping",
                "url": f"https://example.com/search?q={quote_plus(query)}",
                "score": 0.5
            }
        ]
    
    def _generate_fact_check_queries(self, claim: str) -> List[str]:
        """Generate multiple queries for fact checking."""
        queries = [
            claim,  # Original claim
            f"{claim} fact check",
            f"{claim} true or false",
            f"{claim} debunked",
            f"{claim} verification"
        ]
        
        # Add opposite queries to find contradicting information
        if "is" in claim:
            opposite_claim = claim.replace("is", "is not", 1)
            queries.append(opposite_claim)
        
        return queries[:5]  # Limit to 5 queries
    
    def _generate_deep_research_queries(
        self,
        base_query: str,
        context: ExecutionContext
    ) -> List[str]:
        """Generate comprehensive research queries."""
        queries = [base_query]
        
        # Add contextual variations
        aspects = [
            "overview", "benefits", "challenges", "best practices",
            "case studies", "trends", "statistics", "comparison"
        ]
        
        for aspect in aspects[:4]:  # Limit number of queries
            queries.append(f"{base_query} {aspect}")
        
        # Add industry-specific query if applicable
        industry = context.parameters.get("industry")
        if industry:
            queries.append(f"{base_query} {industry} industry")
        
        return queries
    
    def _parse_perplexity_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Perplexity API response."""
        results = []
        
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("url", ""),
                "score": item.get("relevance_score", 0.5),
                "date": item.get("published_date")
            })
        
        return results
    
    def _parse_serper_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Serper (Google) API response."""
        results = []
        
        # Parse organic results
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "score": item.get("position", 10) / 10,  # Convert position to score
                "date": item.get("date")
            })
        
        # Include knowledge graph if available
        if "knowledgeGraph" in data:
            kg = data["knowledgeGraph"]
            results.insert(0, {
                "title": kg.get("title", ""),
                "snippet": kg.get("description", ""),
                "url": kg.get("descriptionLink", ""),
                "score": 1.0,  # Knowledge graph is highly relevant
                "type": "knowledge_graph"
            })
        
        return results
    
    def _analyze_fact_check_results(
        self,
        claim: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze search results for fact verification."""
        supporting = 0
        contradicting = 0
        uncertain = 0
        
        fact_check_sources = []
        
        for result in results:
            snippet_lower = result["snippet"].lower()
            
            # Simple sentiment analysis - enhance with NLP in production
            if any(word in snippet_lower for word in ["true", "confirmed", "accurate", "correct"]):
                supporting += 1
                fact_check_sources.append({
                    "position": "supporting",
                    "source": result["url"],
                    "snippet": result["snippet"]
                })
            elif any(word in snippet_lower for word in ["false", "debunked", "incorrect", "myth"]):
                contradicting += 1
                fact_check_sources.append({
                    "position": "contradicting",
                    "source": result["url"],
                    "snippet": result["snippet"]
                })
            else:
                uncertain += 1
        
        total = len(results)
        confidence = max(supporting, contradicting) / total if total > 0 else 0
        
        verdict = "UNVERIFIED"
        if supporting > contradicting * 2:
            verdict = "LIKELY TRUE"
        elif contradicting > supporting * 2:
            verdict = "LIKELY FALSE"
        elif supporting > contradicting:
            verdict = "POSSIBLY TRUE"
        elif contradicting > supporting:
            verdict = "POSSIBLY FALSE"
        
        return {
            "claim": claim,
            "verdict": verdict,
            "confidence": confidence,
            "evidence": {
                "supporting": supporting,
                "contradicting": contradicting,
                "uncertain": uncertain
            },
            "sources": fact_check_sources[:5]  # Top 5 sources
        }
    
    def _extract_competitive_insights(
        self,
        results: List[Dict[str, Any]],
        competitor: str,
        research_area: str
    ) -> Dict[str, Any]:
        """Extract competitive insights from search results."""
        insights = {
            "competitor": competitor,
            "area": research_area,
            "findings": [],
            "data_points": []
        }
        
        for result in results[:5]:  # Top 5 results
            # Extract relevant snippets
            if competitor.lower() in result["snippet"].lower():
                insights["findings"].append({
                    "insight": result["snippet"],
                    "source": result["url"],
                    "relevance": result["score"]
                })
                
                # Extract numerical data if present
                import re
                numbers = re.findall(r'\$?[\d,]+\.?\d*[MBK]?%?', result["snippet"])
                if numbers:
                    insights["data_points"].extend(numbers)
        
        return insights
    
    def _generate_competitive_analysis(
        self,
        competitive_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate structured competitive analysis report."""
        analysis = {
            "summary": "Competitive landscape analysis based on current market data",
            "competitors": {},
            "key_insights": [],
            "recommendations": []
        }
        
        for competitor, data in competitive_data.items():
            analysis["competitors"][competitor] = {
                "strengths": [],
                "weaknesses": [],
                "market_position": "analyzing...",
                "data": data
            }
            
            # Generate insights based on findings
            for area, insights in data.items():
                if insights["findings"]:
                    key_insight = f"{competitor} - {area}: {insights['findings'][0]['insight'][:100]}..."
                    analysis["key_insights"].append(key_insight)
        
        # Add strategic recommendations
        analysis["recommendations"] = [
            "Monitor competitor pricing strategies closely",
            "Differentiate through unique feature development",
            "Focus on underserved market segments"
        ]
        
        return analysis
    
    def _filter_recent_results(
        self,
        results: List[Dict[str, Any]],
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Filter results by recency."""
        recent_results = []
        
        for result in results:
            # Check if date is available and recent
            if "date" in result and result["date"]:
                # Simple date parsing - enhance in production
                recent_results.append(result)
            else:
                # Include results without dates but lower their relevance
                result["score"] *= 0.8
                recent_results.append(result)
        
        return sorted(recent_results, key=lambda x: x["score"], reverse=True)
    
    def _structure_realtime_data(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Structure real-time search data."""
        structured_data = []
        
        for result in results:
            structured_data.append({
                "title": result["title"],
                "summary": result["snippet"],
                "source": result["url"],
                "timestamp": result.get("date", "recent"),
                "relevance": result["score"]
            })
        
        return structured_data
    
    def _synthesize_research(
        self,
        query: str,
        results: List[Dict[str, Any]],
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Synthesize comprehensive research from multiple sources."""
        synthesis = {
            "query": query,
            "executive_summary": "",
            "sections": [],
            "key_findings": [],
            "data_points": [],
            "sources": []
        }
        
        # Group results by topic similarity (simplified)
        topics = {}
        for result in results:
            # Simple topic extraction based on title words
            title_words = result["title"].lower().split()
            topic_key = None
            
            for word in title_words:
                if len(word) > 5:  # Simple heuristic
                    topic_key = word
                    break
            
            if topic_key:
                if topic_key not in topics:
                    topics[topic_key] = []
                topics[topic_key].append(result)
        
        # Create sections from topics
        for topic, topic_results in topics.items():
            section = {
                "topic": topic.title(),
                "content": "\n".join([r["snippet"] for r in topic_results[:3]]),
                "sources": [r["url"] for r in topic_results[:3]]
            }
            synthesis["sections"].append(section)
        
        # Extract key findings
        for result in results[:10]:
            if result["score"] > 0.7:
                synthesis["key_findings"].append(result["snippet"][:150] + "...")
        
        # Generate executive summary
        synthesis["executive_summary"] = (
            f"Research synthesis for '{query}' based on {len(results)} sources. "
            f"Identified {len(synthesis['sections'])} main topic areas with "
            f"{len(synthesis['key_findings'])} key findings."
        )
        
        # Add source citations
        synthesis["sources"] = self._format_citations(results[:10])
        
        return synthesis
    
    def _format_citations(self, results: List[Dict[str, Any]]) -> List[str]:
        """Format results as citations."""
        citations = []
        
        for i, result in enumerate(results):
            citation = f"[{i+1}] {result['title']}. {result['url']}"
            if result.get("date"):
                citation += f" ({result['date']})"
            citations.append(citation)
        
        return citations
    
    def _get_time_range_param(self, time_range: str) -> str:
        """Convert time range to search parameter."""
        time_params = {
            "day": "qdr:d",
            "week": "qdr:w",
            "month": "qdr:m",
            "year": "qdr:y"
        }
        return time_params.get(time_range, "")
    
    async def estimate_cost(self, prompt: str) -> float:
        """Estimate cost for search operations."""
        # Search API costs vary by provider
        if self.provider == "perplexity":
            # Perplexity pricing per search
            return 0.005 * self.max_results
        elif self.provider == "serper":
            # Serper pricing per search
            return 0.01
        else:
            # No cost for web scraping
            return 0.0
    
    async def validate_input(self, context: ExecutionContext) -> bool:
        """Validate search agent can handle the context."""
        # Check for valid search query
        if not context.parameters.get("query") and not context.parameters.get("claim"):
            logger.warning("No search query or claim provided")
            return False
        
        # Verify API credentials if using API provider
        if self.provider in ["perplexity", "serper"] and not self.api_key:
            logger.error(f"No API key configured for {self.provider}")
            return False
        
        return True
