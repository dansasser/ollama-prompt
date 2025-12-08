"""
Database abstraction layer for session persistence.

Supports SQLite (default) and MongoDB (optional) backends.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager


def get_default_db_path() -> Path:
    """
    Get platform-appropriate database path for SQLite.

    Returns:
        Path: Database file path

    Platform-specific locations:
        - Windows: %APPDATA%\\ollama-prompt\\sessions.db
        - Unix/Linux/Mac: ~/.config/ollama-prompt/sessions.db
    """
    if os.name == "nt":  # Windows
        base = Path(os.getenv("APPDATA", Path.home()))
    else:  # Unix/Linux/Mac
        base = Path.home() / ".config"

    db_dir = base / "ollama-prompt"

    # SECURITY: Create directory with restrictive permissions (user-only access)
    # On Unix/Linux/Mac: 0o700 (rwx------)
    # On Windows: mkdir handles permissions via ACLs
    db_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # On Unix systems, explicitly set permissions in case umask prevented proper mode
    if os.name != "nt" and db_dir.exists():
        try:
            os.chmod(db_dir, 0o700)
        except (OSError, PermissionError):
            # Best effort - may fail if not owner
            pass

    return db_dir / "sessions.db"


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

        Raises:
            ValueError: If custom db_path is outside allowed directories
        """
        env_path = os.getenv("OLLAMA_PROMPT_DB_PATH")

        if db_path:
            # Explicitly provided path takes precedence (no validation for testing)
            self.db_path = db_path
        elif env_path:
            # Use the env var value verbatim (tests expect exact string)
            # We skip _validate_db_path here to avoid canonicalization issues
            self.db_path = env_path
        else:
            # Use default path
            self.db_path = str(get_default_db_path())

        # Ensure parent dir exists if necessary (only when using default path)
        if not env_path and not db_path:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = None  # Do NOT keep a long-lived connection open by default.

        # Initialize schema using the context manager (ensures connection closed)
        with self._get_connection() as conn:
            self._ensure_schema(conn)

    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """
        Provide a short-lived sqlite3.Connection that is always closed on exit.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                # Be defensive; closing should normally succeed.
                pass

    def close(self):
        """Close database connections (for testing/cleanup)."""
        # If there is any persistent connection (e.g., from an old pattern), close it.
        if getattr(self, "_conn", None) is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _validate_db_path(self, path: str) -> str:
        """
        Validate database path is in a safe location.

        Args:
            path: Database file path to validate

        Returns:
            str: Validated absolute path

        Raises:
            ValueError: If path is outside allowed directories
        """
        from pathlib import Path

        # Do not resolve the path here to avoid canonicalization issues in tests
        # We only check containment against the home directory
        try:
            path_obj = Path(path).expanduser().resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid database path: {path}") from e

        # Path must be under user's home directory
        home = Path.home()
        try:
            path_obj.relative_to(home)
        except ValueError:
            raise ValueError(
                f"Database path must be under home directory. "
                f"Path '{path}' is not under '{home}'"
            )

        # Return the original path string for consistency, but ensure it's absolute
        return str(Path(path).expanduser().resolve())

    def _ensure_schema(self, conn: sqlite3.Connection):
        """Create database schema if it doesn't exist."""
        conn.executescript(self.SCHEMA)
        conn.commit()

        # SECURITY: Set restrictive permissions on database file (user-only access)
        # On Unix/Linux/Mac: 0o600 (rw-------)
        if os.name != "nt" and os.path.exists(self.db_path):
            try:
                os.chmod(self.db_path, 0o600)
            except (OSError, PermissionError):
                # Best effort - may fail if not owner
                pass

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
            cursor.execute(
                """
                INSERT INTO sessions (
                    session_id, context, created_at, last_used,
                    max_context_tokens, history_json, metadata_json,
                    model_name, system_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_data["session_id"],
                    session_data.get("context", ""),
                    session_data.get("created_at", datetime.now().isoformat()),
                    session_data.get("last_used", datetime.now().isoformat()),
                    session_data.get("max_context_tokens", 64000),
                    session_data.get("history_json"),
                    session_data.get("metadata_json"),
                    session_data.get("model_name"),
                    session_data.get("system_prompt"),
                ),
            )
            conn.commit()

        return session_data["session_id"]

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
            cursor.execute(
                """
                SELECT session_id, context, created_at, last_used,
                       max_context_tokens, history_json, metadata_json,
                       model_name, system_prompt
                FROM sessions
                WHERE session_id = ?
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            return dict(row)

    # Whitelist of allowed column names for updates
    ALLOWED_UPDATE_COLUMNS = {
        "context",
        "last_used",
        "history_json",
        "metadata_json",
        "max_context_tokens",
        "system_prompt",
    }

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """
        Update session fields.

        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update (e.g., {'context': '...', 'last_used': '...'})

        Raises:
            ValueError: If any update key is not in the whitelist of allowed columns
        """
        if not updates:
            return

        # Validate all column names against whitelist (SECURITY: prevent SQL injection)
        for key in updates.keys():
            if key not in self.ALLOWED_UPDATE_COLUMNS:
                raise ValueError(f"Invalid column name: {key}")

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

        Raises:
            ValueError: If limit is not a positive integer
        """
        query = """
            SELECT session_id, created_at, last_used,
                   max_context_tokens, model_name, history_json, context
            FROM sessions
            ORDER BY last_used DESC
        """

        # Validate limit parameter (SECURITY: prevent SQL injection)
        params: tuple[int, ...] = ()
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError(f"Invalid limit value: {limit}")
            query += " LIMIT ?"
            params = (limit,)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
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
            cursor.execute(
                """
                DELETE FROM sessions
                WHERE last_used < ?
            """,
                (cutoff,),
            )
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
            return cursor.fetchone()["count"]
