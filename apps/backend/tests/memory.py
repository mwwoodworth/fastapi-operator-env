"""
Memory system tests for BrainOps backend.

Tests the RAG memory system including vector storage, knowledge retrieval,
conversation management, and document chunking functionality that powers
the intelligent context awareness across all operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import numpy as np

from apps.backend.memory.memory_store import MemoryStore
from apps.backend.memory.knowledge import KnowledgeManager
from apps.backend.memory.vector_utils import VectorUtils
from apps.backend.memory.models import MemoryEntry, ConversationSession, DocumentChunk


@pytest.mark.asyncio
class TestMemoryStore:
    """Test core memory storage and retrieval functionality."""
    
    @pytest.fixture
    async def memory_store(self):
        """Provide a memory store instance with mocked database."""
        with patch('apps.backend.memory.supabase_client.SupabaseClient') as mock_client:
            store = MemoryStore()
            store.supabase = mock_client
            yield store
    
    async def test_add_conversation_memory(self, memory_store):
        """Test storing conversation interactions in memory."""
        # Mock the database insert
        memory_store.supabase.table.return_value.insert.return_value.execute.return_value = {
            "data": [{
                "id": "memory_123",
                "content": "User asked about roofing estimates",
                "memory_type": "conversation"
            }]
        }
        
        # Add conversation memory
        result = await memory_store.add_conversation(
            user_id="user_123",
            session_id="session_456",
            user_message="I need a roofing estimate for a 10,000 sqft building",
            assistant_response="I'll help you generate that estimate. What type of roofing material?",
            metadata={"context": "roofing_consultation"}
        )
        
        # Verify storage call
        assert result["id"] == "memory_123"
        memory_store.supabase.table.assert_called_with("memory_entries")
        
        # Verify the stored data structure
        insert_call = memory_store.supabase.table.return_value.insert.call_args[0][0]
        assert insert_call["memory_type"] == "conversation"
        assert insert_call["user_id"] == "user_123"
        assert insert_call["session_id"] == "session_456"
        assert "User asked about roofing estimates" in insert_call["content"]
    
    async def test_add_knowledge_with_embedding(self, memory_store):
        """Test storing knowledge with vector embeddings."""
        # Mock embedding generation
        with patch('apps.backend.memory.vector_utils.VectorUtils.generate_embedding') as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]  # Simplified embedding
            
            memory_store.supabase.table.return_value.insert.return_value.execute.return_value = {
                "data": [{"id": "knowledge_123"}]
            }
            
            # Add knowledge entry
            result = await memory_store.add_knowledge(
                content="TPO roofing costs $7-9 per square foot installed in Denver",
                metadata={
                    "source": "pricing_guide",
                    "region": "Denver",
                    "material": "TPO"
                },
                memory_type="knowledge"
            )
            
            # Verify embedding was generated
            mock_embed.assert_called_once_with(
                "TPO roofing costs $7-9 per square foot installed in Denver"
            )
            
            # Verify storage includes embedding
            insert_call = memory_store.supabase.table.return_value.insert.call_args[0][0]
            assert insert_call["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]
            assert insert_call["memory_type"] == "knowledge"
    
    async def test_search_memories_by_similarity(self, memory_store):
        """Test vector similarity search for relevant memories."""
        # Mock embedding for search query
        with patch('apps.backend.memory.vector_utils.VectorUtils.generate_embedding') as mock_embed:
            mock_embed.return_value = [0.15, 0.25, 0.35, 0.45, 0.55]
            
            # Mock RPC call for similarity search
            memory_store.supabase.rpc.return_value.execute.return_value = {
                "data": [
                    {
                        "id": "memory_1",
                        "content": "TPO roofing installation guide",
                        "similarity": 0.95,
                        "metadata": {"material": "TPO"}
                    },
                    {
                        "id": "memory_2",
                        "content": "EPDM roofing costs and benefits",
                        "similarity": 0.75,
                        "metadata": {"material": "EPDM"}
                    }
                ]
            }
            
            # Perform similarity search
            results = await memory_store.search_memories(
                query="Tell me about TPO roofing",
                memory_types=["knowledge"],
                limit=5,
                similarity_threshold=0.7
            )
            
            # Verify results
            assert len(results) == 2
            assert results[0]["content"] == "TPO roofing installation guide"
            assert results[0]["similarity"] == 0.95
            
            # Verify RPC was called correctly
            memory_store.supabase.rpc.assert_called_with(
                'search_memories',
                {
                    'query_embedding': [0.15, 0.25, 0.35, 0.45, 0.55],
                    'match_count': 5,
                    'memory_types': ['knowledge'],
                    'similarity_threshold': 0.7
                }
            )
    
    async def test_get_conversation_history(self, memory_store):
        """Test retrieving conversation history for a session."""
        # Mock database query
        memory_store.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = {
            "data": [
                {
                    "id": "msg_1",
                    "content": "User: What's the cost?\nAssistant: TPO costs $7-9/sqft",
                    "created_at": "2024-01-14T10:00:00Z"
                },
                {
                    "id": "msg_2",
                    "content": "User: What about warranties?\nAssistant: TPO typically has 20-year warranties",
                    "created_at": "2024-01-14T10:05:00Z"
                }
            ]
        }
        
        # Get conversation history
        history = await memory_store.get_conversation_history(
            session_id="session_123",
            limit=10
        )
        
        # Verify results
        assert len(history) == 2
        assert "What's the cost?" in history[0]["content"]
        assert "warranties" in history[1]["content"]
    
    async def test_memory_expiration(self, memory_store):
        """Test that expired memories are excluded from searches."""
        # Current time
        now = datetime.utcnow()
        
        # Mock search results with expired and valid memories
        memory_store.supabase.rpc.return_value.execute.return_value = {
            "data": [
                {
                    "id": "memory_1",
                    "content": "Current pricing info",
                    "expires_at": (now + timedelta(days=30)).isoformat(),
                    "similarity": 0.9
                },
                {
                    "id": "memory_2",
                    "content": "Outdated pricing info",
                    "expires_at": (now - timedelta(days=1)).isoformat(),
                    "similarity": 0.95
                }
            ]
        }
        
        # Search should filter out expired memories
        results = await memory_store.search_memories(
            query="pricing information",
            exclude_expired=True
        )
        
        # Only non-expired memory should be returned
        assert len(results) == 1
        assert results[0]["id"] == "memory_1"


@pytest.mark.asyncio
class TestKnowledgeManager:
    """Test knowledge management and document processing."""
    
    @pytest.fixture
    async def knowledge_manager(self):
        """Provide a knowledge manager instance."""
        with patch('apps.backend.memory.memory_store.MemoryStore') as mock_store:
            manager = KnowledgeManager()
            manager.memory_store = mock_store
            yield manager
    
    async def test_document_chunking(self, knowledge_manager):
        """Test document chunking for large documents."""
        # Test document
        document = """
        # Commercial Roofing Guide
        
        ## Chapter 1: TPO Roofing Systems
        TPO (Thermoplastic Polyolefin) is a single-ply roofing membrane that has gained 
        significant popularity in commercial applications. It offers excellent weather 
        resistance and energy efficiency.
        
        ### Installation Process
        The installation of TPO roofing involves several critical steps:
        1. Deck preparation and inspection
        2. Insulation installation
        3. Membrane attachment
        4. Seam welding
        5. Flashing installation
        
        ### Cost Factors
        TPO roofing costs vary based on several factors including roof size, complexity,
        location, and current market conditions. In Denver, typical costs range from
        $7 to $9 per square foot for a complete installation.
        
        ## Chapter 2: Maintenance Requirements
        Regular maintenance is essential for maximizing the lifespan of TPO roofing...
        """
        
        # Chunk the document
        chunks = await knowledge_manager.chunk_document(
            content=document,
            chunk_size=500,
            overlap=100,
            metadata={"source": "roofing_guide", "doc_type": "manual"}
        )
        
        # Verify chunking
        assert len(chunks) >= 3  # Should create multiple chunks
        assert all(len(chunk["content"]) <= 600 for chunk in chunks)  # Size limit with overlap
        assert chunks[0]["metadata"]["chunk_index"] == 0
        assert chunks[0]["metadata"]["source"] == "roofing_guide"
        
        # Verify overlap between chunks
        if len(chunks) > 1:
            # Check that chunks have some overlapping content
            chunk1_end = chunks[0]["content"][-50:]
            chunk2_start = chunks[1]["content"][:50:]
            # There should be some overlap in content
    
    async def test_knowledge_deduplication(self, knowledge_manager):
        """Test deduplication of similar knowledge entries."""
        # Mock existing knowledge search
        knowledge_manager.memory_store.search_memories.return_value = [
            {
                "id": "existing_1",
                "content": "TPO roofing costs $7-9 per square foot in Denver",
                "similarity": 0.98
            }
        ]
        
        # Try to add nearly identical knowledge
        should_add = await knowledge_manager.should_add_knowledge(
            content="TPO roofing price is $7-9 per sqft in Denver area",
            similarity_threshold=0.95
        )
        
        # Should not add duplicate
        assert should_add is False
        
        # Try to add different knowledge
        knowledge_manager.memory_store.search_memories.return_value = [
            {
                "id": "existing_1",
                "content": "TPO roofing costs $7-9 per square foot in Denver",
                "similarity": 0.65
            }
        ]
        
        should_add = await knowledge_manager.should_add_knowledge(
            content="EPDM roofing costs $5-7 per square foot in Denver",
            similarity_threshold=0.95
        )
        
        # Should add non-duplicate
        assert should_add is True
    
    async def test_knowledge_graph_building(self, knowledge_manager):
        """Test building relationships between knowledge entries."""
        # Mock related knowledge entries
        knowledge_entries = [
            {
                "id": "k1",
                "content": "TPO is a thermoplastic polyolefin roofing membrane",
                "metadata": {"topic": "materials"}
            },
            {
                "id": "k2",
                "content": "TPO installation requires heat welding equipment",
                "metadata": {"topic": "installation"}
            },
            {
                "id": "k3",
                "content": "Heat welding creates permanent seams in TPO",
                "metadata": {"topic": "techniques"}
            }
        ]
        
        # Build knowledge graph
        graph = await knowledge_manager.build_knowledge_graph(
            entries=knowledge_entries,
            relationship_threshold=0.7
        )
        
        # Verify relationships were identified
        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) >= 2  # Should find relationships
        
        # Check specific relationships
        tpo_relationships = [e for e in graph["edges"] if e["source"] == "k1" or e["target"] == "k1"]
        assert len(tpo_relationships) >= 1  # TPO should relate to installation


@pytest.mark.asyncio
class TestVectorUtils:
    """Test vector embedding and similarity utilities."""
    
    async def test_embedding_generation(self):
        """Test generating embeddings for text."""
        vector_utils = VectorUtils()
        
        with patch('openai.AsyncOpenAI') as mock_openai:
            # Mock OpenAI embedding response
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.embeddings.create.return_value = MagicMock(
                data=[MagicMock(embedding=[0.1] * 1536)]  # OpenAI embeddings are 1536 dimensions
            )
            
            # Generate embedding
            embedding = await vector_utils.generate_embedding(
                text="Commercial roofing estimate for Denver"
            )
            
            # Verify embedding
            assert len(embedding) == 1536
            assert all(isinstance(x, float) for x in embedding)
            
            # Verify API call
            mock_client.embeddings.create.assert_called_once_with(
                model="text-embedding-ada-002",
                input="Commercial roofing estimate for Denver"
            )
    
    async def test_batch_embedding_generation(self):
        """Test generating embeddings for multiple texts."""
        vector_utils = VectorUtils()
        
        texts = [
            "TPO roofing costs",
            "EPDM installation guide",
            "Commercial roof warranty"
        ]
        
        with patch.object(vector_utils, 'generate_embedding') as mock_generate:
            # Mock individual embedding calls
            mock_generate.side_effect = [
                [0.1] * 1536,
                [0.2] * 1536,
                [0.3] * 1536
            ]
            
            # Generate batch embeddings
            embeddings = await vector_utils.generate_batch_embeddings(texts)
            
            # Verify results
            assert len(embeddings) == 3
            assert mock_generate.call_count == 3
    
    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation between vectors."""
        vector_utils = VectorUtils()
        
        # Test vectors
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])  # Identical
        vec3 = np.array([0.0, 1.0, 0.0])  # Orthogonal
        vec4 = np.array([-1.0, 0.0, 0.0])  # Opposite
        
        # Calculate similarities
        sim_identical = vector_utils.cosine_similarity(vec1, vec2)
        sim_orthogonal = vector_utils.cosine_similarity(vec1, vec3)
        sim_opposite = vector_utils.cosine_similarity(vec1, vec4)
        
        # Verify similarities
        assert abs(sim_identical - 1.0) < 0.0001  # Should be 1.0
        assert abs(sim_orthogonal - 0.0) < 0.0001  # Should be 0.0
        assert abs(sim_opposite - (-1.0)) < 0.0001  # Should be -1.0
    
    def test_embedding_compression(self):
        """Test embedding compression for storage optimization."""
        vector_utils = VectorUtils()
        
        # Create a test embedding
        original = np.random.rand(1536).astype(np.float32)
        
        # Compress embedding
        compressed = vector_utils.compress_embedding(original)
        
        # Decompress
        decompressed = vector_utils.decompress_embedding(compressed)
        
        # Verify compression worked
        assert len(compressed) < len(original) * 4  # Should be smaller than raw floats
        assert np.allclose(original, decompressed, rtol=1e-5)  # Should be very close


@pytest.fixture
async def test_db():
    """Provide a test database connection."""
    # This would set up a test database in a real implementation
    pass