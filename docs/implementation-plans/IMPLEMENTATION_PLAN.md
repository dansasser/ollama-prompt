# Implementation Plan: Context Window Optimization for ollama-prompt

**Version:** 1.0  
**Date:** December 7, 2024  
**Target Repository:** `dansasser/ollama-prompt`  
**Prepared for:** Development Team

---

## Executive Summary

This document provides a complete implementation plan for adding intelligent context window management to `ollama-prompt`. The implementation is divided into four phases that can be executed sequentially over approximately 3-4 weeks. Each phase is independent and delivers value incrementally, allowing for testing and validation before proceeding to the next phase.

### Goals

1. **Reduce context window usage by 60-90%** through intelligent file summarization and chunking
2. **Enable longer conversations** (50-100+ messages vs. current 10-15)
3. **Support larger codebases** (10-20 files vs. current 2-3)
4. **Automatic context management** with no user intervention required
5. **Maintain backward compatibility** with existing sessions

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ollama-prompt CLI                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: File Chunker (Smart Summarization)               │
│  ├─ Summarize Python files (classes, functions, imports)   │
│  └─ Targeted extraction (@file.py:function_name)           │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Database Schema Upgrade                          │
│  ├─ Migrate from JSON blobs to structured tables           │
│  ├─ Add: messages, file_references, embeddings, chunks     │
│  └─ Automatic migration for existing users                 │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: Context Manager (Automatic Compaction)           │
│  ├─ Level 1: Rule-based file compression (50-65% full)     │
│  ├─ Level 2: Vector-based message pruning (65-80% full)    │
│  └─ Level 3: LLM summarization (>80% full)                 │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: Semantic Search (Vector Embeddings)              │
│  ├─ Generate embeddings for messages and chunks            │
│  ├─ Store in SQLite as BLOB                                │
│  └─ Cosine similarity search for relevance scoring         │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: File Chunking and Summarization

**Duration:** 4-5 days  
**Priority:** High  
**Dependencies:** None  
**Deliverable:** Smart file summarization with 95% context savings

### Overview

Implement intelligent file summarization that replaces full file content with structured summaries showing file structure (classes, functions, imports) while preserving navigability.

### Tasks

#### Task 1.1: Create `file_chunker.py` Module

**File:** `ollama_prompt/file_chunker.py`

**Requirements:**
- Create `FileChunker` class with methods for parsing and summarizing Python files
- Use Python's `ast` module for parsing
- Support extraction of: imports, classes, methods, functions, constants
- Generate human-readable summaries with line numbers

**Acceptance Criteria:**
- [ ] Can parse valid Python files without errors
- [ ] Extracts all top-level classes and functions
- [ ] Extracts methods for each class
- [ ] Includes line numbers for all elements
- [ ] Handles syntax errors gracefully
- [ ] Summary is < 10% of original file size

**Implementation Details:**

```python
class FileChunker:
    """Intelligent file chunking and summarization."""
    
    def summarize_python(self, content: str, path: str) -> Dict[str, Any]:
        """
        Generate structured summary of Python file.
        
        Returns dict with:
        - type: 'python'
        - lines: line count
        - size_kb: file size
        - imports: list of imports
        - classes: list of {name, line, methods}
        - functions: list of {name, line}
        - constants: list of {name, line}
        """
        
    def format_summary(self, summary: Dict) -> str:
        """Format summary as readable text for model."""
        
    def extract_element(self, content: str, element_name: str) -> Optional[str]:
        """Extract specific function or class by name."""
```

**Testing:**
- Unit tests for each method
- Test files: simple.py, complex.py, syntax_error.py
- Verify summary size is < 10% of original

#### Task 1.2: Update `cli.py` to Use Summarization

**File:** `ollama_prompt/cli.py`

**Requirements:**
- Modify `read_file_snippet()` to accept mode parameter
- Add mode detection from file reference syntax
- Integrate `FileChunker` for summarization
- Support new syntax: `@file.py:full`, `@file.py:summary`, `@file.py:function_name`

**Acceptance Criteria:**
- [ ] `@file.py` defaults to summary mode
- [ ] `@file.py:full` sends full content
- [ ] `@file.py:function_name` extracts specific element
- [ ] Summary includes instructions for getting full content
- [ ] Backward compatible (existing `@file.py` still works)

**Implementation Details:**

```python
def read_file_snippet(path, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES, mode="summary"):
    """
    Read file with optional summarization.
    
    Args:
        mode: "summary" (default), "full", or "extract:element_name"
    """
    result = read_file_secure(path, repo_root, max_bytes, audit=True)
    
    if not result["ok"]:
        return result
    
    if mode == "summary" and len(result["content"]) > 5000:
        chunker = FileChunker()
        if path.endswith('.py'):
            summary = chunker.summarize_python(result["content"], path)
            result["content"] = chunker.format_summary(summary)
            result["summarized"] = True
    
    return result
```

**Testing:**
- Integration tests with real files
- Test all modes: summary, full, extract
- Verify token savings (measure before/after)

#### Task 1.3: Update File Reference Parser

**File:** `ollama_prompt/cli.py` (function: `expand_file_refs_in_prompt`)

**Requirements:**
- Update regex pattern to capture mode suffix
- Parse `:full`, `:summary`, `:function_name` suffixes
- Route to appropriate handler based on mode

**Acceptance Criteria:**
- [ ] Parses `@./file.py:mode` correctly
- [ ] Defaults to summary if no mode specified
- [ ] Handles invalid modes gracefully
- [ ] Preserves existing directory operations (`:list`, `:tree`, `:search`)

**Implementation Details:**

```python
# Updated pattern to capture mode
pattern = re.compile(r"@((?:\.\.?[/\\]|[/\\])[^\s@?!,;]+?)(?::(\w+))?(?:\b|$)")

def _repl(m):
    path = m.group(1)
    mode = m.group(2) or "summary"
    
    if mode == "full":
        res = read_file_snippet(path, repo_root, max_bytes, mode="full")
        label = f"FILE: {path} (FULL)"
    elif mode == "summary":
        res = read_file_snippet(path, repo_root, max_bytes, mode="summary")
        label = f"FILE: {path} (SUMMARY)"
    else:
        # Extract specific element
        res = extract_code_element(path, mode, repo_root, max_bytes)
        label = f"FILE: {path}:{mode}"
```

**Testing:**
- Test all syntax variations
- Test with multiple files in one prompt
- Test error cases (invalid mode, missing file)

### Deliverables

- [ ] `ollama_prompt/file_chunker.py` (new file, ~300 lines)
- [ ] Updated `ollama_prompt/cli.py` (~100 lines changed)
- [ ] Unit tests in `tests/test_file_chunker.py` (new file, ~200 lines)
- [ ] Integration tests in `tests/test_cli_integration.py` (~50 lines added)
- [ ] Documentation update in `README.md` (new syntax examples)

### Success Metrics

- **Context savings:** 90-95% for summarized files
- **Performance:** Summarization < 100ms per file
- **Accuracy:** Summary includes all top-level elements
- **Usability:** Users can navigate to full content easily

---

## Phase 2: Database Schema Upgrade

**Duration:** 3-4 days  
**Priority:** High  
**Dependencies:** None (can run in parallel with Phase 1)  
**Deliverable:** Structured database with automatic migration

### Overview

Upgrade the SQLite database from JSON blob storage to structured tables that support messages, file references, embeddings, and compaction tracking.

### Tasks

#### Task 2.1: Design and Implement Schema V2

**File:** `ollama_prompt/session_db.py`

**Requirements:**
- Add new tables: `messages`, `file_references`, `file_chunks`, `embeddings`, `compaction_history`, `schema_metadata`
- Update `sessions` table with new columns
- Create indexes for performance
- Add schema version tracking

**Acceptance Criteria:**
- [ ] All tables created with correct columns and types
- [ ] Foreign key constraints properly defined
- [ ] Indexes created on frequently queried columns
- [ ] Schema version stored in `schema_metadata` table

**Implementation Details:**

```python
SCHEMA_V2 = """
-- Sessions table (upgraded)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_context_tokens INTEGER DEFAULT 64000,
    current_tokens INTEGER DEFAULT 0,
    model_name TEXT,
    system_prompt TEXT,
    compaction_level INTEGER DEFAULT 0,
    total_compactions INTEGER DEFAULT 0,
    schema_version INTEGER DEFAULT 2
);

-- Messages table (NEW)
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_index INTEGER NOT NULL,
    is_summary BOOLEAN DEFAULT 0,
    is_compressed BOOLEAN DEFAULT 0,
    original_tokens INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- [Additional tables as specified in database_upgrade_strategy.md]
```

**Testing:**
- Test schema creation on empty database
- Verify all indexes are created
- Test foreign key constraints
- Verify schema version is set correctly

#### Task 2.2: Implement Automatic Migration

**File:** `ollama_prompt/session_db.py`

**Requirements:**
- Detect schema version on database initialization
- Automatically upgrade from V1 to V2
- Migrate data from `history_json` to `messages` table
- Preserve all existing session data
- Handle migration errors gracefully

**Acceptance Criteria:**
- [ ] Detects V1 schema correctly
- [ ] Creates V2 tables without errors
- [ ] Migrates all sessions from V1 to V2
- [ ] Preserves message order and content
- [ ] Updates schema version to 2
- [ ] Logs migration progress
- [ ] Handles empty databases correctly

**Implementation Details:**

```python
def _check_and_upgrade_schema(self):
    """Automatically upgrade database schema if needed."""
    current_version = self._get_schema_version()
    
    if current_version < 2:
        print("[Database] Upgrading schema from v{} to v2...".format(current_version))
        self._upgrade_v1_to_v2()
        print("[Database] Migration complete!")

def _upgrade_v1_to_v2(self):
    """Migrate from version 1 to version 2."""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # Create new tables
        cursor.executescript(self.SCHEMA_V2)
        
        # Migrate existing sessions
        cursor.execute("SELECT session_id, history_json, created_at FROM sessions")
        for session_id, history_json, created_at in cursor.fetchall():
            if history_json:
                history = json.loads(history_json)
                for idx, msg in enumerate(history):
                    cursor.execute("""
                        INSERT INTO messages 
                        (session_id, role, content, tokens, message_index, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        msg.get('role', 'user'),
                        msg.get('content', ''),
                        len(msg.get('content', '')) // 4,
                        idx,
                        created_at
                    ))
        
        # Mark as upgraded
        cursor.execute("""
            INSERT OR REPLACE INTO schema_metadata (key, value) 
            VALUES ('version', '2')
        """)
        
        conn.commit()
```

**Testing:**
- Test migration with empty database
- Test migration with single session
- Test migration with multiple sessions
- Test migration with large history (100+ messages)
- Test migration with malformed JSON (should skip gracefully)
- Verify data integrity after migration

#### Task 2.3: Update Database API Methods

**File:** `ollama_prompt/session_db.py`

**Requirements:**
- Add methods for working with new tables
- Update existing methods to use structured tables instead of JSON
- Maintain backward compatibility during transition

**Acceptance Criteria:**
- [ ] `save_message()` inserts into `messages` table
- [ ] `load_session()` reads from `messages` table
- [ ] `track_file_reference()` inserts into `file_references` table
- [ ] `get_session_messages()` returns messages in order
- [ ] All methods handle missing data gracefully

**New Methods:**

```python
def save_message(self, session_id: str, role: str, content: str, tokens: int) -> int:
    """Save a message and return message_id."""
    
def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
    """Get all messages for a session."""
    
def track_file_reference(self, session_id: str, message_id: int, file_path: str, mode: str, tokens: int):
    """Track a file reference."""
    
def get_file_references(self, session_id: str) -> List[Dict]:
    """Get all file references for a session."""
    
def update_session_tokens(self, session_id: str, tokens: int):
    """Update current token count for session."""
```

**Testing:**
- Unit tests for each new method
- Integration tests with real sessions
- Test concurrent access (multiple sessions)

### Deliverables

- [ ] Updated `ollama_prompt/session_db.py` (~400 lines changed/added)
- [ ] Migration tests in `tests/test_migration.py` (new file, ~150 lines)
- [ ] Updated unit tests in `tests/test_session_db.py` (~100 lines added)
- [ ] Migration guide in `docs/MIGRATION.md` (new file)

### Success Metrics

- **Migration success rate:** 100% for valid databases
- **Migration time:** < 5 seconds for 100 sessions
- **Data integrity:** 100% of messages preserved
- **Backward compatibility:** Old code still works during transition

---

## Phase 3: Automatic Context Management

**Duration:** 5-6 days  
**Priority:** High  
**Dependencies:** Phase 2 (database schema)  
**Deliverable:** Self-managing context window with graduated compaction

### Overview

Implement automatic context window management that monitors usage and applies appropriate compaction strategies without user intervention.

### Tasks

#### Task 3.1: Create `context_manager.py` Module

**File:** `ollama_prompt/context_manager.py`

**Requirements:**
- Implement `ContextManager` class with automatic decision logic
- Support three compaction levels (soft, hard, emergency)
- Track token usage and trigger compaction automatically
- Integrate with database for persistence

**Acceptance Criteria:**
- [ ] Automatically triggers compaction at correct thresholds
- [ ] Implements all three compaction levels
- [ ] Respects cooldown period between compactions
- [ ] Records compaction history in database
- [ ] Provides status reporting

**Implementation Details:**

```python
class ContextManager:
    """Automatic context window manager."""
    
    def __init__(self, max_tokens: int = 16000):
        self.max_tokens = max_tokens
        self.current_tokens = 0
        self.messages = []
        self.file_references = {}
        
        # Thresholds (based on Manus context engineering best practices)
        self.SOFT_THRESHOLD = 0.50  # Start compacting early to prevent context rot
        self.HARD_THRESHOLD = 0.65  # More aggressive to maintain reasoning quality
        self.EMERGENCY_THRESHOLD = 0.80  # Leave headroom before hitting limits
    
    def add_message(self, role: str, content: str, file_refs: List[str] = None):
        """Add message and automatically compact if needed."""
        # Add message
        # Update token count
        # Check if compaction needed
        # Apply compaction if needed
    
    def _auto_compact(self):
        """Automatic decision engine."""
        usage = self.current_tokens / self.max_tokens
        level = self._determine_compaction_level(usage)
        
        if level == 1:
            self._soft_compact()
        elif level == 2:
            self._hard_compact()
        elif level == 3:
            self._emergency_compact()
    
    def _soft_compact(self) -> int:
        """Level 1: Recompress stale files."""
        
    def _hard_compact(self) -> int:
        """Level 2: Remove low-relevance messages."""
        
    def _emergency_compact(self) -> int:
        """Level 3: Aggressive pruning with LLM summary."""
```

**Testing:**
- Unit tests for each compaction level
- Test threshold detection
- Test cooldown logic
- Test token counting accuracy

#### Task 3.2: Implement Level 1 (Soft Compaction)

**File:** `ollama_prompt/context_manager.py`

**Requirements:**
- Identify files not referenced in last N messages
- Recompress full files to summaries
- Update file reference tracking
- Free tokens and update count

**Acceptance Criteria:**
- [ ] Correctly identifies stale files
- [ ] Recompresses using `FileChunker` from Phase 1
- [ ] Updates database with compression status
- [ ] Frees 30-50% of tokens
- [ ] Completes in < 500ms

**Implementation Details:**

```python
def _soft_compact(self) -> int:
    """Level 1: Recompress files not used recently."""
    tokens_freed = 0
    RECENCY_THRESHOLD = 3
    
    for file_path, info in self.file_references.items():
        if info['mode'] == 'full':
            messages_since = current_index - info['last_message_index']
            if messages_since >= RECENCY_THRESHOLD:
                tokens_freed += self._compress_file(file_path)
    
    return tokens_freed
```

**Testing:**
- Test with various file reference patterns
- Verify token savings
- Test with no files to compress
- Test with all files stale

#### Task 3.3: Implement Level 2 (Hard Compaction)

**File:** `ollama_prompt/context_manager.py`

**Requirements:**
- Score messages by relevance to current query
- Keep top 50% most relevant messages
- Always preserve recent messages (last 5)
- Use lightweight vector scoring

**Acceptance Criteria:**
- [ ] Generates embeddings for messages
- [ ] Calculates cosine similarity correctly
- [ ] Keeps most relevant messages
- [ ] Preserves recent messages
- [ ] Frees 50-70% of tokens
- [ ] Completes in < 2 seconds

**Implementation Details:**

```python
def _hard_compact(self) -> int:
    """Level 2: Remove low-relevance messages."""
    KEEP_RECENT = 5
    
    recent = self.messages[-KEEP_RECENT:]
    old = self.messages[:-KEEP_RECENT]
    
    # Score by relevance
    current_query = self._get_current_query()
    scored = self._score_messages_by_relevance(old, current_query)
    
    # Keep top 50%
    keep_count = len(scored) // 2
    keep = [msg for score, msg in scored[:keep_count]]
    
    self.messages = keep + recent
    return tokens_freed
```

**Testing:**
- Test with various conversation patterns
- Verify relevance scoring works
- Test with short conversations (< 5 messages)
- Measure performance

#### Task 3.4: Implement Level 3 (Emergency Compaction)

**File:** `ollama_prompt/context_manager.py`

**Requirements:**
- Compress ALL files to summaries
- Keep only last 2 exchanges (4 messages)
- Use LLM to summarize rest of conversation
- Add user notification

**Acceptance Criteria:**
- [ ] Compresses all files
- [ ] Generates intelligent summary with LLM
- [ ] Preserves critical information
- [ ] Frees 70-85% of tokens
- [ ] Completes in < 5 seconds

**Implementation Details:**

```python
def _emergency_compact(self) -> int:
    """Level 3: Aggressive pruning."""
    tokens_freed = 0
    
    # Compress all files
    for file_path in self.file_references:
        tokens_freed += self._compress_file(file_path)
    
    # Ultra-compress history
    KEEP_RECENT = 4
    old = self.messages[:-KEEP_RECENT]
    summary = self._generate_llm_summary(old)
    
    self.messages = [summary_message] + self.messages[-KEEP_RECENT:]
    
    return tokens_freed
```

**Testing:**
- Test with critically full context
- Verify summary quality
- Test LLM failure fallback
- Measure token savings

#### Task 3.5: Integrate with Session Manager

**File:** `ollama_prompt/session_manager.py`

**Requirements:**
- Replace manual context management with `ContextManager`
- Load session into `ContextManager` on resume
- Save compaction events to database
- Update token counts in database

**Acceptance Criteria:**
- [ ] Sessions use `ContextManager` automatically
- [ ] Compaction events are persisted
- [ ] Token counts stay accurate
- [ ] Works with existing sessions

**Implementation Details:**

```python
class SessionManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db = SessionDatabase(db_path)
        self.context_manager = ContextManager(max_tokens=16000)
    
    def prepare_prompt(self, session_id: str, new_prompt: str) -> str:
        """Prepare prompt with automatic context management."""
        # Load session
        messages = self.db.get_session_messages(session_id)
        self.context_manager.load_messages(messages)
        
        # Add new prompt
        self.context_manager.add_message('user', new_prompt)
        
        # Build final prompt
        return self.context_manager.build_prompt()
```

**Testing:**
- Integration tests with real sessions
- Test session resume after compaction
- Test multiple sessions concurrently
- Verify database updates

### Deliverables

- [ ] `ollama_prompt/context_manager.py` (new file, ~500 lines)
- [ ] Updated `ollama_prompt/session_manager.py` (~150 lines changed)
- [ ] Unit tests in `tests/test_context_manager.py` (new file, ~300 lines)
- [ ] Integration tests in `tests/test_session_integration.py` (~100 lines added)
- [ ] User documentation in `docs/CONTEXT_MANAGEMENT.md` (new file)

### Success Metrics

- **Token savings:** 60-85% depending on level
- **Conversation length:** 50-100+ messages (vs. 10-15 before)
- **Files per session:** 10-20 (vs. 2-3 before)
- **User intervention:** 0 (fully automatic)
- **Performance:** < 2 seconds for any compaction level

---

## Phase 4: Semantic Search with Embeddings

**Duration:** 4-5 days  
**Priority:** Medium  
**Dependencies:** Phase 2 (database), Phase 3 (context manager)  
**Deliverable:** Vector-based semantic search for intelligent compaction

### Overview

Implement embedding generation and semantic search to enable intelligent message relevance scoring for Level 2 compaction.

### Tasks

#### Task 4.1: Create `vector_search.py` Module

**File:** `ollama_prompt/vector_search.py`

**Requirements:**
- Implement `LightweightVectorScorer` class
- Generate embeddings using Ollama's `nomic-embed-text`
- Calculate cosine similarity
- Cache embeddings for performance

**Acceptance Criteria:**
- [ ] Generates embeddings correctly
- [ ] Calculates cosine similarity accurately
- [ ] Caches embeddings to avoid recomputation
- [ ] Handles embedding failures gracefully
- [ ] Completes embedding generation in < 500ms

**Implementation Details:**

```python
class LightweightVectorScorer:
    """Simple vector-based relevance scoring."""
    
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        self.embedding_model = embedding_model
        self.cache = {}
    
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        # Check cache
        # Generate with ollama.embeddings()
        # Cache and return
    
    def score_relevance(self, text: str, reference_embedding: np.ndarray) -> float:
        """Score relevance using cosine similarity."""
        text_embedding = self.embed(text)
        return cosine_similarity(text_embedding, reference_embedding)
    
    def rank_messages(self, messages: List[Dict], query: str) -> List[Tuple[float, Dict]]:
        """Rank messages by relevance to query."""
```

**Testing:**
- Test embedding generation
- Test similarity calculation
- Test caching behavior
- Test with various text lengths

#### Task 4.2: Integrate with Database

**File:** `ollama_prompt/session_db.py`

**Requirements:**
- Add methods to store embeddings in database
- Add methods to retrieve embeddings
- Store as BLOB for efficiency
- Link embeddings to messages

**Acceptance Criteria:**
- [ ] Can store embeddings as BLOB
- [ ] Can retrieve embeddings by message_id
- [ ] Handles missing embeddings gracefully
- [ ] Efficient storage (no duplication)

**New Methods:**

```python
def store_embedding(self, entity_type: str, entity_id: int, embedding: np.ndarray, model: str):
    """Store embedding in database."""
    
def get_embedding(self, entity_type: str, entity_id: int) -> Optional[np.ndarray]:
    """Retrieve embedding from database."""
    
def get_embeddings_for_session(self, session_id: str) -> Dict[int, np.ndarray]:
    """Get all embeddings for a session."""
```

**Testing:**
- Test storage and retrieval
- Test with various embedding sizes
- Test with missing embeddings
- Verify BLOB encoding/decoding

#### Task 4.3: Integrate with Context Manager

**File:** `ollama_prompt/context_manager.py`

**Requirements:**
- Use `LightweightVectorScorer` in Level 2 compaction
- Generate embeddings for new messages
- Store embeddings in database
- Use cached embeddings when available

**Acceptance Criteria:**
- [ ] Level 2 compaction uses vector scoring
- [ ] Embeddings are generated and cached
- [ ] Relevance scoring improves message selection
- [ ] Performance is acceptable (< 2 seconds)

**Implementation Details:**

```python
def _hard_compact(self) -> int:
    """Level 2: Use vector-based relevance scoring."""
    if self._vector_scorer is None:
        self._vector_scorer = LightweightVectorScorer()
    
    current_query = self._get_current_query()
    scored = self._score_messages_by_relevance(old_messages, current_query)
    
    # Keep top 50%
    keep = [msg for score, msg in scored[:len(scored)//2]]
    return tokens_freed
```

**Testing:**
- Test with various conversation patterns
- Compare with random selection (should be better)
- Measure performance impact
- Test with embedding failures (should fallback)

#### Task 4.4: Add Optional sqlite-vec Support

**File:** `ollama_prompt/vector_search.py`

**Requirements:**
- Detect if `sqlite-vec` extension is available
- Use native vector search if available
- Fallback to manual cosine similarity if not
- Document installation instructions

**Acceptance Criteria:**
- [ ] Detects `sqlite-vec` availability
- [ ] Uses native search when available
- [ ] Falls back gracefully when not available
- [ ] Performance improves with native search

**Implementation Details:**

```python
try:
    import sqlite_vec
    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    VECTOR_SEARCH_AVAILABLE = False

class VectorSearchEngine:
    def __init__(self, conn):
        if VECTOR_SEARCH_AVAILABLE:
            self._init_native_search(conn)
        else:
            self._init_fallback_search()
```

**Testing:**
- Test with and without sqlite-vec
- Verify fallback works
- Measure performance difference
- Document installation

### Deliverables

- [ ] `ollama_prompt/vector_search.py` (new file, ~200 lines)
- [ ] Updated `ollama_prompt/session_db.py` (~100 lines added)
- [ ] Updated `ollama_prompt/context_manager.py` (~50 lines changed)
- [ ] Unit tests in `tests/test_vector_search.py` (new file, ~150 lines)
- [ ] Documentation in `docs/VECTOR_SEARCH.md` (new file)

### Success Metrics

- **Embedding generation:** < 500ms per message
- **Similarity search:** < 100ms for 100 messages
- **Relevance accuracy:** 80%+ (measured by user feedback)
- **Cache hit rate:** > 70% in typical usage

---

## Testing Strategy

### Unit Tests

Each module must have comprehensive unit tests covering:
- All public methods
- Edge cases (empty input, invalid input, etc.)
- Error handling
- Performance benchmarks

**Target Coverage:** 80%+

### Integration Tests

Test interactions between modules:
- File chunker + CLI integration
- Context manager + database integration
- Session manager + context manager integration
- End-to-end conversation flow

### Performance Tests

Measure and validate:
- File summarization time (< 100ms)
- Compaction time (< 2 seconds)
- Embedding generation (< 500ms)
- Database query time (< 50ms)

### Regression Tests

Ensure backward compatibility:
- Old sessions still load correctly
- Existing CLI syntax still works
- Database migration preserves data
- No breaking changes to API

### User Acceptance Tests

Manual testing scenarios:
- Long conversation (50+ messages)
- Multiple file references (10+ files)
- Large files (> 100KB)
- Context window fills up (automatic compaction)
- Session resume after compaction

---

## Deployment Plan

### Pre-Deployment Checklist

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Migration tested on real databases
- [ ] Backward compatibility verified
- [ ] Code review completed

### Deployment Steps

1. **Merge to main branch**
   - Create PR for each phase
   - Code review by team
   - Merge after approval

2. **Version bump**
   - Phase 1: v0.2.0 (minor feature)
   - Phase 2: v0.3.0 (database upgrade)
   - Phase 3: v0.4.0 (context management)
   - Phase 4: v0.5.0 (semantic search)

3. **Release to PyPI**
   ```bash
   python -m build
   twine upload dist/*
   ```

4. **Update documentation**
   - README.md with new features
   - CHANGELOG.md with changes
   - Migration guide for existing users

5. **Announce release**
   - GitHub release notes
   - Update project description

### Rollback Plan

If issues are discovered:

1. **Immediate:** Revert to previous version on PyPI
2. **Database:** Users can manually delete `sessions.db` to start fresh
3. **Code:** Revert commits and redeploy
4. **Communication:** Update release notes with known issues

---

## Risk Management

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Migration fails for some users** | Medium | High | Extensive testing, graceful error handling, backup old data |
| **Performance degradation** | Low | Medium | Performance benchmarks, optimization before release |
| **Embedding generation too slow** | Medium | Medium | Caching, optional feature, fallback to simpler methods |
| **SQLite limitations** | Low | Low | SQLite handles our scale easily, can upgrade later if needed |
| **Breaking changes** | Low | High | Maintain backward compatibility, version detection |

### Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Phase takes longer than estimated** | Medium | Medium | Phases are independent, can delay later phases |
| **Team member unavailable** | Low | Medium | Good documentation, code reviews, knowledge sharing |
| **Dependency issues** | Low | Low | Minimal external dependencies, all in Python stdlib |

### User Impact Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Users don't understand new features** | Medium | Low | Clear documentation, examples, default to safe behavior |
| **Automatic compaction too aggressive** | Low | Medium | Conservative thresholds, user can disable, logging |
| **Data loss during migration** | Low | High | Extensive testing, backup old data, migration logs |

---

## Success Criteria

### Technical Metrics

- [ ] Context window usage reduced by 60-90%
- [ ] Conversation length increased to 50-100+ messages
- [ ] Files per session increased to 10-20
- [ ] All tests passing (80%+ coverage)
- [ ] Performance benchmarks met
- [ ] Zero data loss in migration

### User Metrics

- [ ] No user-reported migration failures
- [ ] Positive feedback on context management
- [ ] Reduced "context window full" errors
- [ ] Increased usage of file references

### Business Metrics

- [ ] Successful PyPI release
- [ ] No critical bugs in first week
- [ ] Documentation complete and accurate
- [ ] Team can maintain and extend code

---

## Timeline Summary

| Phase | Duration | Start | End | Dependencies |
|-------|----------|-------|-----|--------------|
| **Phase 1: File Chunking** | 4-5 days | Day 1 | Day 5 | None |
| **Phase 2: Database Upgrade** | 3-4 days | Day 1 | Day 4 | None (parallel) |
| **Phase 3: Context Manager** | 5-6 days | Day 6 | Day 11 | Phase 2 |
| **Phase 4: Semantic Search** | 4-5 days | Day 12 | Day 16 | Phase 2, 3 |
| **Testing & Polish** | 3-4 days | Day 17 | Day 20 | All phases |
| **Total** | **19-24 days** | Day 1 | Day 20-24 | - |

**Estimated completion:** 3-4 weeks with one developer, 2-3 weeks with two developers

---

## Resources Required

### Development Team

- **1-2 Python developers** with experience in:
  - Python 3.10+
  - SQLite
  - AST parsing
  - Vector embeddings (nice to have)

### Tools & Infrastructure

- **Development environment:** Python 3.10+, pip, git
- **Testing:** pytest, coverage
- **Database:** SQLite 3.35+ (built into Python)
- **Embeddings:** Ollama with `nomic-embed-text` model
- **CI/CD:** GitHub Actions (already set up)

### Documentation

- **Code comments:** Inline documentation for complex logic
- **Docstrings:** All public methods and classes
- **User docs:** README.md, migration guide, feature docs
- **Developer docs:** Architecture overview, testing guide

---

## Appendix: Reference Documents

The following documents provide detailed technical specifications and should be reviewed by the development team:

1. **`chunking_strategy.md`** - Complete file chunking and summarization strategy
2. **`context_compaction_strategy.md`** - Detailed context management and compaction logic
3. **`database_upgrade_strategy.md`** - Database schema design and migration plan
4. **`context_manager_implementation.py`** - Reference implementation of context manager
5. **`decision_flow.md`** - Automatic decision flow for compaction

These documents are attached to this implementation plan and should be distributed to the team.

---

## Questions & Support

For questions or clarifications during implementation:

1. **Technical questions:** Review reference documents first
2. **Design decisions:** Refer to this implementation plan
3. **Ambiguities:** Document assumptions and proceed, flag for review
4. **Blockers:** Escalate immediately to project lead

**Project Lead:** [Your Name]  
**Start Date:** [To be determined]  
**Target Completion:** [Start Date + 3-4 weeks]

---

**End of Implementation Plan**
