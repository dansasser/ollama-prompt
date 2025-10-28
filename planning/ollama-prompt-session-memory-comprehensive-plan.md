# Comprehensive Implementation Plan: ollama-prompt Session Memory

**Generated:** 2025-10-26
**Target Branch:** feat/add-think-flag
**Repository:** dansasser/ollama-prompt
**Method:** CAL (Context Arbitration Layer) Multi-Agent Analysis

---

## Executive Summary

This plan provides a complete roadmap for adding session memory capabilities to ollama-prompt, enabling persistent context across CLI invocations. The implementation uses SQLite as the default database with optional MongoDB support, maintains backward compatibility, and follows a 5-phase approach spanning 14-20 days.

**Key Features:**
- Session-based context persistence with automatic pruning
- Cross-platform SQLite storage (Windows/Linux/Mac)
- CLI session management commands
- Token-aware context window management
- Optional MongoDB backend for teams/cloud deployments
- Zero breaking changes to existing functionality

---

## Architecture Overview

### Current State Analysis

**CLI Framework:** argparse (lines 70-78 in cli.py)
**API Integration:** ollama.generate() call at line 97
**Current Flags:**
```python
--prompt (required)
--model (default: deepseek-v3.1:671b-cloud)
--temperature (default: 0.1)
--max_tokens (default: 2048)
--repo-root (default: '.')
--max-file-bytes
--think (NEW in feat/add-think-flag)
```

**Ollama API Model:** Stateless - client must provide full context with each request

### Target Architecture

```
┌─────────────────────────────────────────────────────┐
│ CLI Layer (cli.py)                                  │
│ - Parse session flags                               │
│ - Route to session commands vs prompt execution     │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│ Session Manager (session_manager.py)               │
│ - SessionManager class                              │
│ - create_or_load_session()                          │
│ - update_session_context()                          │
│ - Session lifecycle management                      │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│ Database Abstraction (session_db.py)               │
│ - SQLite adapter (default)                          │
│ - MongoDB adapter (optional)                        │
│ - Connection pooling                                │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│ Storage Layer                                       │
│ - SQLite: ~/.ollama-prompt/sessions.db              │
│ - MongoDB: via OLLAMA_PROMPT_DB_URI                 │
└─────────────────────────────────────────────────────┘
```

---

## Database Design

### SQLite Schema (Default)

```sql
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
```

### Database Location

**Cross-Platform Path Resolution:**
```python
from pathlib import Path
import os

def get_default_db_path():
    """Get platform-appropriate database path"""
    if os.name == 'nt':  # Windows
        base = Path(os.getenv('APPDATA', Path.home()))
    else:  # Unix/Linux/Mac
        base = Path.home() / '.config'

    db_dir = base / 'ollama-prompt'
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / 'sessions.db'
```

**Environment Variable Override:**
```bash
# SQLite
export OLLAMA_PROMPT_DB_PATH="/custom/path/sessions.db"

# MongoDB (triggers MongoDB adapter)
export OLLAMA_PROMPT_DB_URI="mongodb://localhost:27017/ollama_sessions"
```

---

## CLI Integration

### New Flags (Add after line 78 in cli.py)

```python
# Session management flags
session_group = parser.add_argument_group('Session Management')
session_group.add_argument(
    '--session-id',
    help="Session ID for context persistence"
)
session_group.add_argument(
    '--new-session',
    action='store_true',
    help="Force new session creation"
)
session_group.add_argument(
    '--max-context-tokens',
    type=int,
    default=64000,
    help="Maximum tokens for session context (default: 64000)"
)

# Session utility commands
utility_group = parser.add_argument_group('Session Utilities')
utility_group.add_argument(
    '--list-sessions',
    action='store_true',
    help="List all sessions"
)
utility_group.add_argument(
    '--purge',
    type=int,
    metavar='DAYS',
    help="Purge sessions older than X days"
)
utility_group.add_argument(
    '--session-info',
    help="Show detailed information for session ID"
)
```

### Argument Validation

```python
def validate_session_args(args):
    """Validate session-related arguments"""
    # Mutual exclusivity
    if args.session_id and args.new_session:
        parser.error("Cannot use --session-id with --new-session")

    # Utility commands don't require prompt
    utility_commands = [args.list_sessions, args.purge, args.session_info]
    if any(utility_commands) and not args.prompt:
        return True  # Valid utility command

    return False  # Normal prompt execution
```

### Main Execution Flow Modification

```python
def main():
    parser = argparse.ArgumentParser(...)
    # ... existing argument setup (lines 70-78) ...

    # Add session management arguments (NEW)
    # ... session flags from above ...

    args = parser.parse_args()

    # Handle utility commands first (NEW)
    if args.list_sessions:
        list_sessions()
        return

    if args.purge:
        purge_sessions(args.purge)
        return

    if args.session_info:
        show_session_info(args.session_info)
        return

    # Existing file expansion (line 80)
    try:
        prompt_with_files = expand_file_refs_in_prompt(
            args.prompt,
            args.repo_root,
            args.max_file_bytes
        )
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return

    # Session integration (NEW)
    from ollama_prompt.session_manager import SessionManager

    session_manager = SessionManager()
    session = session_manager.create_or_load_session(
        session_id=args.session_id,
        new_session=args.new_session,
        max_context_tokens=args.max_context_tokens
    )

    # Prepare prompt with session context (NEW)
    prompt_with_context = session.prepare_prompt(prompt_with_files)

    # Existing Ollama API call (line 97) - MODIFIED
    options = {
        'temperature': args.temperature,
        'num_predict': args.max_tokens
    }

    result = ollama.generate(
        model=args.model,
        prompt=prompt_with_context,  # Use session-aware prompt
        options=options,
        stream=False
    )

    # Update session context (NEW)
    session.update_context(
        user_prompt=prompt_with_files,
        assistant_response=result['response']
    )

    # Existing output (line 102)
    print(json.dumps({
        "done": True,
        "response": result['response'],
        "session_id": session.session_id  # NEW
    }))
```

---

## API Context Handling

### Integration Points

**Before API Call (Pre-Processing):**
1. Load session context from database
2. Combine session context with new prompt
3. Validate total tokens <= max_context_tokens
4. Prune if necessary

**After API Call (Post-Processing):**
1. Extract response from Ollama
2. Append to session context
3. Update session timestamp
4. Prune context if exceeds limits
5. Save updated context to database

### Context Preparation

```python
class Session:
    def prepare_prompt(self, user_prompt):
        """Prepare prompt with session context"""
        if not self.context:
            return user_prompt

        # Combine context with new prompt
        full_prompt = f"{self.context}\n\nUser: {user_prompt}\nAssistant:"

        # Check token limit
        estimated_tokens = self._estimate_tokens(full_prompt)
        if estimated_tokens > self.max_context_tokens:
            self.context = self._prune_context(
                self.context,
                self.max_context_tokens - self._estimate_tokens(user_prompt)
            )
            full_prompt = f"{self.context}\n\nUser: {user_prompt}\nAssistant:"

        return full_prompt

    def _estimate_tokens(self, text):
        """Estimate token count (4 chars ~= 1 token)"""
        return len(text) // 4

    def _prune_context(self, context, max_tokens):
        """Prune context to fit within token limit"""
        # Simple FIFO: keep most recent exchanges
        lines = context.split('\n')
        pruned = []
        current_tokens = 0

        # Work backwards to keep recent context
        for line in reversed(lines):
            line_tokens = self._estimate_tokens(line)
            if current_tokens + line_tokens > max_tokens:
                break
            pruned.insert(0, line)
            current_tokens += line_tokens

        return '\n'.join(pruned)
```

### Context Update

```python
def update_context(self, user_prompt, assistant_response):
    """Update session context after API response"""
    # Append new exchange to context
    new_exchange = f"User: {user_prompt}\nAssistant: {assistant_response}"

    if self.context:
        self.context = f"{self.context}\n\n{new_exchange}"
    else:
        self.context = new_exchange

    # Update database
    self._save_to_db()
```

---

## SessionManager Implementation

### Core Class Structure

```python
# File: src/ollama_prompt/session_manager.py

import uuid
from datetime import datetime
from typing import Optional
from .session_db import SessionDatabase

class SessionManager:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize session manager with database connection"""
        self.db = SessionDatabase(db_path)

    def create_or_load_session(
        self,
        session_id: Optional[str] = None,
        new_session: bool = False,
        max_context_tokens: int = 64000
    ) -> 'Session':
        """Create new session or load existing one"""
        if new_session or not session_id:
            session_id = str(uuid.uuid4())
            return self._create_session(session_id, max_context_tokens)

        # Try to load existing session
        session_data = self.db.get_session(session_id)
        if session_data:
            return Session.from_db(session_data, self.db)

        # Session not found, create new with specified ID
        return self._create_session(session_id, max_context_tokens)

    def _create_session(self, session_id: str, max_context_tokens: int) -> 'Session':
        """Create new session in database"""
        session_data = {
            'session_id': session_id,
            'context': '',
            'created_at': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat(),
            'max_context_tokens': max_context_tokens
        }
        self.db.create_session(session_data)
        return Session(session_id, '', max_context_tokens, self.db)

    def list_sessions(self):
        """List all sessions"""
        return self.db.list_all_sessions()

    def purge_old_sessions(self, days: int):
        """Remove sessions older than specified days"""
        return self.db.purge_sessions(days)

class Session:
    def __init__(
        self,
        session_id: str,
        context: str,
        max_context_tokens: int,
        db: SessionDatabase
    ):
        self.session_id = session_id
        self.context = context
        self.max_context_tokens = max_context_tokens
        self._db = db

    @classmethod
    def from_db(cls, session_data: dict, db: SessionDatabase):
        """Create Session from database record"""
        return cls(
            session_data['session_id'],
            session_data['context'],
            session_data['max_context_tokens'],
            db
        )

    def prepare_prompt(self, user_prompt: str) -> str:
        """Prepare prompt with session context"""
        # Implementation from API Context Handling section
        pass

    def update_context(self, user_prompt: str, assistant_response: str):
        """Update session context after API response"""
        # Implementation from API Context Handling section
        pass

    def _save_to_db(self):
        """Save current session state to database"""
        self._db.update_session(
            self.session_id,
            {
                'context': self.context,
                'last_used': datetime.now().isoformat()
            }
        )
```

---

## 5-Phase Implementation Roadmap

### Phase 1: Database Layer Foundation (3-5 days)

**Files to Create:**
- `src/ollama_prompt/session_db.py` - Database abstraction layer
- `src/ollama_prompt/models.py` - Data models
- `tests/test_session_db.py` - Database unit tests

**Files to Modify:**
- `src/ollama_prompt/__init__.py` - Import new modules
- `pyproject.toml` - Add optional MongoDB dependency

**Tasks:**
1. Create SQLite database abstraction with connection pooling
2. Implement schema creation and migration system
3. Build CRUD operations: create_session(), get_session(), update_session(), delete_session()
4. Add cross-platform path handling for database location
5. Create MongoDB adapter interface (placeholder)

**Success Criteria:**
- Database created successfully on first run
- Session CRUD operations work without errors
- Unit tests pass for all database operations
- Cross-platform path handling verified (Windows/Linux/Mac)

---

### Phase 2: CLI Flag Integration (2-3 days)

**Files to Modify:**
- `src/ollama_prompt/cli.py` - Argument parser (lines 70-78)
- `src/ollama_prompt/__main__.py` - Command routing

**Files to Create:**
- `tests/test_cli_integration.py` - CLI flag testing

**Tasks:**
1. Add session management flags (--session-id, --new-session, --max-context-tokens)
2. Add utility commands (--list-sessions, --purge, --session-info)
3. Implement argument validation for mutual exclusivity
4. Add help text and documentation for new flags
5. Ensure backward compatibility (existing functionality unchanged)

**Success Criteria:**
- All new flags parse correctly
- Backward compatibility maintained (no session flags = stateless)
- Help text updated with new options
- Error handling for invalid session IDs
- Utility commands work independently

---

### Phase 3: Context Persistence Logic (4-5 days)

**Files to Modify:**
- `src/ollama_prompt/cli.py` - Main execution flow (around line 97)
- `src/ollama_prompt/ollama_client.py` - API call integration (if exists)

**Files to Create:**
- `src/ollama_prompt/session_manager.py` - SessionManager class
- `src/ollama_prompt/context_manager.py` - Context handling logic
- `tests/test_context_persistence.py` - Integration tests

**Tasks:**
1. Integrate SessionManager into main() flow
2. Implement context preparation before Ollama API call
3. Implement context update after API response
4. Build token counting and estimation
5. Create context pruning logic (FIFO strategy)
6. Handle Ollama API context window errors

**Success Criteria:**
- Session context persists across CLI calls
- Context truncation works within token limits
- Ollama API receives correct context format
- No performance degradation (>100ms overhead acceptable)
- Integration tests pass for full session lifecycle

---

### Phase 4: Session Management Utilities (2-3 days)

**Files to Modify:**
- `src/ollama_prompt/session_db.py` - Add MongoDB adapter
- `src/ollama_prompt/cli.py` - Add utility command implementations

**Files to Create:**
- `src/ollama_prompt/session_utils.py` - Management utilities

**Tasks:**
1. Implement MongoDB support via connection URI
2. Add database selection logic (SQLite default, MongoDB if URI provided)
3. Build session export/import functionality
4. Create batch operations (mass delete, update)
5. Add session statistics and reporting

**Success Criteria:**
- MongoDB integration works with test URI
- All utility commands functional (list, purge, info)
- No regressions in core functionality
- Export/import maintains session integrity

---

### Phase 5: Testing and Documentation (3-4 days)

**Files to Modify:**
- `README.md` - Session management section
- `CHANGELOG.md` - Feature documentation
- `pyproject.toml` - Version bump to 1.2.0

**Files to Create:**
- `examples/session_usage.py` - Practical examples
- `docs/session_management.md` - Detailed guide

**Tasks:**
1. Comprehensive unit testing (90%+ coverage target)
2. Integration tests for session workflows
3. Cross-platform validation (Windows, Linux, Mac)
4. Performance testing with large context windows
5. Update README with session management examples
6. Create migration guide for existing users
7. Write troubleshooting guide
8. Prepare PyPI release

**Success Criteria:**
- All tests pass across platforms
- Documentation clear and comprehensive
- Ready for production release
- Backward compatibility verified
- Performance benchmarks acceptable (<100ms overhead)

---

## Risk Assessment and Mitigation

### High-Risk Areas

**1. Backward Compatibility**
- **Risk:** Breaking existing workflows for current users
- **Mitigation:**
  - Default to stateless behavior when no session flags provided
  - Extensive testing with existing test suite
  - Beta release period for user feedback

**2. Performance Impact**
- **Risk:** Database operations slow down prompt response
- **Mitigation:**
  - Async database operations where possible
  - Connection pooling for SQLite
  - Performance benchmarks in testing phase
  - <100ms overhead target

**3. Context Window Management**
- **Risk:** Incorrect token counting leading to Ollama API errors
- **Mitigation:**
  - Conservative token estimation (4 chars = 1 token)
  - Ollama server validation responses
  - Fallback to context clearing on API errors
  - User warnings when approaching limits

### Medium-Risk Areas

**1. Cross-Platform Path Issues**
- **Risk:** Database path differences between OS
- **Mitigation:**
  - Use pathlib for all path operations
  - Extensive platform testing (Windows/Linux/Mac)
  - Environment variable overrides

**2. Database Corruption**
- **Risk:** SQLite file corruption during concurrent access
- **Mitigation:**
  - Proper locking mechanisms
  - Backup functionality
  - Recovery procedures documented

### Edge Cases to Handle

1. Session ID collisions (UUIDv4 minimizes risk to 1 in 2^122)
2. Database file permission issues (create with user-only access)
3. Very large context windows (>100k tokens - warn and truncate)
4. Concurrent session access (warn users, implement locking)
5. Disk space exhaustion (implement max sessions limit)

---

## Testing Strategy

### Unit Tests

**Database Layer:**
```python
def test_create_session():
    db = SessionDatabase(':memory:')
    session_id = db.create_session({
        'session_id': 'test-123',
        'context': 'test context',
        'max_context_tokens': 64000
    })
    assert session_id == 'test-123'

def test_get_nonexistent_session():
    db = SessionDatabase(':memory:')
    result = db.get_session('nonexistent')
    assert result is None
```

**Session Manager:**
```python
def test_create_or_load_new_session():
    manager = SessionManager(':memory:')
    session = manager.create_or_load_session(new_session=True)
    assert session.session_id is not None
    assert session.context == ''

def test_load_existing_session():
    manager = SessionManager(':memory:')
    session1 = manager.create_or_load_session(session_id='test-456')
    session1.update_context('prompt', 'response')

    session2 = manager.create_or_load_session(session_id='test-456')
    assert session2.context != ''
```

### Integration Tests

**Full Session Lifecycle:**
```python
def test_full_session_workflow(tmp_path):
    db_path = tmp_path / 'test_sessions.db'

    # First CLI call
    result1 = run_cli([
        '--prompt', 'What is Python?',
        '--new-session',
        '--session-id', 'test-session'
    ], db_path)

    session_id = result1['session_id']

    # Second CLI call (should have context)
    result2 = run_cli([
        '--prompt', 'Tell me more',
        '--session-id', session_id
    ], db_path)

    # Verify context was used
    assert 'Python' in get_session_context(db_path, session_id)
```

### Cross-Platform Tests

```python
@pytest.mark.parametrize('platform', ['windows', 'linux', 'darwin'])
def test_database_path_resolution(platform, monkeypatch):
    monkeypatch.setattr('sys.platform', platform)
    path = get_default_db_path()
    assert path.exists() or path.parent.exists()
```

---

## Usage Examples

### Basic Session Usage

```bash
# Create new session
ollama-prompt --prompt "Explain recursion" --new-session
# Output: { "session_id": "abc-123", "response": "..." }

# Continue session
ollama-prompt --prompt "Give me an example" --session-id abc-123
# Uses context from previous exchange

# View session info
ollama-prompt --session-info abc-123
```

### Session Management

```bash
# List all sessions
ollama-prompt --list-sessions

# Purge old sessions
ollama-prompt --purge 30  # Remove sessions older than 30 days

# Custom context window
ollama-prompt --prompt "..." --session-id abc-123 --max-context-tokens 128000
```

### Database Configuration

```bash
# Custom SQLite path
export OLLAMA_PROMPT_DB_PATH="/custom/path/sessions.db"
ollama-prompt --prompt "..."

# MongoDB backend
export OLLAMA_PROMPT_DB_URI="mongodb://localhost:27017/ollama_sessions"
ollama-prompt --prompt "..."
```

---

## Performance Benchmarks

**Target Metrics:**
- Session creation: <50ms
- Session loading: <50ms
- Context update: <100ms
- Total overhead: <200ms per CLI call

**Estimated Token Usage:**
- 10 exchanges at 200 tokens each: ~2000 tokens
- 50 exchanges at 200 tokens each: ~10,000 tokens
- Automatic pruning at configured max_context_tokens

---

## Migration Guide for Users

### No Changes Required

For users who don't use session management:
```bash
# This continues to work exactly as before
ollama-prompt --prompt "Your question here"
```

### Opt-In Session Management

To enable sessions:
```bash
# First time - creates new session
ollama-prompt --prompt "First question" --new-session

# Save the session ID from the output
# Then use it in subsequent calls
ollama-prompt --prompt "Follow-up question" --session-id <your-session-id>
```

---

## Conclusion

This comprehensive plan provides a clear roadmap for implementing session memory in ollama-prompt. The 5-phase approach ensures:

1. **Solid Foundation** - Database layer built first (Phase 1)
2. **User Interface** - CLI integration follows (Phase 2)
3. **Core Functionality** - Context persistence implemented (Phase 3)
4. **Enhanced Features** - Utilities and MongoDB support (Phase 4)
5. **Production Ready** - Testing and documentation (Phase 5)

**Total Timeline:** 14-20 days
**Backward Compatibility:** 100% maintained
**Risk Level:** Low to Medium (with mitigation strategies in place)

The implementation leverages existing patterns in the codebase (argparse, ollama.generate() calls) and adds minimal complexity while providing significant value through persistent context management.

---

## Next Steps

1. Review and approve this plan
2. Set up development branch from feat/add-think-flag
3. Begin Phase 1: Database Layer Foundation
4. Establish testing infrastructure
5. Regular checkpoints after each phase completion

**Questions or clarifications needed before proceeding with implementation?**
