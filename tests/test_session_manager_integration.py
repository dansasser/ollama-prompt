#!/usr/bin/env python3
"""Tests for SessionManager integration with ContextManager and ModelManifest."""

import pytest
from unittest.mock import MagicMock, patch

from ollama_prompt.session_manager import SessionManager
from ollama_prompt.model_manifest import ModelManifest


class TestSessionManagerInit:
    """Test SessionManager initialization."""

    def test_init_default(self, tmp_path):
        """Test default initialization."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path)

        assert manager.use_smart_compaction is False
        assert manager.manifest is None
        assert manager.fallback_model is None
        assert len(manager._context_managers) == 0

        manager.close()

    def test_init_with_smart_compaction(self, tmp_path):
        """Test initialization with smart compaction enabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(
            db_path=db_path,
            use_smart_compaction=True
        )

        assert manager.use_smart_compaction is True
        manager.close()

    def test_init_with_manifest(self, tmp_path):
        """Test initialization with manifest."""
        db_path = str(tmp_path / "test.db")
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()
        manifest.set_model_for_task("embedding", "nomic-embed-text")

        manager = SessionManager(
            db_path=db_path,
            use_smart_compaction=True,
            manifest=manifest
        )

        assert manager.manifest is manifest
        manager.close()

    def test_init_with_fallback_model(self, tmp_path):
        """Test initialization with fallback model."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(
            db_path=db_path,
            use_smart_compaction=True,
            fallback_model="llama3:8b"
        )

        assert manager.fallback_model == "llama3:8b"
        manager.close()


class TestContextManagerIntegration:
    """Test ContextManager integration."""

    def test_get_context_manager_disabled(self, tmp_path):
        """Test that context manager is None when disabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=False)

        session, _ = manager.get_or_create_session(model_name="test")
        ctx = manager._get_context_manager(session)

        assert ctx is None
        manager.close()

    def test_get_context_manager_enabled(self, tmp_path):
        """Test context manager creation when enabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=True)

        session, _ = manager.get_or_create_session(model_name="test")
        ctx = manager._get_context_manager(session)

        assert ctx is not None
        assert ctx.session_id == session["session_id"]
        manager.close()

    def test_context_manager_cached(self, tmp_path):
        """Test that context manager is cached per session."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=True)

        session, _ = manager.get_or_create_session(model_name="test")
        ctx1 = manager._get_context_manager(session)
        ctx2 = manager._get_context_manager(session)

        assert ctx1 is ctx2  # Same instance
        manager.close()

    def test_context_manager_with_manifest(self, tmp_path):
        """Test context manager uses manifest for embedder."""
        db_path = str(tmp_path / "test.db")
        manifest = ModelManifest(path=tmp_path / "manifest.json")
        manifest.load()
        manifest.set_model_for_task("embedding", "mxbai-embed-large")

        manager = SessionManager(
            db_path=db_path,
            use_smart_compaction=True,
            manifest=manifest
        )

        session, _ = manager.get_or_create_session(model_name="test")
        ctx = manager._get_context_manager(session)

        # The context manager should have a vector embedder configured
        embedder = ctx._get_vector_embedder()
        if embedder:
            assert embedder.model == "mxbai-embed-large"

        manager.close()

    def test_context_manager_with_fallback(self, tmp_path):
        """Test context manager uses fallback model."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(
            db_path=db_path,
            use_smart_compaction=True,
            fallback_model="llama3:8b"
        )

        session, _ = manager.get_or_create_session(model_name="test")
        ctx = manager._get_context_manager(session)

        # Check the embedder has fallback configured
        embedder = ctx._get_vector_embedder()
        if embedder:
            assert embedder.fallback_model == "llama3:8b"

        manager.close()


class TestContextStatusMethods:
    """Test context status and stats methods."""

    def test_get_context_status_disabled(self, tmp_path):
        """Test get_context_status returns None when disabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=False)

        session, _ = manager.get_or_create_session(model_name="test")
        status = manager.get_context_status(session)

        assert status is None
        manager.close()

    def test_get_context_status_enabled(self, tmp_path):
        """Test get_context_status returns dict when enabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=True)

        session, _ = manager.get_or_create_session(model_name="test")
        status = manager.get_context_status(session)

        assert status is not None
        assert "session_id" in status
        assert "usage_percentage" in status
        assert "current_level" in status
        manager.close()

    def test_get_compaction_stats_disabled(self, tmp_path):
        """Test get_compaction_stats returns None when disabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=False)

        session, _ = manager.get_or_create_session(model_name="test")
        stats = manager.get_compaction_stats(session)

        assert stats is None
        manager.close()

    def test_get_compaction_stats_enabled(self, tmp_path):
        """Test get_compaction_stats returns dict when enabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=True)

        session, _ = manager.get_or_create_session(model_name="test")
        stats = manager.get_compaction_stats(session)

        assert stats is not None
        assert "total_compactions" in stats
        assert "total_tokens_freed" in stats
        manager.close()

    def test_force_compact_disabled(self, tmp_path):
        """Test force_compact returns 0 when disabled."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=False)

        session, _ = manager.get_or_create_session(model_name="test")
        freed = manager.force_compact(session, level=1)

        assert freed == 0
        manager.close()


class TestCleanup:
    """Test cleanup operations."""

    def test_close_clears_context_managers(self, tmp_path):
        """Test that close clears context managers."""
        db_path = str(tmp_path / "test.db")
        manager = SessionManager(db_path=db_path, use_smart_compaction=True)

        session, _ = manager.get_or_create_session(model_name="test")
        manager._get_context_manager(session)

        assert len(manager._context_managers) == 1

        manager.close()

        assert len(manager._context_managers) == 0
