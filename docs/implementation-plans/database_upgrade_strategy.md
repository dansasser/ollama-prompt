# Database Upgrade Strategy for ollama-prompt

## Current State Analysis

### Existing Schema (session_db.py)

```sql
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
```

### What This Supports

| Feature | Current Support | Limitation |
|---------|----------------|------------|
| **Session persistence** | ✅ Yes | Works well |
| **Conversation history** | ✅ Yes (as JSON blob) | Not queryable, no structure |
| **Context tracking** | ✅ Yes (token count) | No per-message tracking |
| **File references** | ❌ No | Not tracked at all |
| **Message embeddings** | ❌ No | Can't do semantic search |
| **Chunked content** | ❌ No | Can't store file chunks |
| **Compaction history** | ❌ No | Can't track what was compressed |

### The Problem

The current schema treats conversation history as an **opaque JSON blob** stored in `history_json`. This means:

1. **Can't query individual messages** - have to load entire JSON and parse it
2. **Can't store embeddings** - no place to put vector data
3. **Can't track file chunks** - files are embedded in message text
4. **Can't track compaction** - no record of what was compressed when
5. **Can't do semantic search** - no vectors to search

**For the features we've designed (chunking, embeddings, compaction), we need a structured, relational schema.**

---

## Upgraded Schema Design

### Philosophy: Normalize the Data

Instead of storing everything as JSON blobs, we'll create **proper relational tables** for:
- Individual messages
- File references and chunks
- Embeddings
- Compaction events

This enables:
- ✅ Efficient queries
- ✅ Semantic search
- ✅ Compaction tracking
- ✅ File chunk management

### New Schema (Version 2)

```sql
-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Sessions table (upgraded)
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_context_tokens INTEGER DEFAULT 64000,
    current_tokens INTEGER DEFAULT 0,
    model_name TEXT,
    system_prompt TEXT,
    compaction_level INTEGER DEFAULT 0,
    total_compactions INTEGER DEFAULT 0,
    schema_version INTEGER DEFAULT 2  -- NEW: Track schema version
);

CREATE INDEX idx_sessions_last_used ON sessions(last_used);
CREATE INDEX idx_sessions_model ON sessions(model_name);

-- ============================================================================
-- MESSAGES TABLE (NEW)
-- ============================================================================

-- Individual messages (replaces history_json blob)
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_index INTEGER NOT NULL,  -- Order within session
    is_summary BOOLEAN DEFAULT 0,  -- Was this created by compaction?
    is_compressed BOOLEAN DEFAULT 0,  -- Has content been compressed?
    original_tokens INTEGER,  -- Tokens before compression (if compressed)
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_session ON messages(session_id, message_index);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_messages_role ON messages(role);

-- ============================================================================
-- FILE REFERENCES TABLE (NEW)
-- ============================================================================

-- Track which files are referenced in which messages
CREATE TABLE file_references (
    reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    mode TEXT NOT NULL,  -- 'full', 'summary', 'chunk'
    tokens INTEGER NOT NULL,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reference_count INTEGER DEFAULT 1,
    is_compressed BOOLEAN DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

CREATE INDEX idx_file_refs_session ON file_references(session_id);
CREATE INDEX idx_file_refs_path ON file_references(file_path);
CREATE INDEX idx_file_refs_message ON file_references(message_id);

-- ============================================================================
-- FILE CHUNKS TABLE (NEW - for Phase 1 & 3)
-- ============================================================================

-- Store individual chunks of files (functions, classes, sections)
CREATE TABLE file_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_type TEXT NOT NULL,  -- 'function', 'class', 'section', 'full'
    chunk_name TEXT NOT NULL,  -- Function/class name or section heading
    content TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_chunks_session ON file_chunks(session_id);
CREATE INDEX idx_chunks_path ON file_chunks(file_path);
CREATE INDEX idx_chunks_type ON file_chunks(chunk_type);
CREATE INDEX idx_chunks_name ON file_chunks(chunk_name);

-- ============================================================================
-- EMBEDDINGS TABLE (NEW - for Phase 2 & 3)
-- ============================================================================

-- Store vector embeddings for semantic search
CREATE TABLE embeddings (
    embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'message', 'chunk'
    entity_id INTEGER NOT NULL,  -- message_id or chunk_id
    session_id TEXT NOT NULL,
    embedding BLOB NOT NULL,  -- Vector as binary data
    embedding_model TEXT NOT NULL,  -- e.g., 'nomic-embed-text'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_embeddings_entity ON embeddings(entity_type, entity_id);
CREATE INDEX idx_embeddings_session ON embeddings(session_id);

-- ============================================================================
-- COMPACTION HISTORY TABLE (NEW)
-- ============================================================================

-- Track all compaction events for analytics and debugging
CREATE TABLE compaction_history (
    compaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level INTEGER NOT NULL,  -- 1, 2, or 3
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_freed INTEGER NOT NULL,
    actions_json TEXT,  -- JSON array of specific actions taken
    duration_ms INTEGER,  -- How long compaction took
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX idx_compaction_session ON compaction_history(session_id);
CREATE INDEX idx_compaction_timestamp ON compaction_history(timestamp);

-- ============================================================================
-- METADATA TABLE (for schema versioning and migrations)
-- ============================================================================

CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_metadata (key, value) VALUES ('version', '2');
INSERT INTO schema_metadata (key, value) VALUES ('upgraded_at', datetime('now'));
```

---

## Schema Comparison

### Before (Version 1)

```
sessions
├── session_id (PK)
├── context (TEXT - unused?)
├── history_json (TEXT - entire conversation as JSON blob)
├── metadata_json (TEXT - unstructured)
└── ...
```

**Problems:**
- Can't query individual messages
- Can't store embeddings
- Can't track compaction
- Can't manage file chunks

### After (Version 2)

```
sessions (1)
├── session_id (PK)
├── current_tokens
├── compaction_level
└── ...

messages (N) ← One-to-many
├── message_id (PK)
├── session_id (FK)
├── content
├── tokens
├── is_compressed
└── ...

file_references (N) ← Many-to-many
├── reference_id (PK)
├── session_id (FK)
├── message_id (FK)
├── file_path
├── mode (full/summary/chunk)
└── ...

file_chunks (N) ← For chunking strategy
├── chunk_id (PK)
├── session_id (FK)
├── file_path
├── chunk_type
├── content
└── ...

embeddings (N) ← For semantic search
├── embedding_id (PK)
├── entity_type (message/chunk)
├── entity_id (FK)
├── embedding (BLOB)
└── ...

compaction_history (N) ← For analytics
├── compaction_id (PK)
├── session_id (FK)
├── level
├── tokens_freed
└── ...
```

**Benefits:**
- ✅ Can query any message
- ✅ Can store and search embeddings
- ✅ Can track compaction events
- ✅ Can manage file chunks efficiently
- ✅ Can analyze usage patterns

---

## Migration Strategy

### Challenge: Existing Users Have Data

We can't just drop the old schema. We need to **migrate existing data** without loss.

### Migration Approach: Automatic Upgrade

When the application starts, check the schema version and automatically upgrade if needed.

```python
class SessionDatabase:
    def __init__(self, db_path: Optional[str] = None):
        # ... existing init code ...
        
        # Check and upgrade schema if needed
        self._check_and_upgrade_schema()
    
    def _check_and_upgrade_schema(self):
        """Automatically upgrade database schema if needed."""
        current_version = self._get_schema_version()
        
        if current_version == 0:
            # No schema_metadata table = version 1
            print("[Database] Detected schema version 1, upgrading to version 2...")
            self._upgrade_v1_to_v2()
        elif current_version == 1:
            print("[Database] Detected schema version 1, upgrading to version 2...")
            self._upgrade_v1_to_v2()
        elif current_version == 2:
            # Already on latest version
            pass
        else:
            raise ValueError(f"Unknown schema version: {current_version}")
    
    def _get_schema_version(self) -> int:
        """Get current schema version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if schema_metadata table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_metadata'
            """)
            
            if not cursor.fetchone():
                # No metadata table = version 1 (or 0 if completely empty)
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='sessions'
                """)
                return 1 if cursor.fetchone() else 0
            
            # Get version from metadata
            cursor.execute("SELECT value FROM schema_metadata WHERE key='version'")
            row = cursor.fetchone()
            return int(row[0]) if row else 1
    
    def _upgrade_v1_to_v2(self):
        """Migrate from version 1 to version 2."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            print("[Database] Creating new tables...")
            
            # Create all new tables
            cursor.executescript(self.SCHEMA_V2)
            
            print("[Database] Migrating existing sessions...")
            
            # Get all existing sessions
            cursor.execute("SELECT session_id, history_json, created_at, last_used, model_name FROM sessions")
            sessions = cursor.fetchall()
            
            for session_id, history_json, created_at, last_used, model_name in sessions:
                if not history_json:
                    continue
                
                # Parse history JSON
                try:
                    import json
                    history = json.loads(history_json)
                except:
                    print(f"[Database] Warning: Could not parse history for session {session_id}")
                    continue
                
                # Migrate messages
                for idx, msg in enumerate(history):
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    tokens = len(content) // 4  # Estimate
                    
                    cursor.execute("""
                        INSERT INTO messages 
                        (session_id, role, content, tokens, message_index, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session_id, role, content, tokens, idx, created_at))
                
                # Update session with new fields
                cursor.execute("""
                    UPDATE sessions 
                    SET current_tokens = ?, compaction_level = 0, total_compactions = 0
                    WHERE session_id = ?
                """, (sum(len(m.get('content', '')) // 4 for m in history), session_id))
            
            # Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                INSERT OR REPLACE INTO schema_metadata (key, value) 
                VALUES ('version', '2'), ('upgraded_at', datetime('now'))
            """)
            
            conn.commit()
            
            print("[Database] Migration complete!")
```

### Migration Steps

1. **Detect version** - Check for `schema_metadata` table
2. **Create new tables** - Add all v2 tables
3. **Migrate data** - Parse `history_json` and insert into `messages` table
4. **Update sessions** - Add new fields (`current_tokens`, etc.)
5. **Mark complete** - Set `schema_version = 2`

### Backward Compatibility

**Option 1: Keep old columns** (safer)
```sql
-- Keep history_json for rollback
ALTER TABLE sessions ADD COLUMN history_json_backup TEXT;
UPDATE sessions SET history_json_backup = history_json;
```

**Option 2: Drop old columns** (cleaner)
```sql
-- After successful migration, drop old columns
ALTER TABLE sessions DROP COLUMN history_json;
ALTER TABLE sessions DROP COLUMN context;
ALTER TABLE sessions DROP COLUMN metadata_json;
```

I recommend **Option 1** for the first release, then **Option 2** after a few versions.

---

## Implementation Plan

### Phase 1: Core Schema Upgrade

**Goal:** Get the new schema in place without breaking existing functionality

**Steps:**
1. Add schema versioning code
2. Create migration function
3. Test with existing databases
4. Deploy with automatic migration

**Timeline:** 1-2 days

### Phase 2: Use New Tables

**Goal:** Start using the new tables instead of JSON blobs

**Steps:**
1. Update `SessionDatabase.save_message()` to insert into `messages` table
2. Update `SessionDatabase.load_session()` to read from `messages` table
3. Update `SessionDatabase.track_file_reference()` (new method)
4. Keep `history_json` in sync for backward compatibility

**Timeline:** 2-3 days

### Phase 3: Add Embeddings Support

**Goal:** Enable semantic search with embeddings

**Steps:**
1. Add `generate_embedding()` method
2. Add `store_embedding()` method
3. Add `search_by_similarity()` method
4. Integrate with Level 2 compaction

**Timeline:** 3-4 days

### Phase 4: Add Chunking Support

**Goal:** Enable file chunking and storage

**Steps:**
1. Add `store_chunk()` method
2. Add `get_chunks_for_file()` method
3. Integrate with Phase 1 chunking strategy
4. Add chunk-level embeddings

**Timeline:** 3-4 days

---

## Storage Requirements

### Disk Space Estimates

| Data Type | Size per Item | Items per Session | Total per Session |
|-----------|---------------|-------------------|-------------------|
| **Messages** | 1-5 KB | 50-100 | 50-500 KB |
| **File chunks** | 0.5-2 KB | 20-50 | 10-100 KB |
| **Embeddings** | 3 KB (768 dims × 4 bytes) | 50-100 | 150-300 KB |
| **Compaction history** | 0.2 KB | 5-10 | 1-2 KB |
| **Total** | - | - | **~200-900 KB per session** |

**For 100 sessions:** ~20-90 MB (very manageable)

### Performance Considerations

**SQLite is fast enough for this:**
- ✅ Can handle millions of rows
- ✅ Indexes make queries fast
- ✅ BLOB storage for embeddings is efficient
- ✅ No need for separate vector database (yet)

**When to upgrade to a real vector DB:**
- If you have > 10,000 chunks per session
- If semantic search is too slow (> 1 second)
- If you need advanced vector operations (clustering, etc.)

For now, **SQLite with the upgraded schema is sufficient**.

---

## Alternative: SQLite with Vector Extension

If you want better vector search performance without a separate database, use **SQLite with the `sqlite-vec` extension**.

### What is sqlite-vec?

A SQLite extension that adds vector similarity search directly to SQLite.

**Installation:**
```bash
pip install sqlite-vec
```

**Usage:**
```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect('sessions.db')
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# Create vector table
conn.execute("""
    CREATE VIRTUAL TABLE vec_embeddings USING vec0(
        embedding float[768]
    )
""")

# Insert vectors
conn.execute("INSERT INTO vec_embeddings VALUES (?)", (embedding_array,))

# Search by similarity
results = conn.execute("""
    SELECT rowid, distance 
    FROM vec_embeddings 
    WHERE embedding MATCH ? 
    ORDER BY distance 
    LIMIT 10
""", (query_embedding,))
```

**Benefits:**
- ✅ No separate vector database needed
- ✅ Fast vector similarity search
- ✅ Stays in SQLite ecosystem
- ✅ Easy to deploy

**Tradeoff:**
- ❌ Requires C extension (might complicate deployment)
- ❌ Not as feature-rich as dedicated vector DBs

**Recommendation:** Start with plain SQLite + BLOB storage, upgrade to `sqlite-vec` if search is too slow.

---

## Summary

### What Changes

| Aspect | Before | After |
|--------|--------|-------|
| **Schema** | 1 table (sessions) | 6 tables (sessions, messages, file_references, file_chunks, embeddings, compaction_history) |
| **Message storage** | JSON blob | Structured rows |
| **File tracking** | None | Dedicated table |
| **Embeddings** | Not supported | BLOB storage |
| **Compaction tracking** | Not supported | Full history |
| **Queryability** | Poor (parse JSON) | Excellent (SQL queries) |

### Migration Path

1. **Automatic detection** - Check schema version on startup
2. **Automatic upgrade** - Migrate data from v1 to v2
3. **Backward compatible** - Keep old columns initially
4. **Gradual adoption** - Use new tables while keeping old ones in sync

### Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1** | 1-2 days | Schema upgrade + migration |
| **Phase 2** | 2-3 days | Use new tables |
| **Phase 3** | 3-4 days | Embeddings support |
| **Phase 4** | 3-4 days | Chunking support |
| **Total** | **~2 weeks** | Fully upgraded database |

### Next Steps

1. **Implement schema v2** in `session_db.py`
2. **Add migration code** with automatic upgrade
3. **Test migration** with existing databases
4. **Deploy** with backward compatibility

**Want me to implement the schema upgrade and migration code now?**
