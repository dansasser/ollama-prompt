"""
Database abstraction layer for session persistence.

Supports SQLite (default) and MongoDB (optional) backends.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json


def get_default_db_path() -> Path:
    """
    Get platform-appropriate database path for SQLite.

    Returns:
        Path: Database file path

    Platform-specific locations:
        - Windows: %APPDATA%\\ollama-prompt\\sessions.db
        - Unix/Linux/Mac: ~/.config/ollama-prompt/sessions.db
    """
    if os.name == 'nt':  # Windows
        base = Path(os.getenv('APPDATA', Path.home()))
    else:  # Unix/Linux/Mac
        base = Path.home() / '.config'

    db_dir = base / 'ollama-prompt'
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / 'sessions.db'


class SessionDatabase:
    """
    Database abstraction layer for session storage.

    Handles SQLite operations with proper connection management,
    schema creation, and CRUD operations for sessions.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sessions (
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

    CREATE INDEX IF NOT EXISTS idx_sessions_last_used
    ON sessions(last_used);

    CREATE INDEX IF NOT EXISTS idx_sessions_model
    ON sessions(model_name);
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Custom database path. If None, uses default platform path.
        """
        if db_path is None:
            # Check for environment variable override
            db_path = os.getenv('OLLAMA_PROMPT_DB_PATH')
            if db_path is None:
                db_path = str(get_default_db_path())

        self.db_path = db_path
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection with proper settings.

        Returns:
            sqlite3.Connection: Database connection with row factory
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def close(self):
        """Close database connections (for testing/cleanup)."""
        # SQLite connections are closed automatically when using context managers
        # This method exists for explicit cleanup if needed
        pass

    def _ensure_schema(self):
        """Create database schema if it doesn't exist."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def create_session(self, session_data: Dict[str, Any]) -> str:
        """
        Create a new session in the database.

        Args:
            session_data: Dictionary containing session fields:
                - session_id: Unique session identifier
                - context: Initial context (default: '')
                - max_context_tokens: Token limit (default: 64000)
                - created_at: Creation timestamp (default: now)
                - last_used: Last used timestamp (default: now)
                - model_name: Model name (optional)
                - system_prompt: System prompt (optional)

        Returns:
            str: The session_id of the created session
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (
                    session_id, context, created_at, last_used,
                    max_context_tokens, history_json, metadata_json,
                    model_name, system_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_data['session_id'],
                session_data.get('context', ''),
                session_data.get('created_at', datetime.now().isoformat()),
                session_data.get('last_used', datetime.now().isoformat()),
                session_data.get('max_context_tokens', 64000),
                session_data.get('history_json'),
                session_data.get('metadata_json'),
                session_data.get('model_name'),
                session_data.get('system_prompt')
            ))
            conn.commit()

        return session_data['session_id']

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Dict containing session data, or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, context, created_at, last_used,
                       max_context_tokens, history_json, metadata_json,
                       model_name, system_prompt
                FROM sessions
                WHERE session_id = ?
            """, (session_id,))

            row = cursor.fetchone()
            if row is None:
                return None

            return dict(row)

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """
        Update session fields.

        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update (e.g., {'context': '...', 'last_used': '...'})
        """
        if not updates:
            return

        # Build dynamic UPDATE query
        set_clauses = []
        values = []

        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(session_id)  # For WHERE clause

        query = f"""
            UPDATE sessions
            SET {', '.join(set_clauses)}
            WHERE session_id = ?
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if session was deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all sessions, ordered by last_used descending.

        Args:
            limit: Maximum number of sessions to return (optional)

        Returns:
            List of session dictionaries
        """
        query = """
            SELECT session_id, created_at, last_used,
                   max_context_tokens, model_name
            FROM sessions
            ORDER BY last_used DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def purge_sessions(self, days: int) -> int:
        """
        Remove sessions older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            int: Number of sessions deleted
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM sessions
                WHERE last_used < ?
            """, (cutoff,))
            conn.commit()
            return cursor.rowcount

    def get_session_count(self) -> int:
        """
        Get total number of sessions in database.

        Returns:
            int: Session count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            return cursor.fetchone()['count']
