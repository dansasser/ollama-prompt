# ollama-prompt Context Management Implementation Roadmap

**Created:** 2025-12-10
**Based on:** Gap Analysis by ollama-task-router
**Target:** MVP with automatic context compaction

---

## Executive Summary

Implement intelligent context window management for ollama-prompt in 4 phases, targeting an MVP in ~2 weeks that delivers:
- Smart file summarization (95% token savings on large files)
- Structured message storage (enables selective pruning)
- Automatic 3-level compaction (50/65/80% thresholds)
- Optional vector-based relevance scoring

---

## Phase 1: FileChunker Module (Days 1-3)

**Goal:** Replace full file dumps with intelligent summaries

### 1.1 Create FileChunker Class
**File:** `ollama_prompt/file_chunker.py`
**LOC:** ~300

```
Components:
- summarize_python() - AST-based Python file analysis
- summarize_markdown() - Section-based markdown parsing
- summarize_generic() - Line-count based fallback
- extract_element() - Extract specific function/class by name
- extract_lines() - Extract line range
- format_summary() - Convert summary dict to model-friendly text
```

**Deliverables:**
- [ ] FileChunker class with Python AST parsing
- [ ] Markdown section extraction
- [ ] Generic file summarization fallback
- [ ] Element extraction (function/class by name)
- [ ] Line range extraction
- [ ] Unit tests for all methods

### 1.2 Integrate with CLI
**File:** `ollama_prompt/cli.py` (modify `expand_file_refs_in_prompt`)

**New syntax support:**
- `@./file.py` - Summary (NEW DEFAULT for files >5KB)
- `@./file.py:full` - Full content (old behavior)
- `@./file.py:function_name` - Extract specific function/class
- `@./file.py:lines:100-150` - Extract line range
- `@./file.py:summary` - Force summary mode

**Deliverables:**
- [ ] Update regex pattern to capture mode suffix
- [ ] Add mode routing logic
- [ ] Integrate FileChunker calls
- [ ] Add size threshold check (5KB default)
- [ ] Update help text

### 1.3 Testing
**File:** `tests/test_file_chunker.py`

- [ ] Test Python AST extraction (classes, functions, imports)
- [ ] Test Markdown section parsing
- [ ] Test element extraction by name
- [ ] Test line range extraction
- [ ] Test CLI syntax parsing
- [ ] Integration tests with real files

---

## Phase 2: Database Schema Upgrade (Days 4-6)

**Goal:** Enable structured message storage for selective compaction

### 2.1 Design New Schema
**File:** `ollama_prompt/session_db.py` (extend)

**New tables:**
```sql
-- Structured message storage
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    is_summary BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Track file references per message
CREATE TABLE file_references (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    mode TEXT NOT NULL,  -- 'full', 'summary', 'extract'
    tokens INTEGER NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- Compaction audit trail
CREATE TABLE compaction_history (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level INTEGER NOT NULL,  -- 1, 2, 3
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_freed INTEGER NOT NULL,
    strategy TEXT NOT NULL,  -- 'file_compress', 'message_prune', 'llm_summary'
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Schema version tracking
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    upgraded_at TEXT NOT NULL
);
```

**Deliverables:**
- [ ] Add schema version table
- [ ] Add messages table
- [ ] Add file_references table
- [ ] Add compaction_history table
- [ ] Create indexes for performance

### 2.2 Migration Logic
**File:** `ollama_prompt/session_db.py` (extend)

**Methods:**
- `_get_schema_version()` - Check current version
- `_upgrade_schema()` - Run migrations
- `_migrate_v1_to_v2()` - Convert JSON blobs to structured messages

**Deliverables:**
- [ ] Schema version detection
- [ ] Automatic upgrade on connect
- [ ] V1 to V2 migration (parse JSON blobs)
- [ ] Backup before migration
- [ ] Migration tests

### 2.3 New API Methods
**File:** `ollama_prompt/session_db.py` (extend)

**Methods:**
- `save_message()` - Insert structured message
- `load_messages()` - Load messages for session
- `get_message_tokens()` - Get token count for session
- `delete_messages()` - Delete specific messages by ID
- `track_file_reference()` - Record file usage
- `get_stale_files()` - Find files not used in N messages
- `record_compaction()` - Log compaction event

**Deliverables:**
- [ ] Message CRUD operations
- [ ] File reference tracking
- [ ] Compaction history logging
- [ ] Query methods for compaction decisions
- [ ] Unit tests for all methods

---

## Phase 3: Context Manager (Days 7-10)

**Goal:** Automatic compaction with 3-level graduated response

### 3.1 Create ContextManager Class
**File:** `ollama_prompt/context_manager.py`
**LOC:** ~400

**Core logic:**
```python
class ContextManager:
    SOFT_THRESHOLD = 0.50    # 50% - Compress stale files
    HARD_THRESHOLD = 0.65    # 65% - Prune low-relevance messages
    EMERGENCY_THRESHOLD = 0.80  # 80% - LLM summarization

    def add_message() -> None
    def _auto_compact() -> None
    def _determine_level() -> int
    def _soft_compact() -> int      # Level 1: File recompression
    def _hard_compact() -> int      # Level 2: Message pruning
    def _emergency_compact() -> int # Level 3: LLM summary
```

**Deliverables:**
- [ ] ContextManager class skeleton
- [ ] Threshold constants (50/65/80)
- [ ] Usage calculation
- [ ] Level determination logic
- [ ] Cooldown tracking (prevent thrashing)

### 3.2 Level 1: Soft Compaction
**Rule-based file recompression**

**Logic:**
1. Find files in 'full' mode not referenced in last 3 messages
2. Replace full content with FileChunker summary
3. Update file_references table

**Deliverables:**
- [ ] Stale file detection
- [ ] In-place content replacement
- [ ] Token recalculation
- [ ] File reference mode update

### 3.3 Level 2: Hard Compaction
**Relevance-based message pruning**

**Logic:**
1. Score old messages by relevance to current query
2. Keep top 50% most relevant + last 5 messages
3. Delete low-relevance messages

**MVP approach (no vectors):**
- Use keyword overlap scoring
- Prioritize messages with file references
- Prioritize messages with code blocks

**Deliverables:**
- [ ] Simple relevance scoring (keyword-based)
- [ ] Message selection logic
- [ ] Safe deletion (keep recent)
- [ ] Token accounting

### 3.4 Level 3: Emergency Compaction
**LLM-based summarization**

**Logic:**
1. Compress ALL files to summaries
2. Keep only last 2 exchanges (4 messages)
3. Use small model to summarize older history
4. Replace old messages with summary message

**Deliverables:**
- [ ] Bulk file compression
- [ ] Message aggregation for summary prompt
- [ ] LLM summary generation (llama3.2:3b)
- [ ] History reconstruction with summary

### 3.5 Integration with SessionManager
**File:** `ollama_prompt/session_manager.py` (modify)

**Changes:**
- Replace simple pruning with ContextManager
- Hook into message add flow
- Pass compaction events to context manager

**Deliverables:**
- [ ] Replace `_prune_if_needed()` calls
- [ ] Initialize ContextManager per session
- [ ] Wire up automatic compaction
- [ ] Integration tests

---

## Phase 4: Vector Embeddings (Days 11-13) - OPTIONAL

**Goal:** Semantic relevance scoring for Level 2 compaction

### 4.1 VectorEmbedder Class
**File:** `ollama_prompt/vector_embedder.py`
**LOC:** ~200

**Methods:**
- `embed()` - Generate embedding using nomic-embed-text
- `cosine_similarity()` - Compare two embeddings
- `score_relevance()` - Score text against query embedding
- `batch_embed()` - Embed multiple texts efficiently

**Deliverables:**
- [ ] Ollama embedding integration
- [ ] Embedding caching (MD5 key)
- [ ] Cosine similarity with zero-norm protection
- [ ] Batch processing

### 4.2 Database Integration
**File:** `ollama_prompt/session_db.py` (extend)

**New table:**
```sql
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);
```

**Deliverables:**
- [ ] Embeddings table
- [ ] Store/retrieve embedding BLOBs
- [ ] Lazy embedding generation

### 4.3 Upgrade Level 2 Compaction
**File:** `ollama_prompt/context_manager.py` (modify)

**Changes:**
- Replace keyword scoring with vector scoring
- Lazy-load VectorEmbedder only when needed
- Fall back to keyword scoring if embedding fails

**Deliverables:**
- [ ] Vector scorer integration
- [ ] Graceful fallback
- [ ] Performance optimization

---

## Testing Strategy

### Unit Tests
- `tests/test_file_chunker.py` - FileChunker methods
- `tests/test_session_db_v2.py` - New schema and migrations
- `tests/test_context_manager.py` - Compaction logic
- `tests/test_vector_embedder.py` - Embedding operations

### Integration Tests
- `tests/test_compaction_integration.py` - End-to-end compaction
- `tests/test_migration.py` - V1 to V2 upgrade

### Manual Testing
- Large file handling (>50KB)
- Multi-file conversations
- Long conversation compaction
- Session restore after compaction

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Data loss during migration | Automatic backup before upgrade |
| Compaction thrashing | Cooldown period (2 messages minimum) |
| LLM summary quality | Use structured prompt, validate output |
| Embedding model unavailable | Fallback to keyword scoring |
| Performance degradation | Lazy loading, caching, batch operations |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Token savings on large files | >90% |
| Context window utilization | Stay under 80% |
| Compaction latency | <2 seconds for Level 1-2 |
| Migration success rate | 100% (with backup) |
| Test coverage | >80% |

---

## Timeline Summary

| Phase | Days | Cumulative |
|-------|------|------------|
| Phase 1: FileChunker | 3 | 3 |
| Phase 2: Database | 3 | 6 |
| Phase 3: Context Manager | 4 | 10 |
| Phase 4: Vectors (optional) | 3 | 13 |
| Buffer/Polish | 2 | 15 |

**MVP Target:** Day 10 (Phases 1-3 complete)
**Full Feature:** Day 15 (includes vectors)
