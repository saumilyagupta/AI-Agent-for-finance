"""Memory system using Supabase for storage."""

from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np

from app.core.llm_provider import llm_manager
from app.database.crud import (
    create_memory_entry,
    get_memory_entries,
)
from app.database.database import get_db_session
from app.utils.config import settings
from app.utils.logger import logger

# Try to import sentence-transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available, using keyword-based search")


class MemorySystem:
    """Memory system using Supabase database for storage."""

    def __init__(self):
        self.short_term_memory: Dict[str, Any] = {}  # Session-based memory
        self.embedding_model = None

        if EMBEDDINGS_AVAILABLE:
            try:
                # Initialize embedding model for semantic search
                self.embedding_model = SentenceTransformer(settings.embedding_model)
                logger.info(f"Embedding model '{settings.embedding_model}' initialized")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embedding_model = None
        else:
            logger.info("Using keyword-based search (embeddings not available)")

    def store_short_term(self, key: str, value: Any):
        """Store data in short-term (session) memory."""
        self.short_term_memory[key] = value

    def get_short_term(self, key: str) -> Optional[Any]:
        """Retrieve data from short-term memory."""
        return self.short_term_memory.get(key)

    def clear_short_term(self):
        """Clear short-term memory."""
        self.short_term_memory.clear()

    async def store_execution(
        self,
        execution_id: UUID,
        goal: str,
        plan: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ):
        """Store execution in long-term memory (Supabase)."""
        try:
            content = f"Goal: {goal}\nPlan: {plan}\nResult: {result}\nSuccess: {success}"
            
            # Extract keywords using LLM if available, otherwise use simple extraction
            keywords = await self._extract_keywords_with_llm(goal) if llm_manager.primary_provider else self._extract_keywords(goal)
            
            # Generate context using LLM if available
            context = await self._generate_context_with_llm(goal, plan) if llm_manager.primary_provider else f"Execution {execution_id}: {goal}"
            
            tags = ["execution", "goal"] + keywords[:5]

            # Store in Supabase
            with get_db_session() as db:
                memory_entry = create_memory_entry(
                    db,
                    content=content,
                    execution_id=execution_id,
                    keywords=keywords,
                    context=context,
                    tags=tags,
                )
                logger.info(f"Stored execution {execution_id} in Supabase memory with ID: {memory_entry.id}")
        except Exception as e:
            logger.error(f"Failed to store execution in memory: {e}")

    async def search_similar_executions(
        self, goal: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar past executions using semantic search."""
        try:
            with get_db_session() as db:
                # Get all memory entries
                all_entries = get_memory_entries(db, skip=0, limit=1000)
                
                if not all_entries:
                    return []

                if self.embedding_model:
                    # Semantic search using embeddings
                    goal_embedding = self.embedding_model.encode(goal)
                    
                    # Calculate similarity scores
                    scored_entries = []
                    for entry in all_entries:
                        entry_embedding = self.embedding_model.encode(entry.content)
                        # Cosine similarity
                        similarity = np.dot(goal_embedding, entry_embedding) / (
                            np.linalg.norm(goal_embedding) * np.linalg.norm(entry_embedding)
                        )
                        scored_entries.append((entry, float(similarity)))
                    
                    # Sort by similarity and return top k
                    scored_entries.sort(key=lambda x: x[1], reverse=True)
                    results = scored_entries[:k]
                    
                    return [
                        {
                            "id": str(entry.id),
                            "content": entry.content,
                            "score": score,
                            "keywords": entry.keywords or [],
                            "tags": entry.tags or [],
                            "context": entry.context,
                        }
                        for entry, score in results
                    ]
                else:
                    # Keyword-based search
                    goal_keywords = set(self._extract_keywords(goal))
                    scored_entries = []
                    
                    for entry in all_entries:
                        entry_keywords = set(entry.keywords or [])
                        # Jaccard similarity
                        if goal_keywords or entry_keywords:
                            similarity = len(goal_keywords & entry_keywords) / len(goal_keywords | entry_keywords) if (goal_keywords | entry_keywords) else 0.0
                        else:
                            similarity = 0.0
                        scored_entries.append((entry, similarity))
                    
                    # Sort by similarity and return top k
                    scored_entries.sort(key=lambda x: x[1], reverse=True)
                    results = scored_entries[:k]
                    
                    return [
                        {
                            "id": str(entry.id),
                            "content": entry.content,
                            "score": score,
                            "keywords": entry.keywords or [],
                            "tags": entry.tags or [],
                            "context": entry.context,
                        }
                        for entry, score in results if score > 0
                    ]
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    async def get_execution_context(self, execution_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve execution context from memory."""
        try:
            with get_db_session() as db:
                entries = get_memory_entries(db, execution_id=execution_id, skip=0, limit=10)
                if entries:
                    return {
                        "execution_id": str(execution_id),
                        "entries": [
                            {
                                "content": e.content,
                                "keywords": e.keywords,
                                "tags": e.tags,
                                "context": e.context,
                            }
                            for e in entries
                        ],
                    }
        except Exception as e:
            logger.error(f"Failed to get execution context: {e}")
        return self.short_term_memory.get(str(execution_id))

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simple implementation)."""
        # Simple keyword extraction
        words = text.lower().split()
        # Filter common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        return keywords[:10]

    async def _extract_keywords_with_llm(self, text: str) -> List[str]:
        """Extract keywords using LLM."""
        try:
            prompt = f"Extract 5-10 key keywords from this text. Return only a comma-separated list:\n\n{text}"
            response = await llm_manager.generate(prompt, max_tokens=50)
            keywords_str = response["content"].strip()
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            return keywords[:10] if keywords else self._extract_keywords(text)
        except Exception as e:
            logger.warning(f"LLM keyword extraction failed: {e}, using simple extraction")
            return self._extract_keywords(text)

    async def _generate_context_with_llm(self, goal: str, plan: Dict[str, Any]) -> str:
        """Generate context using LLM."""
        try:
            prompt = f"Generate a brief context summary (1-2 sentences) for this goal and plan:\n\nGoal: {goal}\nPlan: {plan}"
            response = await llm_manager.generate(prompt, max_tokens=100)
            return response["content"].strip()
        except Exception as e:
            logger.warning(f"LLM context generation failed: {e}")
            return f"Execution goal: {goal}"


# Global memory instance
memory_system = MemorySystem()

