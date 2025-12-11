"""
Database abstraction layer for session persistence.

Supports SQLite (default) and MongoDB (optional) backends.

Schema Versions:
- V1: Original schema (sessions table only)
- V2: Context management schema (messages, file_references, compaction_history)
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager


# Current schema version
SCHEMA_VERSION = 2


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

    # V1 Schema - Original sessions table
    SCHEMA_V1 = """
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

    # V2 Schema - Context management tables
    SCHEMA_V2 = """
    -- Schema version tracking
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        upgraded_at TEXT NOT NULL
    );

    -- Structured message storage for selective compaction
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tokens INTEGER NOT NULL DEFAULT 0,
        timestamp TEXT NOT NULL,
        is_summary BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id);

    CREATE INDEX IF NOT EXISTS idx_messages_timestamp
    ON messages(timestamp);

    -- Track file references per message for stale detection
    CREATE TABLE IF NOT EXISTS file_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        mode TEXT NOT NULL,
        tokens INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_file_refs_message
    ON file_references(message_id);

    CREATE INDEX IF NOT EXISTS idx_file_refs_path
    ON file_references(file_path);

    -- Compaction audit trail
    CREATE TABLE IF NOT EXISTS compaction_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        level INTEGER NOT NULL,
        tokens_before INTEGER NOT NULL,
        tokens_after INTEGER NOT NULL,
        tokens_freed INTEGER NOT NULL,
        strategy TEXT NOT NULL,
        details TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_compaction_session
    ON compaction_history(session_id);

    -- Vector embeddings for semantic relevance scoring
    CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        model TEXT NOT NULL,
        embedding BLOB NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_embeddings_message
    ON embeddings(message_id);
    """

    # Combined schema for new databases
    SCHEMA = SCHEMA_V1 + SCHEMA_V2

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
            # Check for and perform any needed migrations
            self._migrate_if_needed(conn)

    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """
        Provide a short-lived sqlite3.Connection that is always closed on exit.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        # Enable foreign key support for CASCADE DELETE
        conn.execute("PRAGMA foreign_keys = ON")
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

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """
        Get current schema version from database.

        Returns:
            int: Schema version (0 if no version table exists, i.e., V1 schema)
        """
        cursor = conn.cursor()

        # Check if schema_version table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version'
        """)

        if cursor.fetchone() is None:
            # No version table means V1 schema (original)
            return 1

        # Get the highest version number
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()

        if result is None or result[0] is None:
            return 1

        return result[0]

    def _set_schema_version(self, conn: sqlite3.Connection, version: int):
        """Record schema version in database."""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO schema_version (version, upgraded_at) VALUES (?, ?)",
            (version, datetime.now().isoformat())
        )
        conn.commit()

    def _backup_database(self) -> Optional[str]:
        """
        Create backup of database before migration.

        Returns:
            str: Path to backup file, or None if backup failed
        """
        if not os.path.exists(self.db_path):
            return None

        backup_path = f"{self.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        except (OSError, shutil.Error):
            return None

    def _migrate_if_needed(self, conn: sqlite3.Connection):
        """
        Check schema version and perform migrations if needed.

        Automatically backs up database before any migration.
        """
        current_version = self._get_schema_version(conn)

        if current_version >= SCHEMA_VERSION:
            return  # Already up to date

        # Backup before migration
        backup_path = self._backup_database()

        try:
            if current_version < 2:
                self._migrate_v1_to_v2(conn)

            # Record successful migration
            self._set_schema_version(conn, SCHEMA_VERSION)

        except Exception as e:
            # Migration failed - database may be in inconsistent state
            # The backup is available for recovery
            raise RuntimeError(
                f"Database migration failed: {e}. "
                f"Backup available at: {backup_path}"
            ) from e

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection):
        """
        Migrate from V1 (sessions only) to V2 (context management).

        Creates new tables and migrates existing history_json to messages table.
        """
        cursor = conn.cursor()

        # Create V2 tables (schema_version, messages, file_references, compaction_history)
        conn.executescript(self.SCHEMA_V2)

        # Migrate existing history_json data to messages table
        cursor.execute("""
            SELECT session_id, history_json
            FROM sessions
            WHERE history_json IS NOT NULL AND history_json != ''
        """)

        for row in cursor.fetchall():
            session_id = row[0]
            history_json = row[1]

            try:
                history = json.loads(history_json)
                if isinstance(history, list):
                    for i, msg in enumerate(history):
                        if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            # Estimate tokens (rough: 4 chars per token)
                            content = msg.get('content', '')
                            tokens = len(content) // 4

                            cursor.execute("""
                                INSERT INTO messages
                                (session_id, role, content, tokens, timestamp, is_summary)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                session_id,
                                msg['role'],
                                content,
                                tokens,
                                datetime.now().isoformat(),
                                False
                            ))
            except (json.JSONDecodeError, TypeError, KeyError):
                # Skip malformed history_json entries
                pass

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

    # =========================================================================
    # V2 API: Message Management
    # =========================================================================

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        is_summary: bool = False,
        timestamp: Optional[str] = None
    ) -> int:
        """
        Save a message to the structured messages table.

        Args:
            session_id: Session identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            tokens: Token count for this message
            is_summary: Whether this is a summary message
            timestamp: ISO timestamp (default: now)

        Returns:
            int: Message ID
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages
                (session_id, role, content, tokens, timestamp, is_summary)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, tokens, timestamp, is_summary))
            conn.commit()
            return cursor.lastrowid

    def load_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        include_summaries: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Load messages for a session.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return (newest first, then reversed)
            include_summaries: Whether to include summary messages

        Returns:
            List of message dictionaries ordered by timestamp ascending
        """
        query = """
            SELECT id, session_id, role, content, tokens, timestamp, is_summary
            FROM messages
            WHERE session_id = ?
        """
        params: List[Any] = [session_id]

        if not include_summaries:
            query += " AND is_summary = FALSE"

        query += " ORDER BY timestamp ASC"

        if limit is not None:
            # Get newest N messages by using subquery
            query = f"""
                SELECT * FROM (
                    SELECT id, session_id, role, content, tokens, timestamp, is_summary
                    FROM messages
                    WHERE session_id = ?
                    {"AND is_summary = FALSE" if not include_summaries else ""}
                    ORDER BY timestamp DESC
                    LIMIT ?
                ) ORDER BY timestamp ASC
            """
            params = [session_id, limit]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_message_tokens(self, session_id: str) -> int:
        """
        Get total token count for a session's messages.

        Args:
            session_id: Session identifier

        Returns:
            int: Total tokens
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(tokens), 0) as total
                FROM messages
                WHERE session_id = ?
            """, (session_id,))
            return cursor.fetchone()["total"]

    def delete_messages(self, message_ids: List[int]) -> int:
        """
        Delete specific messages by ID.

        Args:
            message_ids: List of message IDs to delete

        Returns:
            int: Number of messages deleted
        """
        if not message_ids:
            return 0

        placeholders = ",".join("?" * len(message_ids))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM messages WHERE id IN ({placeholders})",
                message_ids
            )
            conn.commit()
            return cursor.rowcount

    def delete_messages_before(
        self,
        session_id: str,
        before_timestamp: str,
        keep_count: int = 0
    ) -> int:
        """
        Delete messages before a timestamp, optionally keeping N newest.

        Args:
            session_id: Session identifier
            before_timestamp: Delete messages before this ISO timestamp
            keep_count: Number of newest messages to always keep

        Returns:
            int: Number of messages deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if keep_count > 0:
                # Get IDs of messages to keep
                cursor.execute("""
                    SELECT id FROM messages
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, keep_count))
                keep_ids = [row["id"] for row in cursor.fetchall()]

                if keep_ids:
                    placeholders = ",".join("?" * len(keep_ids))
                    cursor.execute(f"""
                        DELETE FROM messages
                        WHERE session_id = ?
                        AND timestamp < ?
                        AND id NOT IN ({placeholders})
                    """, [session_id, before_timestamp] + keep_ids)
                else:
                    cursor.execute("""
                        DELETE FROM messages
                        WHERE session_id = ? AND timestamp < ?
                    """, (session_id, before_timestamp))
            else:
                cursor.execute("""
                    DELETE FROM messages
                    WHERE session_id = ? AND timestamp < ?
                """, (session_id, before_timestamp))

            conn.commit()
            return cursor.rowcount

    # =========================================================================
    # V2 API: File Reference Tracking
    # =========================================================================

    def track_file_reference(
        self,
        message_id: int,
        file_path: str,
        mode: str,
        tokens: int = 0
    ) -> int:
        """
        Record a file reference in a message.

        Args:
            message_id: ID of the message containing the reference
            file_path: Path to the referenced file
            mode: Reference mode ('full', 'summary', 'extract', 'lines')
            tokens: Token count for the file content

        Returns:
            int: File reference ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO file_references
                (message_id, file_path, mode, tokens)
                VALUES (?, ?, ?, ?)
            """, (message_id, file_path, mode, tokens))
            conn.commit()
            return cursor.lastrowid

    def get_file_references(
        self,
        session_id: str,
        file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get file references for a session.

        Args:
            session_id: Session identifier
            file_path: Optional filter by file path

        Returns:
            List of file reference dictionaries with message info
        """
        query = """
            SELECT fr.id, fr.message_id, fr.file_path, fr.mode, fr.tokens,
                   m.timestamp, m.role
            FROM file_references fr
            JOIN messages m ON fr.message_id = m.id
            WHERE m.session_id = ?
        """
        params: List[Any] = [session_id]

        if file_path is not None:
            query += " AND fr.file_path = ?"
            params.append(file_path)

        query += " ORDER BY m.timestamp DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_stale_files(
        self,
        session_id: str,
        stale_threshold: int = 3,
        mode_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find files not referenced in recent messages.

        Args:
            session_id: Session identifier
            stale_threshold: Number of recent messages to check
            mode_filter: Optional filter by mode (e.g., 'full')

        Returns:
            List of stale file info dictionaries with:
            - file_path: Path to the file
            - mode: Last reference mode
            - tokens: Tokens used
            - last_message_id: ID of last message referencing this file
            - messages_ago: How many messages since last reference
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get recent message IDs
            cursor.execute("""
                SELECT id FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, stale_threshold))
            recent_ids = [row["id"] for row in cursor.fetchall()]

            if not recent_ids:
                return []

            # Get all unique files with their last reference
            query = """
                SELECT fr.file_path, fr.mode, fr.tokens, fr.message_id,
                       (SELECT COUNT(*) FROM messages m2
                        WHERE m2.session_id = ? AND m2.timestamp > m.timestamp) as messages_ago
                FROM file_references fr
                JOIN messages m ON fr.message_id = m.id
                WHERE m.session_id = ?
            """
            params: List[Any] = [session_id, session_id]

            if mode_filter:
                query += " AND fr.mode = ?"
                params.append(mode_filter)

            query += """
                GROUP BY fr.file_path
                HAVING fr.message_id = MAX(fr.message_id)
            """

            cursor.execute(query, params)
            all_files = [dict(row) for row in cursor.fetchall()]

            # Filter to only stale files (not in recent messages)
            recent_set = set(recent_ids)
            stale = [
                f for f in all_files
                if f["message_id"] not in recent_set
            ]

            return stale

    def update_file_reference_mode(
        self,
        file_ref_id: int,
        new_mode: str,
        new_tokens: int
    ):
        """
        Update the mode and tokens for a file reference (for recompression).

        Args:
            file_ref_id: File reference ID
            new_mode: New mode ('full' -> 'summary', etc.)
            new_tokens: New token count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_references
                SET mode = ?, tokens = ?
                WHERE id = ?
            """, (new_mode, new_tokens, file_ref_id))
            conn.commit()

    # =========================================================================
    # V2 API: Compaction History
    # =========================================================================

    def record_compaction(
        self,
        session_id: str,
        level: int,
        tokens_before: int,
        tokens_after: int,
        strategy: str,
        details: Optional[str] = None
    ) -> int:
        """
        Record a compaction event.

        Args:
            session_id: Session identifier
            level: Compaction level (1=soft, 2=hard, 3=emergency)
            tokens_before: Token count before compaction
            tokens_after: Token count after compaction
            strategy: Strategy used ('file_compress', 'message_prune', 'llm_summary')
            details: Optional JSON string with additional details

        Returns:
            int: Compaction history ID
        """
        tokens_freed = tokens_before - tokens_after

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO compaction_history
                (session_id, timestamp, level, tokens_before, tokens_after,
                 tokens_freed, strategy, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now().isoformat(),
                level,
                tokens_before,
                tokens_after,
                tokens_freed,
                strategy,
                details
            ))
            conn.commit()
            return cursor.lastrowid

    def get_compaction_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get compaction history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum records to return

        Returns:
            List of compaction history dictionaries
        """
        query = """
            SELECT id, session_id, timestamp, level, tokens_before,
                   tokens_after, tokens_freed, strategy, details
            FROM compaction_history
            WHERE session_id = ?
            ORDER BY timestamp DESC
        """
        params: List[Any] = [session_id]

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_total_tokens_freed(self, session_id: str) -> int:
        """
        Get total tokens freed by compaction for a session.

        Args:
            session_id: Session identifier

        Returns:
            int: Total tokens freed
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(tokens_freed), 0) as total
                FROM compaction_history
                WHERE session_id = ?
            """, (session_id,))
            return cursor.fetchone()["total"]

    def get_last_compaction(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent compaction event for a session.

        Args:
            session_id: Session identifier

        Returns:
            Compaction history dict, or None if no compactions
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, timestamp, level, tokens_before,
                       tokens_after, tokens_freed, strategy, details
                FROM compaction_history
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
