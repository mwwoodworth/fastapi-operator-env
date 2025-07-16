"""
Agent system tests for BrainOps backend.

Tests the multi-agent orchestration system including individual agent
functionality, LangGraph execution, routing logic, and cost tracking
for all AI model interactions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from .agents.base import BaseAgent, AgentNode, AgentGraph
from .agents.claude_agent import ClaudeAgent
from .agents.codex_agent import CodexAgent
from .agents.gemini_agent import GeminiAgent
from .agents.search_agent import SearchAgent


@pytest.mark.asyncio
class TestBaseAgentSystem:
    """Test core agent system functionality."""
    
    async def test_agent_node_execution(self):
        """Test basic agent node execution and state management."""
        # Create a test agent node
        class TestNode(AgentNode):
            async def execute(self, state: dict) -> dict:
                # Simple test logic - add to counter
                state["counter"] = state.get("counter", 0) + 1
                state["executed_nodes"] = state.get("executed_nodes", [])
                state["executed_nodes"].append(self.name)
                return state
        
        # Create and execute node
        node = TestNode(name="test_node")
        initial_state = {"input": "test"}
        
        result_state = await node.execute(initial_state)
        
        # Verify execution
        assert result_state["counter"] == 1
        assert "test_node" in result_state["executed_nodes"]
        assert result_state["input"] == "test"  # Original state preserved
    
    async def test_agent_graph_construction(self):
        """Test building and validating agent graphs."""
        graph = AgentGraph()
        
        # Add nodes
        node1 = AgentNode(name="start")
        node2 = AgentNode(name="process")
        node3 = AgentNode(name="end")
        
        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)
        
        # Add edges
        graph.add_edge("start", "process")
        graph.add_edge("process", "end")
        
        # Verify graph structure
        assert len(graph.nodes) == 3
        assert len(graph.edges["start"]) == 1
        assert graph.edges["start"][0] == "process"
        
        # Test graph validation
        is_valid = graph.validate()
        assert is_valid is True
        
        # Test invalid graph (circular dependency)
        graph.add_edge("end", "start")
        is_valid = graph.validate()
        assert is_valid is False  # Should detect cycle
    
    async def test_conditional_routing(self):
        """Test conditional routing between agent nodes."""
        graph = AgentGraph()
        
        # Create nodes with routing logic
        class RouterNode(AgentNode):
            async def execute(self, state: dict) -> dict:
                # Route based on input value
                if state.get("value", 0) > 5:
                    state["next_node"] = "high_path"
                else:
                    state["next_node"] = "low_path"
                return state
        
        router = RouterNode(name="router")
        high_node = AgentNode(name="high_path")
        low_node = AgentNode(name="low_path")
        
        graph.add_node(router)
        graph.add_node(high_node)
        graph.add_node(low_node)
        
        # Test routing with high value
        state_high = {"value": 10}
        result = await router.execute(state_high)
        assert result["next_node"] == "high_path"
        
        # Test routing with low value
        state_low = {"value": 3}
        result = await router.execute(state_low)
        assert result["next_node"] == "low_path"


@pytest.mark.asyncio
class TestClaudeAgent:
    """Test Claude agent functionality."""
    
    @pytest.fixture
    async def claude_agent(self):
        """Provide a Claude agent instance with mocked client."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            agent = ClaudeAgent()
            agent.client = mock_anthropic.return_value
            yield agent
    
    async def test_content_generation(self, claude_agent):
        """Test Claude content generation with proper formatting."""
        # Mock Claude API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated content about roofing estimates")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        
        claude_agent.client.messages.create = AsyncMock(return_value=mock_response)
        
        # Generate content
        result = await claude_agent.generate_content(
            topic="Commercial roofing estimates",
            style="professional",
            max_tokens=1000
        )
        
        # Verify result
        assert "content" in result
        assert result["content"] == "Generated content about roofing estimates"
        assert result["tokens_used"]["input"] == 100
        assert result["tokens_used"]["output"] == 50
        
        # Verify API call
        claude_agent.client.messages.create.assert_called_once()
        call_args = claude_agent.client.messages.create.call_args[1]
        assert call_args["model"] == "claude-3-opus-20240229"
        assert call_args["max_tokens"] == 1000
    
    async def test_document_analysis(self, claude_agent):
        """Test Claude's document analysis capabilities."""
        # Mock response for document analysis
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "summary": "Roofing specification document",
            "key_points": ["TPO system", "20-year warranty", "Class A fire rating"],
            "concerns": ["Drainage details missing"]
        }))]
        mock_response.usage = MagicMock(input_tokens=500, output_tokens=150)
        
        claude_agent.client.messages.create = AsyncMock(return_value=mock_response)
        
        # Analyze document
        result = await claude_agent.analyze_document(
            document="[Long roofing specification document]",
            analysis_type="specification_review"
        )
        
        # Verify structured analysis
        assert result["summary"] == "Roofing specification document"
        assert len(result["key_points"]) == 3
        assert "TPO system" in result["key_points"]
        assert len(result["concerns"]) == 1
    
    async def test_cost_tracking(self, claude_agent):
        """Test token usage and cost tracking."""
        # Mock multiple API calls
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        mock_response.usage = MagicMock(input_tokens=1000, output_tokens=500)
        
        claude_agent.client.messages.create = AsyncMock(return_value=mock_response)
        
        # Make multiple calls
        for _ in range(3):
            await claude_agent.generate_text(prompt="Test prompt")
        
        # Calculate expected costs (Claude-3 Opus pricing)
        # Input: $15/million tokens, Output: $75/million tokens
        expected_input_cost = (3 * 1000 / 1_000_000) * 15 * 100  # cents
        expected_output_cost = (3 * 500 / 1_000_000) * 75 * 100  # cents
        
        total_cost = await claude_agent.get_total_cost()
        
        assert total_cost == pytest.approx(expected_input_cost + expected_output_cost, rel=0.01)


@pytest.mark.asyncio
class TestCodexAgent:
    """Test Codex/GPT-4 agent functionality."""
    
    @pytest.fixture
    async def codex_agent(self):
        """Provide a Codex agent instance with mocked client."""
        with patch('openai.AsyncOpenAI') as mock_openai:
            agent = CodexAgent()
            agent.client = mock_openai.return_value
            yield agent
    
    async def test_code_generation(self, codex_agent):
        """Test code generation for automation scenarios."""
        # Mock GPT-4 response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="""
```python
def calculate_roof_area(length: float, width: float, pitch: float) -> float:
    \"\"\"Calculate roof area accounting for pitch.\"\"\"
    pitch_factor = (pitch ** 2 + 144) ** 0.5 / 12
    return length * width * pitch_factor
```
"""))]
        mock_response.usage = MagicMock(prompt_tokens=150, completion_tokens=100)
        
        codex_agent.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Generate code
        result = await codex_agent.generate_code(
            description="Function to calculate roof area with pitch adjustment",
            language="python"
        )
        
        # Verify code extraction
        assert "calculate_roof_area" in result["code"]
        assert "pitch_factor" in result["code"]
        assert result["language"] == "python"
        assert result["tokens_used"]["input"] == 150
    
    async def test_code_review(self, codex_agent):
        """Test code review and improvement suggestions."""
        # Sample code to review
        code_to_review = """
def calc_cost(area, price):
    return area * price
"""
        
        # Mock review response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "issues": [
                "No type hints",
                "No docstring",
                "No input validation"
            ],
            "improved_code": """
def calculate_cost(area: float, price_per_sqft: float) -> float:
    \"\"\"Calculate total cost based on area and price per square foot.
    
    Args:
        area: Total area in square feet
        price_per_sqft: Price per square foot
        
    Returns:
        Total cost
        
    Raises:
        ValueError: If area or price is negative
    \"\"\"
    if area < 0 or price_per_sqft < 0:
        raise ValueError("Area and price must be non-negative")
    return area * price_per_sqft
"""
        })))]
        mock_response.usage = MagicMock(prompt_tokens=200, completion_tokens=250)
        
        codex_agent.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Review code
        result = await codex_agent.review_code(code_to_review)
        
        # Verify review results
        assert len(result["issues"]) == 3
        assert "type hints" in result["issues"][0]
        assert "calculate_cost" in result["improved_code"]
        assert "ValueError" in result["improved_code"]


@pytest.mark.asyncio
class TestGeminiAgent:
    """Test Gemini agent functionality."""
    
    @pytest.fixture
    async def gemini_agent(self):
        """Provide a Gemini agent instance with mocked client."""
        with patch('google.generativeai.GenerativeModel') as mock_gemini:
            agent = GeminiAgent()
            agent.model = mock_gemini.return_value
            yield agent
    
    async def test_seo_optimization(self, gemini_agent):
        """Test SEO content optimization."""
        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "optimized_title": "Commercial Roofing Costs: 2024 Complete Pricing Guide",
            "meta_description": "Discover accurate commercial roofing costs per square foot. Compare TPO, EPDM, and metal systems with real pricing data from Denver contractors.",
            "keywords": ["commercial roofing cost", "TPO pricing", "roofing cost per square foot"],
            "content_improvements": [
                "Add location-specific pricing",
                "Include comparison table",
                "Add FAQ section"
            ]
        })
        
        gemini_agent.model.generate_content_async = AsyncMock(return_value=mock_response)
        
        # Optimize content
        result = await gemini_agent.optimize_for_seo(
            content="Basic article about roofing costs",
            target_keywords=["commercial roofing", "roofing cost"]
        )
        
        # Verify SEO optimization
        assert "Complete Pricing Guide" in result["optimized_title"]
        assert len(result["keywords"]) >= 3
        assert "meta_description" in result
        assert len(result["content_improvements"]) >= 3
    
    async def test_content_variation_generation(self, gemini_agent):
        """Test generating content variations for A/B testing."""
        # Mock response with variations
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "variations": [
                {
                    "version": "A",
                    "headline": "Save 30% on Commercial Roofing",
                    "cta": "Get Free Estimate"
                },
                {
                    "version": "B",
                    "headline": "Commercial Roofing Experts - 20 Year Warranty",
                    "cta": "Request Quote"
                }
            ]
        })
        
        gemini_agent.model.generate_content_async = AsyncMock(return_value=mock_response)
        
        # Generate variations
        result = await gemini_agent.generate_variations(
            base_content="Commercial roofing services",
            num_variations=2
        )
        
        # Verify variations
        assert len(result["variations"]) == 2
        assert result["variations"][0]["version"] == "A"
        assert result["variations"][1]["version"] == "B"
        assert all("headline" in v for v in result["variations"])


@pytest.mark.asyncio
class TestSearchAgent:
    """Test search/research agent functionality."""
    
    @pytest.fixture
    async def search_agent(self):
        """Provide a search agent instance with mocked client."""
        agent = SearchAgent()
        with patch('httpx.AsyncClient') as mock_client:
            agent.client = mock_client.return_value
            yield agent
    
    async def test_web_search(self, search_agent):
        """Test web search functionality."""
        # Mock search API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "TPO Roofing Costs 2024",
                    "url": "https://example.com/tpo-costs",
                    "snippet": "TPO roofing typically costs $7-9 per square foot..."
                },
                {
                    "title": "Commercial Roofing Price Guide",
                    "url": "https://example.com/price-guide",
                    "snippet": "Compare commercial roofing materials and pricing..."
                }
            ]
        }
        
        search_agent.client.get = AsyncMock(return_value=mock_response)
        
        # Perform search
        result = await search_agent.search(
            query="TPO roofing cost per square foot Denver",
            num_results=10
        )
        
        # Verify results
        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "TPO Roofing Costs 2024"
        assert "snippet" in result["results"][0]
    
    async def test_structured_research(self, search_agent):
        """Test structured research with multiple queries."""
        # Mock multiple search responses
        search_responses = [
            {"results": [{"title": "TPO Costs", "snippet": "TPO: $7-9/sqft"}]},
            {"results": [{"title": "EPDM Costs", "snippet": "EPDM: $5-7/sqft"}]},
            {"results": [{"title": "Labor Rates", "snippet": "Denver labor: $75-100/hour"}]}
        ]
        
        search_agent.client.get = AsyncMock(side_effect=[
            MagicMock(status_code=200, json=MagicMock(return_value=resp))
            for resp in search_responses
        ])
        
        # Conduct structured research
        research_plan = {
            "material_costs": "TPO roofing material cost Denver",
            "epdm_costs": "EPDM roofing cost comparison",
            "labor_rates": "commercial roofing labor rates Denver"
        }
        
        results = await search_agent.conduct_research(research_plan)
        
        # Verify comprehensive research
        assert len(results) == 3
        assert "material_costs" in results
        assert "TPO: $7-9/sqft" in results["material_costs"]["results"][0]["snippet"]
        assert "labor_rates" in results
        
        # Verify multiple searches were made
        assert search_agent.client.get.call_count == 3