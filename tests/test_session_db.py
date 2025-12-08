"""
Unit tests for session database layer.

Tests SQLite database operations, CRUD functionality, and data integrity.
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from ollama_prompt.session_db import SessionDatabase, get_default_db_path
from ollama_prompt.models import SessionData


class TestDatabasePath:
    """Tests for database path resolution."""

    def test_get_default_db_path_returns_path(self):
        """Test that default path function returns a valid Path object."""
        path = get_default_db_path()
        assert isinstance(path, Path)
        assert path.name == 'sessions.db'

    def test_get_default_db_path_creates_parent_directory(self):
        """Test that parent directory is created if it doesn't exist."""
        path = get_default_db_path()
        assert path.parent.exists()

    def test_default_path_is_platform_appropriate(self):
        """Test that path is appropriate for current platform."""
        path = get_default_db_path()

        if os.name == 'nt':  # Windows
            assert 'AppData' in str(path) or str(Path.home()) in str(path)
        else:  # Unix/Linux/Mac
            assert '.config' in str(path) or str(Path.home()) in str(path)


class TestSessionDatabase:
    """Tests for SessionDatabase class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = SessionDatabase(db_path)
        yield db

        # Cleanup - close and delete database file
        db.close()

        # Retry delete with exponential backoff (Windows can have brief file locks)
        import time
        for attempt in range(6):
            try:
                if os.path.exists(db_path):
                    os.unlink(db_path)
                break
            except PermissionError:
                time.sleep(0.1 * (2**attempt))
            except FileNotFoundError:
                break  # Already deleted
        else:
            # If still locked after retries, log and move on (system cleanup will handle it)
            pass

    @pytest.fixture
    def sample_session(self):
        """Sample session data for testing."""
        return {
            'session_id': 'test-session-123',
            'context': 'User: Hello\nAssistant: Hi there!',
            'max_context_tokens': 64000,
            'model_name': 'deepseek-v3.1:671b-cloud'
        }

    def test_database_initialization(self, temp_db):
        """Test that database initializes with schema."""
        assert os.path.exists(temp_db.db_path)

        # Check that tables exist
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='sessions'
            """)
            assert cursor.fetchone() is not None

    def test_create_session(self, temp_db, sample_session):
        """Test creating a new session."""
        session_id = temp_db.create_session(sample_session)
        assert session_id == sample_session['session_id']

        # Verify session was created
        retrieved = temp_db.get_session(session_id)
        assert retrieved is not None
        assert retrieved['session_id'] == session_id
        assert retrieved['context'] == sample_session['context']

    def test_get_nonexistent_session(self, temp_db):
        """Test retrieving a session that doesn't exist."""
        result = temp_db.get_session('nonexistent-id')
        assert result is None

    def test_get_session(self, temp_db, sample_session):
        """Test retrieving an existing session."""
        session_id = temp_db.create_session(sample_session)
        retrieved = temp_db.get_session(session_id)

        assert retrieved is not None
        assert retrieved['session_id'] == session_id
        assert retrieved['context'] == sample_session['context']
        assert retrieved['max_context_tokens'] == sample_session['max_context_tokens']
        assert retrieved['model_name'] == sample_session['model_name']

    def test_update_session(self, temp_db, sample_session):
        """Test updating session fields."""
        session_id = temp_db.create_session(sample_session)

        new_context = 'User: Hello\nAssistant: Hi!\nUser: How are you?\nAssistant: Great!'
        temp_db.update_session(session_id, {
            'context': new_context,
            'last_used': datetime.now().isoformat()
        })

        retrieved = temp_db.get_session(session_id)
        assert retrieved['context'] == new_context

    def test_update_session_with_no_changes(self, temp_db, sample_session):
        """Test update with empty dict does nothing."""
        session_id = temp_db.create_session(sample_session)
        temp_db.update_session(session_id, {})  # Should not raise error

        retrieved = temp_db.get_session(session_id)
        assert retrieved is not None

    def test_delete_session(self, temp_db, sample_session):
        """Test deleting a session."""
        session_id = temp_db.create_session(sample_session)

        # Verify session exists
        assert temp_db.get_session(session_id) is not None

        # Delete session
        result = temp_db.delete_session(session_id)
        assert result is True

        # Verify session no longer exists
        assert temp_db.get_session(session_id) is None

    def test_delete_nonexistent_session(self, temp_db):
        """Test deleting a session that doesn't exist."""
        result = temp_db.delete_session('nonexistent-id')
        assert result is False

    def test_list_all_sessions(self, temp_db):
        """Test listing all sessions."""
        # Create multiple sessions
        sessions = [
            {'session_id': 'session-1', 'context': 'context 1'},
            {'session_id': 'session-2', 'context': 'context 2'},
            {'session_id': 'session-3', 'context': 'context 3'}
        ]

        for session in sessions:
            temp_db.create_session(session)

        # List all sessions
        all_sessions = temp_db.list_all_sessions()
        assert len(all_sessions) == 3

        # Check that sessions are ordered by last_used descending
        session_ids = [s['session_id'] for s in all_sessions]
        assert 'session-3' in session_ids
        assert 'session-2' in session_ids
        assert 'session-1' in session_ids

    def test_list_sessions_with_limit(self, temp_db):
        """Test listing sessions with limit."""
        # Create multiple sessions
        for i in range(5):
            temp_db.create_session({'session_id': f'session-{i}', 'context': ''})

        # List with limit
        limited = temp_db.list_all_sessions(limit=3)
        assert len(limited) == 3

    def test_purge_old_sessions(self, temp_db):
        """Test purging sessions older than specified days."""
        # Create sessions with different timestamps
        old_timestamp = (datetime.now() - timedelta(days=35)).isoformat()
        recent_timestamp = datetime.now().isoformat()

        temp_db.create_session({
            'session_id': 'old-session',
            'context': '',
            'last_used': old_timestamp
        })

        temp_db.create_session({
            'session_id': 'recent-session',
            'context': '',
            'last_used': recent_timestamp
        })

        # Purge sessions older than 30 days
        deleted_count = temp_db.purge_sessions(30)
        assert deleted_count == 1

        # Verify old session is gone, recent session remains
        assert temp_db.get_session('old-session') is None
        assert temp_db.get_session('recent-session') is not None

    def test_get_session_count(self, temp_db):
        """Test getting total session count."""
        assert temp_db.get_session_count() == 0

        # Create sessions
        temp_db.create_session({'session_id': 'session-1', 'context': ''})
        assert temp_db.get_session_count() == 1

        temp_db.create_session({'session_id': 'session-2', 'context': ''})
        assert temp_db.get_session_count() == 2

    def test_session_with_special_characters(self, temp_db):
        """Test session with special characters in context."""
        session = {
            'session_id': 'special-chars-session',
            'context': 'User: What\'s "quoted" text?\nAssistant: It uses \\n for newlines.'
        }

        temp_db.create_session(session)
        retrieved = temp_db.get_session(session['session_id'])

        assert retrieved['context'] == session['context']

    def test_environment_variable_override(self, monkeypatch):
        """Test that OLLAMA_PROMPT_DB_PATH environment variable overrides default."""
        # Use temp directory for cross-platform compatibility
        import tempfile
        temp_dir = tempfile.gettempdir()
        custom_path = os.path.join(temp_dir, 'custom_sessions.db')
        monkeypatch.setenv('OLLAMA_PROMPT_DB_PATH', custom_path)

        db = SessionDatabase()

        # Fix: Normalize both paths before asserting equality
        norm_db_path = os.path.normcase(os.path.abspath(db.db_path))
        norm_custom_path = os.path.normcase(os.path.abspath(custom_path))
        assert norm_db_path == norm_custom_path

        # Cleanup
        db.close()
        if os.path.exists(custom_path):
            try:
                os.unlink(custom_path)
            except PermissionError:
                pass  # Cleanup will happen later


class TestSessionData:
    """Tests for SessionData model."""

    def test_session_data_creation(self):
        """Test creating SessionData instance."""
        session = SessionData(
            session_id='test-123',
            context='Test context',
            max_context_tokens=32000
        )

        assert session.session_id == 'test-123'
        assert session.context == 'Test context'
        assert session.max_context_tokens == 32000

    def test_session_data_defaults(self):
        """Test SessionData default values."""
        session = SessionData(session_id='test-123')

        assert session.context == ''
        assert session.max_context_tokens == 64000
        assert session.created_at is not None
        assert session.last_used is not None

    def test_session_data_to_dict(self):
        """Test converting SessionData to dictionary."""
        session = SessionData(
            session_id='test-123',
            context='Test context'
        )

        data_dict = session.to_dict()

        assert data_dict['session_id'] == 'test-123'
        assert data_dict['context'] == 'Test context'
        assert 'created_at' in data_dict
        assert 'last_used' in data_dict

    def test_session_data_from_dict(self):
        """Test creating SessionData from dictionary."""
        data = {
            'session_id': 'test-123',
            'context': 'Test context',
            'max_context_tokens': 32000,
            'model_name': 'test-model'
        }

        session = SessionData.from_dict(data)

        assert session.session_id == 'test-123'
        assert session.context == 'Test context'
        assert session.max_context_tokens == 32000
        assert session.model_name == 'test-model'

    def test_update_last_used(self):
        """Test updating last_used timestamp."""
        session = SessionData(session_id='test-123')
        original_timestamp = session.last_used

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        session.update_last_used()
        assert session.last_used != original_timestamp

    def test_estimate_tokens(self):
        """Test token estimation."""
        session = SessionData(
            session_id='test-123',
            context='This is a test context with some words.'  # ~40 chars = ~10 tokens
        )

        tokens = session.estimate_tokens()
        assert tokens > 0
        assert tokens < 20  # Should be around 10

    def test_is_context_near_limit(self):
        """Test checking if context is near token limit."""
        # Create session with context near limit
        session = SessionData(
            session_id='test-123',
            context='x' * (64000 * 4),  # 64000 tokens worth of characters
            max_context_tokens=64000
        )

        assert session.is_context_near_limit(threshold=0.9) is True

        # Create session with small context
        session2 = SessionData(
            session_id='test-456',
            context='Small context',
            max_context_tokens=64000
        )

        assert session2.is_context_near_limit(threshold=0.9) is False
