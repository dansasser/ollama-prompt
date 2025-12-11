#!/usr/bin/env python3
"""Tests for VectorEmbedder module."""

import json
import pytest
from unittest.mock import patch, MagicMock

from ollama_prompt.vector_embedder import VectorEmbedder, EmbeddingStore
from ollama_prompt.session_db import SessionDatabase


class TestVectorEmbedderInit:
    """Test VectorEmbedder initialization."""

    def test_init_default_model(self):
        """Test initialization with default model."""
        embedder = VectorEmbedder()
        assert embedder.model == "nomic-embed-text"

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        embedder = VectorEmbedder(model="custom-embed")
        assert embedder.model == "custom-embed"

    def test_init_with_cache(self):
        """Test initialization with existing cache."""
        cache = {"key1": [0.1, 0.2, 0.3]}
        embedder = VectorEmbedder(cache=cache)
        assert len(embedder.cache) == 1

    def test_init_custom_host(self):
        """Test initialization with custom Ollama host."""
        embedder = VectorEmbedder(ollama_host="http://myhost:11434")
        assert embedder.ollama_host == "http://myhost:11434"


class TestCacheKey:
    """Test cache key generation."""

    def test_cache_key_deterministic(self):
        """Test that cache key is deterministic."""
        embedder = VectorEmbedder()
        key1 = embedder._get_cache_key("hello world")
        key2 = embedder._get_cache_key("hello world")
        assert key1 == key2

    def test_cache_key_unique(self):
        """Test that different text produces different keys."""
        embedder = VectorEmbedder()
        key1 = embedder._get_cache_key("hello")
        key2 = embedder._get_cache_key("world")
        assert key1 != key2

    def test_cache_key_includes_model(self):
        """Test that cache key depends on model."""
        embedder1 = VectorEmbedder(model="model1")
        embedder2 = VectorEmbedder(model="model2")
        key1 = embedder1._get_cache_key("hello")
        key2 = embedder2._get_cache_key("hello")
        assert key1 != key2


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_vectors(self):
        """Test similarity of identical vectors."""
        vec = [1.0, 2.0, 3.0]
        sim = VectorEmbedder.cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 0.0001

    def test_opposite_vectors(self):
        """Test similarity of opposite vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        sim = VectorEmbedder.cosine_similarity(vec1, vec2)
        assert abs(sim - (-1.0)) < 0.0001

    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        sim = VectorEmbedder.cosine_similarity(vec1, vec2)
        assert abs(sim) < 0.0001

    def test_zero_vector_protection(self):
        """Test protection against zero-norm vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        sim = VectorEmbedder.cosine_similarity(vec1, vec2)
        assert sim == 0.0

    def test_none_vector_protection(self):
        """Test protection against None vectors."""
        vec = [1.0, 2.0, 3.0]
        assert VectorEmbedder.cosine_similarity(None, vec) == 0.0
        assert VectorEmbedder.cosine_similarity(vec, None) == 0.0
        assert VectorEmbedder.cosine_similarity(None, None) == 0.0

    def test_empty_vector_protection(self):
        """Test protection against empty vectors."""
        vec = [1.0, 2.0, 3.0]
        assert VectorEmbedder.cosine_similarity([], vec) == 0.0
        assert VectorEmbedder.cosine_similarity(vec, []) == 0.0

    def test_different_length_vectors(self):
        """Test handling of different length vectors."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        sim = VectorEmbedder.cosine_similarity(vec1, vec2)
        assert sim == 0.0


class TestEmbedding:
    """Test embedding generation."""

    def test_embed_empty_text(self):
        """Test embedding empty text returns None."""
        embedder = VectorEmbedder()
        result = embedder.embed("")
        assert result is None

    def test_embed_whitespace_text(self):
        """Test embedding whitespace-only text returns None."""
        embedder = VectorEmbedder()
        result = embedder.embed("   ")
        assert result is None

    def test_embed_uses_cache(self):
        """Test that embed uses cache."""
        embedder = VectorEmbedder()
        cache_key = embedder._get_cache_key("test text")
        embedder.cache[cache_key] = [0.1, 0.2, 0.3]

        result = embedder.embed("test text", use_cache=True)
        assert result == [0.1, 0.2, 0.3]

    def test_embed_updates_cache(self):
        """Test that successful embed updates cache."""
        embedder = VectorEmbedder()

        # Mock the API call
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3]
        }).encode('utf-8')
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = embedder.embed("test text", use_cache=True)

        assert result == [0.1, 0.2, 0.3]
        cache_key = embedder._get_cache_key("test text")
        assert cache_key in embedder.cache


class TestBatchEmbed:
    """Test batch embedding."""

    def test_batch_embed_empty_list(self):
        """Test batch embed with empty list."""
        embedder = VectorEmbedder()
        result = embedder.batch_embed([])
        assert result == []

    def test_batch_embed_uses_cache(self):
        """Test batch embed uses cache for known texts."""
        embedder = VectorEmbedder()

        # Pre-populate cache
        key1 = embedder._get_cache_key("text1")
        key2 = embedder._get_cache_key("text2")
        embedder.cache[key1] = [0.1, 0.2]
        embedder.cache[key2] = [0.3, 0.4]

        result = embedder.batch_embed(["text1", "text2"], use_cache=True)
        assert result == [[0.1, 0.2], [0.3, 0.4]]


class TestScoreRelevance:
    """Test relevance scoring."""

    def test_score_relevance_range(self):
        """Test that score_relevance returns value in [0, 1]."""
        embedder = VectorEmbedder()

        # Pre-populate cache with test embeddings
        key1 = embedder._get_cache_key("hello world")
        key2 = embedder._get_cache_key("goodbye moon")
        embedder.cache[key1] = [1.0, 0.0, 0.0]
        embedder.cache[key2] = [-1.0, 0.0, 0.0]  # Opposite direction

        score = embedder.score_relevance("hello world", "goodbye moon")
        assert 0.0 <= score <= 1.0

    def test_score_relevance_identical_text(self):
        """Test scoring identical texts."""
        embedder = VectorEmbedder()

        key = embedder._get_cache_key("same text")
        embedder.cache[key] = [1.0, 0.0, 0.0]

        score = embedder.score_relevance("same text", "same text")
        assert score == 1.0  # (1 + 1) / 2 = 1.0


class TestScoreRelevanceBatch:
    """Test batch relevance scoring."""

    def test_batch_scoring(self):
        """Test batch scoring multiple texts."""
        embedder = VectorEmbedder()

        # Pre-populate cache
        embedder.cache[embedder._get_cache_key("context")] = [1.0, 0.0]
        embedder.cache[embedder._get_cache_key("text1")] = [1.0, 0.0]  # Same as context
        embedder.cache[embedder._get_cache_key("text2")] = [0.0, 1.0]  # Orthogonal

        scores = embedder.score_relevance_batch(["text1", "text2"], "context")

        assert len(scores) == 2
        assert scores[0] > scores[1]  # text1 more similar to context


class TestCacheManagement:
    """Test cache management methods."""

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        embedder = VectorEmbedder()
        embedder.cache["key1"] = [0.1]
        embedder.cache["key2"] = [0.2]

        stats = embedder.get_cache_stats()
        assert stats["model"] == "nomic-embed-text"
        assert stats["cache_size"] == 2

    def test_clear_cache(self):
        """Test clearing the cache."""
        embedder = VectorEmbedder()
        embedder.cache["key1"] = [0.1]
        embedder.cache["key2"] = [0.2]

        embedder.clear_cache()
        assert len(embedder.cache) == 0


class TestEmbeddingStore:
    """Test database embedding storage."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session and message."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_save_and_get_embedding(self, db):
        """Test saving and retrieving embedding."""
        # First create a message
        msg_id = db.save_message("test-session", "user", "test content", 10)

        store = EmbeddingStore(db)
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Save embedding
        emb_id = store.save_embedding(msg_id, "nomic-embed-text", embedding)
        assert emb_id > 0

        # Retrieve embedding
        result = store.get_embedding(msg_id)
        assert result == embedding

    def test_get_embedding_with_model_filter(self, db):
        """Test retrieving embedding with model filter."""
        msg_id = db.save_message("test-session", "user", "test", 10)
        store = EmbeddingStore(db)

        # Save embeddings from different models
        store.save_embedding(msg_id, "model1", [0.1, 0.2])
        store.save_embedding(msg_id, "model2", [0.3, 0.4])

        # Get specific model
        result = store.get_embedding(msg_id, model="model1")
        assert result == [0.1, 0.2]

    def test_get_embedding_not_found(self, db):
        """Test getting embedding that doesn't exist."""
        store = EmbeddingStore(db)
        result = store.get_embedding(99999)
        assert result is None

    def test_has_embedding(self, db):
        """Test checking if embedding exists."""
        msg_id = db.save_message("test-session", "user", "test", 10)
        store = EmbeddingStore(db)

        assert store.has_embedding(msg_id) is False

        store.save_embedding(msg_id, "nomic", [0.1])
        assert store.has_embedding(msg_id) is True

    def test_delete_embedding(self, db):
        """Test deleting embedding."""
        msg_id = db.save_message("test-session", "user", "test", 10)
        store = EmbeddingStore(db)

        store.save_embedding(msg_id, "nomic", [0.1])
        assert store.has_embedding(msg_id) is True

        store.delete_embedding(msg_id)
        assert store.has_embedding(msg_id) is False

    def test_get_embedding_count(self, db):
        """Test counting embeddings."""
        store = EmbeddingStore(db)
        assert store.get_embedding_count() == 0

        msg1 = db.save_message("test-session", "user", "test1", 10)
        msg2 = db.save_message("test-session", "user", "test2", 10)

        store.save_embedding(msg1, "nomic", [0.1])
        store.save_embedding(msg2, "nomic", [0.2])

        assert store.get_embedding_count() == 2

    def test_embedding_cascade_delete(self, db):
        """Test that embeddings are deleted when message is deleted."""
        msg_id = db.save_message("test-session", "user", "test", 10)
        store = EmbeddingStore(db)

        store.save_embedding(msg_id, "nomic", [0.1, 0.2])
        assert store.has_embedding(msg_id) is True

        # Delete the message
        db.delete_messages([msg_id])

        # Embedding should be gone too
        assert store.has_embedding(msg_id) is False


class TestContextManagerVectorIntegration:
    """Test ContextManager integration with vector scoring."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_vector_scoring_disabled(self, db):
        """Test that vector scoring can be disabled."""
        from ollama_prompt.context_manager import ContextManager

        manager = ContextManager(
            db, "test-session",
            max_tokens=10000,
            use_vector_scoring=False
        )

        # Should not have embedder
        assert manager._get_vector_embedder() is None

    def test_vector_scoring_fallback(self, db):
        """Test fallback to keyword scoring when vectors unavailable."""
        from ollama_prompt.context_manager import ContextManager

        # Create mock embedder that is unavailable
        mock_embedder = MagicMock()
        mock_embedder.is_available.return_value = False

        manager = ContextManager(
            db, "test-session",
            max_tokens=10000,
            vector_embedder=mock_embedder,
            use_vector_scoring=True
        )

        # Should fall back to keyword scoring
        msg = {"content": "python code function", "role": "user"}
        context = "python code"

        # This should work without errors (uses keyword fallback)
        score = manager._calculate_relevance(msg, context)
        assert 0.0 <= score <= 1.0

    def test_keyword_relevance_calculation(self, db):
        """Test keyword-based relevance calculation."""
        from ollama_prompt.context_manager import ContextManager

        manager = ContextManager(
            db, "test-session",
            max_tokens=10000,
            use_vector_scoring=False
        )

        # High overlap
        msg_high = {"content": "python code function variable", "role": "user"}
        context = "python code function"
        score_high = manager._calculate_keyword_relevance(msg_high, context)

        # Low overlap
        msg_low = {"content": "apple banana cherry", "role": "user"}
        score_low = manager._calculate_keyword_relevance(msg_low, context)

        assert score_high > score_low

    def test_relevance_boosts(self, db):
        """Test relevance boost application."""
        from ollama_prompt.context_manager import ContextManager

        manager = ContextManager(
            db, "test-session",
            max_tokens=10000,
            use_vector_scoring=False
        )

        base_score = 0.5

        # Test code block boost
        msg_with_code = {"content": "```python\ncode\n```", "role": "user"}
        boosted = manager._apply_relevance_boosts(msg_with_code, base_score)
        assert boosted > base_score

        # Test assistant boost
        msg_assistant = {"content": "response", "role": "assistant"}
        boosted_assistant = manager._apply_relevance_boosts(msg_assistant, base_score)
        assert boosted_assistant > base_score

        # Test file ref boost
        msg_file_ref = {"content": "look at @./file.py", "role": "user"}
        boosted_file = manager._apply_relevance_boosts(msg_file_ref, base_score)
        assert boosted_file > base_score
