#!/usr/bin/env python3
"""Tests for SessionDatabase V2 schema (context management features)."""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ollama_prompt.session_db import SessionDatabase, SCHEMA_VERSION


class TestSchemaVersion:
    """Test schema versioning functionality."""

    def test_new_database_has_current_version(self, tmp_path):
        """Test that new databases are created at current schema version."""
        db_path = str(tmp_path / "new.db")
        db = SessionDatabase(db_path)

        with db._get_connection() as conn:
            version = db._get_schema_version(conn)

        assert version == SCHEMA_VERSION
        db.close()

    def test_get_schema_version_v1_database(self, tmp_path):
        """Test version detection for V1 (no version table) database."""
        db_path = str(tmp_path / "v1.db")

        # Create V1 schema manually (without version table)
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                context TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                max_context_tokens INTEGER DEFAULT 64000,
                history_json TEXT,
                metadata_json TEXT,
                model_name TEXT,
                system_prompt TEXT
            );
        """)
        conn.commit()
        conn.close()

        # Now open with SessionDatabase - should detect V1 and migrate
        db = SessionDatabase(db_path)

        with db._get_connection() as conn:
            version = db._get_schema_version(conn)

        # After migration, should be at current version
        assert version == SCHEMA_VERSION
        db.close()

    def test_schema_version_persisted(self, tmp_path):
        """Test that schema version is persisted across reopens."""
        db_path = str(tmp_path / "test.db")

        db = SessionDatabase(db_path)
        db.close()

        # Reopen
        db2 = SessionDatabase(db_path)
        with db2._get_connection() as conn:
            version = db2._get_schema_version(conn)

        assert version == SCHEMA_VERSION
        db2.close()


class TestV2Tables:
    """Test that V2 tables are created correctly."""

    def test_messages_table_exists(self, tmp_path):
        """Test that messages table is created."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='messages'
            """)
            result = cursor.fetchone()

        assert result is not None
        db.close()

    def test_file_references_table_exists(self, tmp_path):
        """Test that file_references table is created."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='file_references'
            """)
            result = cursor.fetchone()

        assert result is not None
        db.close()

    def test_compaction_history_table_exists(self, tmp_path):
        """Test that compaction_history table is created."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='compaction_history'
            """)
            result = cursor.fetchone()

        assert result is not None
        db.close()


class TestMigration:
    """Test V1 to V2 migration."""

    def test_migration_creates_backup(self, tmp_path):
        """Test that migration creates backup file."""
        db_path = str(tmp_path / "migrate.db")

        # Create V1 database
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                context TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                max_context_tokens INTEGER DEFAULT 64000,
                history_json TEXT,
                metadata_json TEXT,
                model_name TEXT,
                system_prompt TEXT
            );
        """)
        conn.commit()
        conn.close()

        # Migrate by opening with SessionDatabase
        db = SessionDatabase(db_path)
        db.close()

        # Check backup was created
        backup_files = list(tmp_path.glob("*.backup.*"))
        assert len(backup_files) >= 1

    def test_migration_preserves_history_json(self, tmp_path):
        """Test that history_json is migrated to messages table."""
        db_path = str(tmp_path / "migrate.db")

        # Create V1 database with history
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                context TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                max_context_tokens INTEGER DEFAULT 64000,
                history_json TEXT,
                metadata_json TEXT,
                model_name TEXT,
                system_prompt TEXT
            );
        """)

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        conn.execute(
            "INSERT INTO sessions (session_id, history_json) VALUES (?, ?)",
            ("test-session", json.dumps(history))
        )
        conn.commit()
        conn.close()

        # Migrate
        db = SessionDatabase(db_path)

        # Check messages were migrated
        messages = db.load_messages("test-session")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"

        db.close()


class TestMessageAPI:
    """Test message management API."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        # Create a session for testing
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_save_message(self, db):
        """Test saving a message."""
        msg_id = db.save_message(
            session_id="test-session",
            role="user",
            content="Hello world",
            tokens=50
        )
        assert msg_id > 0

    def test_load_messages(self, db):
        """Test loading messages."""
        db.save_message("test-session", "user", "First message", 10)
        db.save_message("test-session", "assistant", "Second message", 20)

        messages = db.load_messages("test-session")
        assert len(messages) == 2
        assert messages[0]["content"] == "First message"
        assert messages[1]["content"] == "Second message"

    def test_load_messages_with_limit(self, db):
        """Test loading messages with limit."""
        for i in range(10):
            db.save_message("test-session", "user", f"Message {i}", 10)

        messages = db.load_messages("test-session", limit=3)
        assert len(messages) == 3
        # Should be newest 3, but ordered by timestamp ASC
        assert "Message 7" in messages[0]["content"]

    def test_load_messages_exclude_summaries(self, db):
        """Test excluding summary messages."""
        db.save_message("test-session", "user", "Regular message", 10)
        db.save_message("test-session", "system", "Summary message", 50, is_summary=True)

        messages = db.load_messages("test-session", include_summaries=False)
        assert len(messages) == 1
        assert messages[0]["content"] == "Regular message"

    def test_get_message_tokens(self, db):
        """Test getting total token count."""
        db.save_message("test-session", "user", "First", 100)
        db.save_message("test-session", "assistant", "Second", 200)

        total = db.get_message_tokens("test-session")
        assert total == 300

    def test_delete_messages(self, db):
        """Test deleting specific messages."""
        id1 = db.save_message("test-session", "user", "Keep this", 10)
        id2 = db.save_message("test-session", "user", "Delete this", 10)
        id3 = db.save_message("test-session", "user", "Delete this too", 10)

        deleted = db.delete_messages([id2, id3])
        assert deleted == 2

        messages = db.load_messages("test-session")
        assert len(messages) == 1
        assert messages[0]["id"] == id1

    def test_delete_messages_before_timestamp(self, db):
        """Test deleting messages before timestamp."""
        # Create messages with specific timestamps
        db.save_message("test-session", "user", "Old message",
                        10, timestamp="2024-01-01T00:00:00")
        db.save_message("test-session", "user", "New message",
                        10, timestamp="2024-06-01T00:00:00")

        deleted = db.delete_messages_before("test-session", "2024-03-01T00:00:00")
        assert deleted == 1

        messages = db.load_messages("test-session")
        assert len(messages) == 1
        assert messages[0]["content"] == "New message"

    def test_delete_messages_keep_count(self, db):
        """Test keeping N newest messages during delete."""
        for i in range(5):
            db.save_message("test-session", "user", f"Message {i}", 10)

        # Delete all but keep 2 newest
        deleted = db.delete_messages_before(
            "test-session",
            datetime.now().isoformat(),
            keep_count=2
        )
        assert deleted == 3

        messages = db.load_messages("test-session")
        assert len(messages) == 2


class TestFileReferenceAPI:
    """Test file reference tracking API."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session and message."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_track_file_reference(self, db):
        """Test tracking a file reference."""
        msg_id = db.save_message("test-session", "user", "content", 10)
        ref_id = db.track_file_reference(msg_id, "/path/to/file.py", "full", 500)
        assert ref_id > 0

    def test_get_file_references(self, db):
        """Test getting file references."""
        msg_id = db.save_message("test-session", "user", "content", 10)
        db.track_file_reference(msg_id, "/path/to/file.py", "full", 500)
        db.track_file_reference(msg_id, "/path/to/other.py", "summary", 100)

        refs = db.get_file_references("test-session")
        assert len(refs) == 2

    def test_get_file_references_by_path(self, db):
        """Test filtering file references by path."""
        msg_id = db.save_message("test-session", "user", "content", 10)
        db.track_file_reference(msg_id, "/path/to/file.py", "full", 500)
        db.track_file_reference(msg_id, "/path/to/other.py", "summary", 100)

        refs = db.get_file_references("test-session", file_path="/path/to/file.py")
        assert len(refs) == 1
        assert refs[0]["file_path"] == "/path/to/file.py"

    def test_get_stale_files(self, db):
        """Test finding stale files."""
        # Old message with file reference
        msg1 = db.save_message("test-session", "user", "old", 10,
                               timestamp="2024-01-01T00:00:00")
        db.track_file_reference(msg1, "/old/file.py", "full", 500)

        # Recent messages without file references
        for i in range(5):
            db.save_message("test-session", "user", f"recent {i}", 10)

        stale = db.get_stale_files("test-session", stale_threshold=3)
        assert len(stale) == 1
        assert stale[0]["file_path"] == "/old/file.py"

    def test_get_stale_files_mode_filter(self, db):
        """Test filtering stale files by mode."""
        msg1 = db.save_message("test-session", "user", "old", 10,
                               timestamp="2024-01-01T00:00:00")
        db.track_file_reference(msg1, "/file1.py", "full", 500)
        db.track_file_reference(msg1, "/file2.py", "summary", 100)

        # Add recent messages
        for i in range(3):
            db.save_message("test-session", "user", f"recent {i}", 10)

        stale = db.get_stale_files("test-session", stale_threshold=2, mode_filter="full")
        assert len(stale) == 1
        assert stale[0]["file_path"] == "/file1.py"

    def test_update_file_reference_mode(self, db):
        """Test updating file reference mode."""
        msg_id = db.save_message("test-session", "user", "content", 10)
        ref_id = db.track_file_reference(msg_id, "/file.py", "full", 500)

        db.update_file_reference_mode(ref_id, "summary", 50)

        refs = db.get_file_references("test-session")
        assert refs[0]["mode"] == "summary"
        assert refs[0]["tokens"] == 50


class TestCompactionAPI:
    """Test compaction history API."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database with session."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        db.create_session({"session_id": "test-session"})
        yield db
        db.close()

    def test_record_compaction(self, db):
        """Test recording a compaction event."""
        comp_id = db.record_compaction(
            session_id="test-session",
            level=1,
            tokens_before=10000,
            tokens_after=5000,
            strategy="file_compress"
        )
        assert comp_id > 0

    def test_record_compaction_calculates_freed(self, db):
        """Test that tokens_freed is calculated correctly."""
        db.record_compaction(
            session_id="test-session",
            level=1,
            tokens_before=10000,
            tokens_after=5000,
            strategy="file_compress"
        )

        history = db.get_compaction_history("test-session")
        assert len(history) == 1
        assert history[0]["tokens_freed"] == 5000

    def test_get_compaction_history(self, db):
        """Test getting compaction history."""
        db.record_compaction("test-session", 1, 10000, 8000, "file_compress")
        db.record_compaction("test-session", 2, 8000, 5000, "message_prune")

        history = db.get_compaction_history("test-session")
        assert len(history) == 2
        # Should be newest first
        assert history[0]["level"] == 2
        assert history[1]["level"] == 1

    def test_get_compaction_history_with_limit(self, db):
        """Test limiting compaction history."""
        for i in range(5):
            db.record_compaction("test-session", 1, 10000, 9000, "file_compress")

        history = db.get_compaction_history("test-session", limit=2)
        assert len(history) == 2

    def test_get_total_tokens_freed(self, db):
        """Test getting total tokens freed."""
        db.record_compaction("test-session", 1, 10000, 8000, "file_compress")
        db.record_compaction("test-session", 2, 8000, 5000, "message_prune")

        total = db.get_total_tokens_freed("test-session")
        assert total == 5000  # 2000 + 3000

    def test_get_last_compaction(self, db):
        """Test getting most recent compaction."""
        db.record_compaction("test-session", 1, 10000, 8000, "file_compress")
        db.record_compaction("test-session", 2, 8000, 5000, "message_prune")

        last = db.get_last_compaction("test-session")
        assert last is not None
        assert last["level"] == 2
        assert last["strategy"] == "message_prune"

    def test_get_last_compaction_no_history(self, db):
        """Test getting last compaction when none exist."""
        last = db.get_last_compaction("test-session")
        assert last is None

    def test_compaction_with_details(self, db):
        """Test compaction with details JSON."""
        details = json.dumps({"files_compressed": 3, "messages_pruned": 10})
        db.record_compaction(
            session_id="test-session",
            level=2,
            tokens_before=10000,
            tokens_after=5000,
            strategy="message_prune",
            details=details
        )

        history = db.get_compaction_history("test-session")
        assert history[0]["details"] == details


class TestCascadeDelete:
    """Test CASCADE DELETE behavior."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        yield db
        db.close()

    def test_session_delete_cascades_messages(self, db):
        """Test that deleting session cascades to messages."""
        db.create_session({"session_id": "test-session"})
        db.save_message("test-session", "user", "Hello", 10)
        db.save_message("test-session", "assistant", "Hi", 10)

        db.delete_session("test-session")

        messages = db.load_messages("test-session")
        assert len(messages) == 0

    def test_session_delete_cascades_compaction(self, db):
        """Test that deleting session cascades to compaction history."""
        db.create_session({"session_id": "test-session"})
        db.record_compaction("test-session", 1, 1000, 500, "file_compress")

        db.delete_session("test-session")

        history = db.get_compaction_history("test-session")
        assert len(history) == 0

    def test_message_delete_cascades_file_refs(self, db):
        """Test that deleting message cascades to file references."""
        db.create_session({"session_id": "test-session"})
        msg_id = db.save_message("test-session", "user", "content", 10)
        db.track_file_reference(msg_id, "/file.py", "full", 100)

        db.delete_messages([msg_id])

        refs = db.get_file_references("test-session")
        assert len(refs) == 0


class TestBackwardsCompatibility:
    """Test that V1 API still works with V2 schema."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = str(tmp_path / "test.db")
        db = SessionDatabase(db_path)
        yield db
        db.close()

    def test_create_session_still_works(self, db):
        """Test V1 create_session API."""
        session_id = db.create_session({
            "session_id": "compat-test",
            "context": "test context",
            "max_context_tokens": 32000
        })
        assert session_id == "compat-test"

    def test_get_session_still_works(self, db):
        """Test V1 get_session API."""
        db.create_session({"session_id": "compat-test"})
        session = db.get_session("compat-test")
        assert session is not None
        assert session["session_id"] == "compat-test"

    def test_update_session_still_works(self, db):
        """Test V1 update_session API."""
        db.create_session({"session_id": "compat-test"})
        db.update_session("compat-test", {"context": "new context"})

        session = db.get_session("compat-test")
        assert session["context"] == "new context"

    def test_list_all_sessions_still_works(self, db):
        """Test V1 list_all_sessions API."""
        db.create_session({"session_id": "session1"})
        db.create_session({"session_id": "session2"})

        sessions = db.list_all_sessions()
        assert len(sessions) == 2

    def test_purge_sessions_still_works(self, db):
        """Test V1 purge_sessions API."""
        db.create_session({
            "session_id": "old-session",
            "last_used": "2020-01-01T00:00:00"
        })

        deleted = db.purge_sessions(days=30)
        assert deleted == 1
