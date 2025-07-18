"""
Vector store for embedding-based search and retrieval.

This module provides vector storage and search capabilities for
semantic memory retrieval using embeddings.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime


class VectorStore:
    """
    Vector store for managing embeddings and similarity search.
    """
    
    def __init__(self):
        """Initialize the vector store."""
        self.embeddings: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    async def add_embedding(
        self,
        key: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add an embedding to the store.
        
        Args:
            key: Unique identifier for the embedding
            embedding: The embedding vector
            metadata: Optional metadata to associate with the embedding
        
        Returns:
            True if successful
        """
        self.embeddings[key] = np.array(embedding)
        self.metadata[key] = metadata or {}
        self.metadata[key]["created_at"] = datetime.utcnow()
        return True
    
    async def get_conversation_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.
        
        Args:
            user_id: User ID
            session_id: Session ID
            limit: Maximum number of messages to return
        
        Returns:
            List of chat messages
        """
        # Mock implementation for testing
        return [
            {
                "role": "user",
                "content": "Hello, how are you?",
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "role": "assistant",
                "content": "I'm doing well, thank you! How can I help you today?",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get user's chat sessions.
        
        Args:
            user_id: User ID
            limit: Maximum number of sessions to return
        
        Returns:
            List of chat sessions
        """
        # Mock implementation for testing
        sessions = [
            {
                "id": "session-1",
                "title": "Project Discussion",
                "model": "claude",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "message_count": 5
            },
            {
                "id": "session-2", 
                "title": "Code Review",
                "model": "gpt-4",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "message_count": 3
            }
        ]
        # Apply limit and offset
        return sessions[offset:offset+limit]
    
    async def delete_session(
        self,
        user_id: str,
        session_id: str
    ) -> bool:
        """
        Delete a chat session.
        
        Args:
            user_id: User ID
            session_id: Session ID
        
        Returns:
            True if successful
        """
        # Mock implementation for testing
        return True
    
    async def update_session_model(
        self,
        user_id: str,
        session_id: str,
        model: str
    ) -> bool:
        """
        Update the model for a session.
        
        Args:
            user_id: User ID
            session_id: Session ID
            model: New model name
        
        Returns:
            True if successful
        """
        # Mock implementation for testing
        return True
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings.
        
        Args:
            query_embedding: The query embedding vector
            top_k: Number of results to return
            threshold: Minimum similarity threshold
        
        Returns:
            List of similar items with metadata
        """
        if not self.embeddings:
            return []
        
        query_vec = np.array(query_embedding)
        results = []
        
        for key, embedding in self.embeddings.items():
            # Cosine similarity
            similarity = np.dot(query_vec, embedding) / (
                np.linalg.norm(query_vec) * np.linalg.norm(embedding)
            )
            
            if similarity >= threshold:
                results.append({
                    "key": key,
                    "similarity": float(similarity),
                    "metadata": self.metadata.get(key, {})
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    async def delete_embedding(self, key: str) -> bool:
        """
        Delete an embedding from the store.
        
        Args:
            key: The key of the embedding to delete
        
        Returns:
            True if deleted, False if not found
        """
        if key in self.embeddings:
            del self.embeddings[key]
            del self.metadata[key]
            return True
        return False
    
    async def clear(self) -> bool:
        """
        Clear all embeddings from the store.
        
        Returns:
            True if successful
        """
        self.embeddings.clear()
        self.metadata.clear()
        return True
    
    async def get_embedding(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get an embedding by key.
        
        Args:
            key: The key of the embedding
        
        Returns:
            Dict with embedding and metadata, or None if not found
        """
        if key in self.embeddings:
            return {
                "key": key,
                "embedding": self.embeddings[key].tolist(),
                "metadata": self.metadata.get(key, {})
            }
        return None
    
    async def add_memory(
        self,
        content: str,
        memory_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a memory to the store.
        
        Args:
            content: The memory content
            memory_type: Type of memory (conversation, document, etc.)
            metadata: Optional metadata
        
        Returns:
            True if successful
        """
        # For now, just store as metadata without embedding
        # In production, would generate embedding from content
        key = f"{memory_type}_{datetime.utcnow().timestamp()}"
        self.metadata[key] = {
            "content": content,
            "type": memory_type,
            "metadata": metadata or {},
            "created_at": datetime.utcnow()
        }
        return True