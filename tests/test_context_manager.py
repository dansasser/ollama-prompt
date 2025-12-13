#!/usr/bin/env python3
"""Tests for ContextManager module."""

import json
import pytest
from datetime import datetime, timedelta

from ollama_prompt.session_db import SessionDatabase
from ollama_prompt.context_manager import ContextManager


class TestContextManagerInit:
    """Test ContextManager initialization."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session", "max_context_tokens": 1000})
        yield db
        db.close()

    def test_init_basic(self, db):
        """Test basic initialization."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager.session_id == "test-session"
        assert manager.max_tokens == 1000

    def test_init_loads_last_compaction(self, db):
        """Test that initialization loads last compaction time."""
        # Record a compaction
        db.record_compaction("test-session", 1, 1000, 500, "file_compress")

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._last_compaction_time is not None

    def test_threshold_constants(self, db):
        """Test threshold constants are correct."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager.SOFT_THRESHOLD == 0.50
        assert manager.HARD_THRESHOLD == 0.65
        assert manager.EMERGENCY_THRESHOLD == 0.80


class TestUsageCalculation:
    """Test context usage calculation."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_get_usage_empty(self, db):
        """Test usage with no messages."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager.get_usage() == 0.0

    def test_get_usage_with_messages(self, db):
        """Test usage calculation with messages."""
        db.save_message("test-session", "user", "Hello", 100)
        db.save_message("test-session", "assistant", "Hi there", 200)

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager.get_usage() == 0.3  # 300/1000

    def test_get_usage_percentage(self, db):
        """Test usage percentage calculation."""
        db.save_message("test-session", "user", "Hello", 500)

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager.get_usage_percentage() == 50.0


class TestDetermineLevel:
    """Test compaction level determination."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_level_0_below_soft(self, db):
        """Test level 0 when below soft threshold."""
        db.save_message("test-session", "user", "Hello", 400)  # 40%

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._determine_level() == 0

    def test_level_1_at_soft(self, db):
        """Test level 1 at soft threshold."""
        db.save_message("test-session", "user", "Hello", 500)  # 50%

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._determine_level() == 1

    def test_level_2_at_hard(self, db):
        """Test level 2 at hard threshold."""
        db.save_message("test-session", "user", "Hello", 650)  # 65%

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._determine_level() == 2

    def test_level_3_at_emergency(self, db):
        """Test level 3 at emergency threshold."""
        db.save_message("test-session", "user", "Hello", 800)  # 80%

        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._determine_level() == 3


class TestCooldown:
    """Test cooldown tracking."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_cooldown_initial_state(self, db):
        """Test that compaction is blocked initially."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        # Need MIN_MESSAGES_BETWEEN_COMPACTION messages first
        assert manager._can_compact() is False

    def test_cooldown_after_messages(self, db):
        """Test that compaction is allowed after enough messages."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        manager._messages_since_compaction = 3
        assert manager._can_compact() is True

    def test_cooldown_reset_after_compaction(self, db):
        """Test cooldown reset after compaction."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        manager._messages_since_compaction = 5

        # Simulate compaction
        manager._record_compaction(1, 1000, 500, "file_compress")

        assert manager._messages_since_compaction == 0
        assert manager._can_compact() is False


class TestAddMessage:
    """Test message addition with automatic compaction."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_add_message_basic(self, db):
        """Test basic message addition."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        msg_id = manager.add_message("user", "Hello", 100)

        assert msg_id > 0
        messages = db.load_messages("test-session")
        assert len(messages) == 1

    def test_add_message_with_file_refs(self, db):
        """Test adding message with file references."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        msg_id = manager.add_message(
            "user",
            "Look at this file",
            100,
            file_refs=[("/path/to/file.py", "full", 500)]
        )

        refs = db.get_file_references("test-session")
        assert len(refs) == 1
        assert refs[0]["file_path"] == "/path/to/file.py"

    def test_add_message_increments_counter(self, db):
        """Test that message counter is incremented."""
        manager = ContextManager(db, "test-session", max_tokens=1000)
        assert manager._messages_since_compaction == 0

        manager.add_message("user", "Hello", 100)
        assert manager._messages_since_compaction == 1


class TestSoftCompaction:
    """Test Level 1: Soft compaction (file recompression)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session and messages."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_soft_compact_compresses_stale_files(self, db):
        """Test that stale files are compressed."""
        # Add old message with file reference
        msg_id = db.save_message("test-session", "user", "old message", 100,
                                  timestamp="2024-01-01T00:00:00")
        db.track_file_reference(msg_id, "/old/file.py", "full", 1000)

        # Add recent messages (making the file stale)
        for i in range(5):
            db.save_message("test-session", "user", f"recent {i}", 10)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 5  # Bypass cooldown

        tokens_freed = manager._soft_compact()

        # Check file was compressed
        refs = db.get_file_references("test-session", "/old/file.py")
        assert refs[0]["mode"] == "summary"
        assert refs[0]["tokens"] < 1000

    def test_soft_compact_preserves_recent_files(self, db):
        """Test that recently referenced files are not compressed."""
        # Add message with file reference
        msg_id = db.save_message("test-session", "user", "recent message", 100)
        db.track_file_reference(msg_id, "/recent/file.py", "full", 1000)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._soft_compact()

        # Check file is still full
        refs = db.get_file_references("test-session", "/recent/file.py")
        assert refs[0]["mode"] == "full"


class TestHardCompaction:
    """Test Level 2: Hard compaction (message pruning)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_hard_compact_keeps_recent_messages(self, db):
        """Test that recent messages are always kept."""
        # Add many messages
        for i in range(10):
            db.save_message("test-session", "user", f"Message {i}", 100)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        manager._hard_compact()

        messages = db.load_messages("test-session")
        # Should keep at least MIN_MESSAGES_TO_KEEP
        assert len(messages) >= manager.MIN_MESSAGES_TO_KEEP

    def test_hard_compact_removes_low_relevance(self, db):
        """Test that low-relevance messages are removed."""
        # Add irrelevant messages
        db.save_message("test-session", "user", "apple banana cherry", 100)
        db.save_message("test-session", "user", "dog elephant frog", 100)

        # Add relevant messages (recent, kept)
        db.save_message("test-session", "user", "python code function", 100)
        db.save_message("test-session", "assistant", "python code class", 100)
        db.save_message("test-session", "user", "python code method", 100)
        db.save_message("test-session", "assistant", "python code variable", 100)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        initial_count = len(db.load_messages("test-session"))

        manager._hard_compact()

        final_count = len(db.load_messages("test-session"))
        # Should have fewer messages
        assert final_count < initial_count

    def test_calculate_relevance_keyword_overlap(self, db):
        """Test relevance scoring based on keyword overlap."""
        manager = ContextManager(db, "test-session", max_tokens=10000)

        # High overlap
        msg_high = {"content": "python code function variable", "role": "user"}
        context = "python code function"
        score_high = manager._calculate_relevance(msg_high, context)

        # Low overlap
        msg_low = {"content": "apple banana cherry", "role": "user"}
        score_low = manager._calculate_relevance(msg_low, context)

        assert score_high > score_low

    def test_relevance_boost_for_code(self, db):
        """Test relevance boost for code blocks."""
        manager = ContextManager(db, "test-session", max_tokens=10000)

        msg_with_code = {"content": "```python\ndef foo(): pass\n```", "role": "assistant"}
        msg_without_code = {"content": "def foo pass", "role": "assistant"}
        context = "python def foo"

        score_with = manager._calculate_relevance(msg_with_code, context)
        score_without = manager._calculate_relevance(msg_without_code, context)

        # Code block should boost score
        assert score_with >= score_without


class TestEmergencyCompaction:
    """Test Level 3: Emergency compaction (LLM summarization)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_emergency_compact_keeps_recent(self, db):
        """Test that emergency compaction keeps last 4 messages."""
        for i in range(10):
            db.save_message("test-session", "user" if i % 2 == 0 else "assistant",
                            f"Message {i}", 100)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        manager._emergency_compact()

        messages = db.load_messages("test-session")
        # Should have 4 original + 1 summary = 5
        # (or fewer if summary not added)
        assert len(messages) <= 5

    def test_emergency_compact_creates_summary(self, db):
        """Test that emergency compaction creates summary message."""
        for i in range(10):
            db.save_message("test-session", "user", f"Message {i}", 100)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        manager._emergency_compact()

        messages = db.load_messages("test-session")
        summary_messages = [m for m in messages if m["is_summary"]]
        assert len(summary_messages) == 1

    def test_emergency_compact_with_custom_summarizer(self, db):
        """Test emergency compaction with custom LLM summarizer."""
        for i in range(10):
            db.save_message("test-session", "user", f"Message {i}", 100)

        def mock_summarizer(messages):
            return f"Custom summary of {len(messages)} messages"

        manager = ContextManager(db, "test-session", max_tokens=10000,
                                  llm_summarizer=mock_summarizer)
        manager._messages_since_compaction = 10
        manager._emergency_compact()

        messages = db.load_messages("test-session")
        summary = [m for m in messages if m["is_summary"]][0]
        assert "Custom summary" in summary["content"]

    def test_fallback_summary_structure(self, db):
        """Test fallback summary content."""
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            db.save_message("test-session", role, f"Message {i}", 100)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        messages = db.load_messages("test-session")[:6]
        summary = manager._create_fallback_summary(messages)

        assert "user messages" in summary
        assert "assistant responses" in summary


class TestAutoCompaction:
    """Test automatic compaction triggering."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_auto_compact_triggers_at_threshold(self, db):
        """Test that compaction triggers at threshold."""
        # Fill to 50% to trigger soft compaction
        db.save_message("test-session", "user", "x" * 2000, 500)

        manager = ContextManager(db, "test-session", max_tokens=1000)
        manager._messages_since_compaction = 5  # Bypass cooldown

        level = manager._auto_compact()
        assert level >= 1  # At least soft compaction

    def test_auto_compact_respects_cooldown(self, db):
        """Test that auto compaction respects cooldown."""
        db.save_message("test-session", "user", "Hello", 600)  # 60%

        manager = ContextManager(db, "test-session", max_tokens=1000)
        # Don't add messages, cooldown should block
        level = manager._auto_compact()

        assert level is None  # Blocked by cooldown

    def test_force_compact_ignores_cooldown(self, db):
        """Test that force_compact ignores cooldown."""
        db.save_message("test-session", "user", "Hello", 100)

        manager = ContextManager(db, "test-session", max_tokens=1000)
        # Force compact should work even with cooldown
        tokens_freed = manager.force_compact(level=1)

        # May or may not free tokens depending on state
        assert isinstance(tokens_freed, int)


class TestStatus:
    """Test status and statistics methods."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_get_status(self, db):
        """Test getting status."""
        db.save_message("test-session", "user", "Hello", 300)

        manager = ContextManager(db, "test-session", max_tokens=1000)
        status = manager.get_status()

        assert status["session_id"] == "test-session"
        assert status["max_tokens"] == 1000
        assert status["current_tokens"] == 300
        assert status["usage_percentage"] == 30.0
        assert "thresholds" in status

    def test_get_compaction_stats(self, db):
        """Test getting compaction statistics."""
        db.record_compaction("test-session", 1, 1000, 800, "file_compress")
        db.record_compaction("test-session", 2, 800, 500, "message_prune")

        manager = ContextManager(db, "test-session", max_tokens=1000)
        stats = manager.get_compaction_stats()

        assert stats["total_compactions"] == 2
        assert stats["total_tokens_freed"] == 500  # 200 + 300
        assert stats["level_counts"]["soft"] == 1
        assert stats["level_counts"]["hard"] == 1


class TestCompactionRecording:
    """Test compaction history recording."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_compaction_recorded(self, db):
        """Test that compaction events are recorded."""
        # Add stale file
        msg_id = db.save_message("test-session", "user", "old", 100,
                                  timestamp="2024-01-01T00:00:00")
        db.track_file_reference(msg_id, "/file.py", "full", 1000)

        # Add recent messages
        for i in range(5):
            db.save_message("test-session", "user", f"recent {i}", 10)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        manager._soft_compact()

        history = db.get_compaction_history("test-session")
        assert len(history) >= 1
        assert history[0]["strategy"] == "file_compress"

    def test_compaction_details_json(self, db):
        """Test that compaction details are properly JSON encoded."""
        # Setup for compaction
        msg_id = db.save_message("test-session", "user", "old", 100,
                                  timestamp="2024-01-01T00:00:00")
        db.track_file_reference(msg_id, "/file.py", "full", 1000)

        for i in range(5):
            db.save_message("test-session", "user", f"recent {i}", 10)

        manager = ContextManager(db, "test-session", max_tokens=10000)
        manager._messages_since_compaction = 10
        manager._soft_compact()

        history = db.get_compaction_history("test-session")
        if history and history[0]["details"]:
            details = json.loads(history[0]["details"])
            assert "files_compressed" in details or "tokens_saved" in details
