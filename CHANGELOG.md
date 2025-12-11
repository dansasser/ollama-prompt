# Changelog

All notable changes to ollama-prompt will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Intelligent Context Window Management (In Progress)
- **FileChunker module** - Smart file summarization with 90%+ token savings
  - Python AST parsing for class/function extraction
  - Markdown section-based summarization
  - Generic line-count fallback for other file types
- **Enhanced file reference syntax:**
  - `@./file.py` - Auto-summary for files >5KB (NEW DEFAULT)
  - `@./file.py:full` - Full content (old behavior)
  - `@./file.py:function_name` - Extract specific function/class
  - `@./file.py:lines:100-150` - Extract line range
- **3-Level automatic compaction:**
  - Level 1 (50%): Soft compaction - recompress stale files
  - Level 2 (65%): Hard compaction - prune low-relevance messages
  - Level 3 (80%): Emergency compaction - LLM-based summarization
- **Structured message storage** - Enables selective pruning vs blob truncation
- **Compaction audit trail** - Track all compaction events for debugging

#### Directory Syntax for File References
- **New directory operations** using `@` syntax in prompts:
  - `@./dir/` or `@./dir/:list` - List directory contents
  - `@./dir/:tree` - Show directory tree (depth=3)
  - `@./dir/:search:PATTERN` - Search for pattern in files
- Directory listings show `[DIR]` and `[FILE]` markers with sizes
- Tree view uses ASCII art for hierarchical display
- Search shows file:line:content for each match
- All operations use secure llm-fs-tools backend
- 17 new tests for directory syntax

### Changed

#### Security: Migrated to llm-fs-tools Package
- **Replaced local `secure_file.py`** with `llm-fs-tools` package dependency
- All secure file operations now use production-ready, shared implementation
- Benefits:
  - TOCTOU-safe file reading with fd-based validation
  - Cross-platform secure open (O_NOFOLLOW on Unix, GetFinalPathNameByHandle on Windows)
  - Symlink blocking, device file rejection, path traversal prevention
  - Shared security implementation between ollama-prompt and other projects

### Breaking Changes

#### Python 3.10+ Required
- **Minimum Python version raised from 3.7 to 3.10**
- Reason: The new `llm-fs-tools` dependency requires Python 3.10+
- Users on Python 3.7-3.9 must upgrade Python to use ollama-prompt v1.2.0+

### Removed
- `ollama_prompt/secure_file.py` (418 lines) - replaced by llm-fs-tools

### Dependencies
- Added: `llm-fs-tools>=0.1.0` (requires Python 3.10+)

### Testing
- Updated `tests/test_secure_file.py` to use llm-fs-tools imports
- Skipped `TestHardlinkDetection` (check_hardlinks not in llm-fs-tools)
- Added `tests/test_directory_syntax.py` with 17 tests
- Added `tests/test_file_chunker.py` with 30 tests
- Added `tests/test_session_db_v2.py` with 38 tests
- Added `tests/test_context_manager.py` with 33 tests
- Added `tests/test_vector_embedder.py` with 36 tests
- 204 tests passing, 7 skipped

### Database Schema (In Progress)

#### New Tables
- **messages** - Structured message storage (replaces JSON blob)
- **file_references** - Track file usage per message
- **compaction_history** - Audit trail for compaction events
- **schema_version** - Enable automatic migrations

#### Migration
- Automatic V1 to V2 migration on first connect
- Backup created before migration
- Backward compatible (old sessions still work)

### New Modules
- `ollama_prompt/file_chunker.py` - Smart file summarization (~530 LOC)
- `ollama_prompt/context_manager.py` - Automatic compaction (~600 LOC)
- `ollama_prompt/vector_embedder.py` - Semantic relevance scoring (~300 LOC)

---

## [1.2.0] - 2025-10-31

### Added

#### Session Management System
- **Persistent conversation sessions** with automatic context management
- Sessions auto-create on first prompt (no manual flag needed!)
- Context persists across multiple CLI invocations
- Local SQLite database storage (no cloud dependency)

#### Session Flags
- `--session-id <id>` - Continue existing session with full context
- `--no-session` - Stateless mode for one-off queries
- `--max-context-tokens <num>` - Configure context window (default: 64,000 tokens)

#### Session Utility Commands
- `--list-sessions` - List all stored sessions with metadata
- `--session-info <id>` - Show detailed session information
- `--purge <days>` - Remove sessions older than specified days

#### Storage & Performance
- **Dual storage strategy:** JSON messages + cached plain text
- **Smart context pruning:** Automatically removes old messages at 90% capacity
- **Token estimation:** ~4 characters = 1 token
- **Cross-platform database:** Windows, Linux, Mac support
  - Windows: `%APPDATA%\ollama-prompt\sessions.db`
  - Linux/Mac: `~/.config/ollama-prompt/sessions.db`

#### Configuration
- `OLLAMA_PROMPT_MAX_CONTEXT_TOKENS` - Set default context limit via environment
- `OLLAMA_PROMPT_DB_PATH` - Override database location

#### Documentation
- `docs/session_management.md` - Comprehensive session management guide
- `examples/session_usage.py` - Practical Python examples for all use cases
- Updated `README.md` with session management quick start

#### Testing
- 7 new context persistence tests (all passing)
- 9 CLI integration tests (all passing)
- 24 database layer tests (all passing)
- Total: 40 tests covering session functionality

### Changed

- CLI now outputs `session_id` field in JSON response when sessions are used
- `--prompt` flag is now optional (not required for utility commands)
- Help output reorganized with session management and utility command groups

### Technical Details

#### New Modules
- `ollama_prompt/session_db.py` - SQLite database abstraction layer
- `ollama_prompt/session_manager.py` - Session lifecycle management
- `ollama_prompt/session_utils.py` - Utility command handlers
- `ollama_prompt/models.py` - Data models (SessionData)

#### Database Schema
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

#### Message Storage Format
```json
{
  "messages": [
    {
      "role": "user",
      "content": "...",
      "timestamp": "2025-10-31T10:30:00",
      "tokens": 123
    },
    {
      "role": "assistant",
      "content": "...",
      "timestamp": "2025-10-31T10:30:05",
      "tokens": 456
    }
  ]
}
```

### Migration Notes

This is a **non-breaking** release:
- Existing functionality unchanged
- Sessions are opt-in (auto-created by default, but `--no-session` available)
- No action required for existing users
- Database created automatically on first use

### Use Cases

- **Multi-turn conversations** - Natural follow-up questions with context
- **Code reviews** - Review multiple files with shared understanding
- **Iterative problem-solving** - Refine solutions across prompts
- **Agent orchestration** - Maintain state across sub-agent calls

### Example Usage

```bash
# Start conversation (auto-creates session)
ollama-prompt --prompt "What is Python?"
# Output: {"session_id": "abc-123", "response": "...", ...}

# Continue conversation
ollama-prompt --prompt "Show me an example" --session-id abc-123
# Context from first question automatically included!

# Quick lookup (no session)
ollama-prompt --prompt "What is 2+2?" --no-session
```

---

## [1.1.6] - Previous Release

### Added
- Thinking mode support with `--think` flag for compatible models
- File reference inlining with `@path` syntax
- Cross-platform path handling (Unix and Windows)

### Features
- Custom temperature, max tokens, model selection
- Full JSON output with token counts and timings
- Repository root configuration for file references
- File size limits with truncation markers

---

## Future Roadmap

### v1.3.0 (In Development)
- Intelligent context window management
- Smart file summarization (FileChunker)
- 3-level automatic compaction
- Structured message storage
- Optional vector-based relevance scoring

### Future Releases
- MongoDB adapter for distributed deployments
- Session export/import functionality
- Advanced analytics and session metrics
- Multi-user session management
- Session sharing and collaboration features

---

For complete documentation, see:
- [README.md](README.md) - Quick start and overview
- [docs/session_management.md](docs/session_management.md) - Comprehensive guide
- [examples/session_usage.py](examples/session_usage.py) - Practical examples
