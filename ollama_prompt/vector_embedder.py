#!/usr/bin/env python3
"""
Vector Embedder for semantic relevance scoring.

Uses Ollama's embedding models (nomic-embed-text by default) to generate
vector embeddings for semantic similarity comparisons.
"""

import hashlib
import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union
import math


class VectorEmbedder:
    """
    Generate and compare vector embeddings using Ollama.

    Uses nomic-embed-text model by default for high-quality embeddings.
    Supports caching to avoid regenerating embeddings for unchanged content.

    Usage:
        embedder = VectorEmbedder()
        emb1 = embedder.embed("Hello world")
        emb2 = embedder.embed("Hi there")
        similarity = embedder.cosine_similarity(emb1, emb2)
    """

    DEFAULT_MODEL = "nomic-embed-text"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        cache: Optional[Dict[str, List[float]]] = None,
        ollama_host: Optional[str] = None
    ):
        """
        Initialize vector embedder.

        Args:
            model: Ollama embedding model name
            cache: Optional dict for embedding cache (key: content hash, value: embedding)
            ollama_host: Optional Ollama API host (default: http://localhost:11434)
        """
        self.model = model
        self.cache = cache if cache is not None else {}
        self.ollama_host = ollama_host or "http://localhost:11434"
        self._model_available: Optional[bool] = None

    def _get_cache_key(self, text: str) -> str:
        """
        Generate cache key for text content.

        Args:
            text: Text to hash

        Returns:
            str: MD5 hash of text + model name
        """
        content = f"{self.model}:{text}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def is_available(self) -> bool:
        """
        Check if embedding model is available.

        Returns:
            bool: True if model is available via Ollama
        """
        if self._model_available is not None:
            return self._model_available

        try:
            # Try to get a simple embedding to test availability
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            self._model_available = self.model in result.stdout
            return self._model_available
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            self._model_available = False
            return False

    def embed(self, text: str, use_cache: bool = True) -> Optional[List[float]]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed
            use_cache: Whether to use/update cache

        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        if not text or not text.strip():
            return None

        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self.cache:
                return self.cache[cache_key]

        # Generate embedding via Ollama API
        try:
            import urllib.request
            import urllib.error

            url = f"{self.ollama_host}/api/embeddings"
            data = json.dumps({
                "model": self.model,
                "prompt": text
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                embedding = result.get("embedding")

                if embedding and use_cache:
                    cache_key = self._get_cache_key(text)
                    self.cache[cache_key] = embedding

                return embedding

        except (urllib.error.URLError, json.JSONDecodeError, KeyError, Exception):
            return None

    def batch_embed(
        self,
        texts: List[str],
        use_cache: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use/update cache

        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        return [self.embed(text, use_cache) for text in texts]

    @staticmethod
    def cosine_similarity(
        vec1: Optional[List[float]],
        vec2: Optional[List[float]]
    ) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            float: Cosine similarity (-1 to 1), or 0.0 if either vector is None/empty
        """
        if not vec1 or not vec2:
            return 0.0

        if len(vec1) != len(vec2):
            return 0.0

        # Calculate dot product and magnitudes
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        # Zero-norm protection
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def score_relevance(
        self,
        text: str,
        context: str,
        use_cache: bool = True
    ) -> float:
        """
        Score text relevance to context using semantic similarity.

        Args:
            text: Text to score
            context: Context to compare against
            use_cache: Whether to use cache

        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        text_embedding = self.embed(text, use_cache)
        context_embedding = self.embed(context, use_cache)

        similarity = self.cosine_similarity(text_embedding, context_embedding)

        # Convert from [-1, 1] to [0, 1] range
        return (similarity + 1) / 2

    def score_relevance_batch(
        self,
        texts: List[str],
        context: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Score multiple texts against a single context.

        More efficient than calling score_relevance repeatedly
        as context embedding is only generated once.

        Args:
            texts: List of texts to score
            context: Context to compare against
            use_cache: Whether to use cache

        Returns:
            List of relevance scores (0.0 to 1.0)
        """
        context_embedding = self.embed(context, use_cache)
        if not context_embedding:
            return [0.0] * len(texts)

        scores = []
        for text in texts:
            text_embedding = self.embed(text, use_cache)
            similarity = self.cosine_similarity(text_embedding, context_embedding)
            scores.append((similarity + 1) / 2)

        return scores

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache info
        """
        return {
            "model": self.model,
            "cache_size": len(self.cache),
            "cache_keys": list(self.cache.keys())[:10]  # First 10 keys
        }

    def clear_cache(self):
        """Clear the embedding cache."""
        self.cache.clear()


class EmbeddingStore:
    """
    Database storage for embeddings.

    Provides persistent storage of embeddings in SQLite to avoid
    regenerating them across sessions.
    """

    def __init__(self, db):
        """
        Initialize embedding store.

        Args:
            db: SessionDatabase instance
        """
        self.db = db

    def save_embedding(
        self,
        message_id: int,
        model: str,
        embedding: List[float]
    ) -> int:
        """
        Save embedding for a message.

        Args:
            message_id: Message ID
            model: Model used for embedding
            embedding: Embedding vector

        Returns:
            int: Embedding record ID
        """
        # Serialize embedding as JSON bytes
        embedding_blob = json.dumps(embedding).encode('utf-8')

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO embeddings (message_id, model, embedding, created_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (message_id, model, embedding_blob))
            conn.commit()
            return cursor.lastrowid

    def get_embedding(
        self,
        message_id: int,
        model: Optional[str] = None
    ) -> Optional[List[float]]:
        """
        Get embedding for a message.

        Args:
            message_id: Message ID
            model: Optional model filter

        Returns:
            Embedding vector, or None if not found
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if model:
                cursor.execute("""
                    SELECT embedding FROM embeddings
                    WHERE message_id = ? AND model = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (message_id, model))
            else:
                cursor.execute("""
                    SELECT embedding FROM embeddings
                    WHERE message_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (message_id,))

            row = cursor.fetchone()
            if row:
                return json.loads(row[0].decode('utf-8'))
            return None

    def has_embedding(self, message_id: int, model: Optional[str] = None) -> bool:
        """
        Check if embedding exists for a message.

        Args:
            message_id: Message ID
            model: Optional model filter

        Returns:
            bool: True if embedding exists
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if model:
                cursor.execute("""
                    SELECT 1 FROM embeddings
                    WHERE message_id = ? AND model = ?
                    LIMIT 1
                """, (message_id, model))
            else:
                cursor.execute("""
                    SELECT 1 FROM embeddings WHERE message_id = ? LIMIT 1
                """, (message_id,))

            return cursor.fetchone() is not None

    def delete_embedding(self, message_id: int):
        """
        Delete embeddings for a message.

        Args:
            message_id: Message ID
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM embeddings WHERE message_id = ?",
                (message_id,)
            )
            conn.commit()

    def get_embedding_count(self) -> int:
        """
        Get total number of stored embeddings.

        Returns:
            int: Embedding count
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            return cursor.fetchone()[0]
