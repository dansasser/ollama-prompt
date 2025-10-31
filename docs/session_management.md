# Session Management Guide

**ollama-prompt** now supports persistent conversation sessions, allowing you to maintain context across multiple CLI invocations. This guide covers everything you need to know about using session management effectively.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [How It Works](#how-it-works)
3. [Session Workflow](#session-workflow)
4. [Session Flags](#session-flags)
5. [Utility Commands](#utility-commands)
6. [Configuration](#configuration)
7. [Storage Details](#storage-details)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

**Start a conversation (auto-creates session):**
```bash
ollama-prompt --prompt "What is 2+2?"
```

**Output includes session_id:**
```json
{
  "response": "2+2 equals 4.",
  "session_id": "abc-123-def-456",
  ...
}
```

**Continue the conversation:**
```bash
ollama-prompt --prompt "What about 3+3?" --session-id abc-123-def-456
```

The model will automatically include the previous exchange as context!

---

## How It Works

### Automatic Session Creation

By default, every prompt automatically creates a new session. No flags needed!

- First prompt → Session auto-created with unique ID
- Output includes `session_id` field
- Context stored in local SQLite database

### Context Persistence

Sessions store your conversation history:
- **Dual storage:** JSON messages + cached plain text
- **Smart pruning:** Automatically removes old messages when approaching token limits
- **Token management:** Configurable context window (default: 64,000 tokens)

### Database Location

Sessions are stored in a local SQLite database:

- **Windows:** `%APPDATA%\ollama-prompt\sessions.db`
- **Linux/Mac:** `~/.config/ollama-prompt/sessions.db`

Override with `OLLAMA_PROMPT_DB_PATH` environment variable.

---

## Session Workflow

### Pattern 1: Multi-Turn Conversation

```bash
# First question - creates session
ollama-prompt --prompt "Who wrote Hamlet?"
# Output: {"session_id": "abc-123", "response": "William Shakespeare", ...}

# Follow-up question - uses context
ollama-prompt --prompt "When was he born?" --session-id abc-123
# Model knows "he" refers to Shakespeare from previous exchange

# Another follow-up
ollama-prompt --prompt "What other plays did he write?" --session-id abc-123
# Full conversation history is maintained
```

### Pattern 2: Code Review Across Files

```bash
# Review first file
ollama-prompt --prompt "@./src/auth.py Review this authentication code"
# Output: {"session_id": "xyz-789", ...}

# Review related file with context
ollama-prompt --prompt "@./src/user.py How does this interact with the auth module?" \
  --session-id xyz-789
# Model remembers the authentication code from previous review
```

### Pattern 3: Stateless Mode

For one-off questions that don't need context:

```bash
ollama-prompt --prompt "What is the capital of France?" --no-session
```

No session created, no database storage.

---

## Session Flags

### `--session-id <id>`

**Continue an existing session by ID.**

```bash
ollama-prompt --prompt "Follow-up question" --session-id abc-123-def-456
```

- Loads conversation history from database
- Prepends context to your prompt automatically
- Updates session after response

**Error if session not found:**
```json
{"error": "session management failed: Session not found: invalid-id"}
```

### `--no-session`

**Run in stateless mode (no session storage).**

```bash
ollama-prompt --prompt "Quick question" --no-session
```

- No session created
- No database storage
- No context from previous exchanges
- Useful for one-off queries

**Mutually exclusive with `--session-id`.**

### `--max-context-tokens <num>`

**Override the maximum context token limit for this session.**

```bash
ollama-prompt --prompt "Start conversation" --max-context-tokens 128000
```

- Default: 64,000 tokens
- Range: 4,000 - 256,000 (depends on your model)
- Context automatically pruned when approaching limit

**Priority:** CLI flag > Env var > Default

---

## Utility Commands

### `--list-sessions`

**List all stored sessions.**

```bash
ollama-prompt --list-sessions
```

**Output:**
```json
{
  "sessions": [
    {
      "session_id": "abc-123-def-456",
      "model_name": "deepseek-v3.1:671b-cloud",
      "created_at": "2025-10-31T10:30:00",
      "last_used": "2025-10-31T14:45:00",
      "message_count": 5,
      "context_tokens": 1250
    }
  ],
  "total": 1
}
```

### `--purge <days>`

**Remove sessions older than specified days.**

```bash
ollama-prompt --purge 30
```

**Output:**
```json
{
  "removed": 5,
  "message": "Removed 5 sessions older than 30 days"
}
```

Useful for:
- Cleaning up old sessions
- Managing disk space
- Privacy (removing old conversations)

### `--session-info <id>`

**Show detailed information for a specific session.**

```bash
ollama-prompt --session-info abc-123-def-456
```

**Output:**
```json
{
  "session_id": "abc-123-def-456",
  "model_name": "deepseek-v3.1:671b-cloud",
  "created_at": "2025-10-31T10:30:00",
  "last_used": "2025-10-31T14:45:00",
  "max_context_tokens": 64000,
  "context_tokens": 1250,
  "context_usage_percent": 1.95,
  "message_count": 5,
  "messages": [
    {
      "role": "user",
      "content": "What is 2+2?",
      "timestamp": "2025-10-31T10:30:00",
      "tokens": 4
    },
    {
      "role": "assistant",
      "content": "2+2 equals 4.",
      "timestamp": "2025-10-31T10:30:05",
      "tokens": 5
    }
  ]
}
```

Useful for:
- Debugging context issues
- Reviewing conversation history
- Monitoring token usage

---

## Configuration

### Environment Variables

**`OLLAMA_PROMPT_MAX_CONTEXT_TOKENS`**

Set default max context tokens for all new sessions:

```bash
export OLLAMA_PROMPT_MAX_CONTEXT_TOKENS=128000
ollama-prompt --prompt "Start conversation"
```

**`OLLAMA_PROMPT_DB_PATH`**

Override database location:

```bash
export OLLAMA_PROMPT_DB_PATH=/custom/path/sessions.db
ollama-prompt --prompt "Question"
```

### Configuration Priority

When determining `max_context_tokens`:

1. CLI flag: `--max-context-tokens 100000` (highest priority)
2. Environment variable: `OLLAMA_PROMPT_MAX_CONTEXT_TOKENS=100000`
3. Default: `64000` (lowest priority)

---

## Storage Details

### Database Schema

Sessions are stored in SQLite with the following structure:

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    context TEXT NOT NULL DEFAULT '',              -- Cached plain text
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_context_tokens INTEGER DEFAULT 64000,
    history_json TEXT,                             -- Structured messages (JSON)
    metadata_json TEXT,                            -- Extra metadata (JSON)
    model_name TEXT,
    system_prompt TEXT
);
```

### Message Storage Format

Messages are stored as JSON in the `history_json` field:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is 2+2?",
      "timestamp": "2025-10-31T10:30:00",
      "tokens": 4
    },
    {
      "role": "assistant",
      "content": "2+2 equals 4.",
      "timestamp": "2025-10-31T10:30:05",
      "tokens": 5
    }
  ]
}
```

### Dual Storage Strategy

For performance and reliability, ollama-prompt uses **dual storage:**

1. **Structured JSON** (`history_json` field)
   - Preserves message roles, timestamps, token counts
   - Enables smart pruning (remove specific messages)
   - Supports future features (search, analytics, export)

2. **Cached Plain Text** (`context` field)
   - Fast loading without JSON parsing
   - Used directly in prompt preparation
   - Rebuilt when messages are pruned

### Automatic Pruning

When context approaches the token limit (90% threshold):

1. Calculate total tokens across all messages
2. Remove oldest exchanges (FIFO - First In, First Out)
3. Prune to 80% of `max_context_tokens`
4. Rebuild cached plain text
5. Update database

**Always keeps at least 2 messages** (1 user + 1 assistant exchange).

---

## Best Practices

### 1. Use Descriptive Prompts

Start conversations with context:

```bash
# Good
ollama-prompt --prompt "I'm reviewing authentication code. Here's the first file: @./auth.py"

# Better
ollama-prompt --prompt "Code review session: analyzing authentication security in a Python web app. First file: @./auth.py"
```

### 2. Monitor Token Usage

Check context usage regularly:

```bash
ollama-prompt --session-info abc-123 | jq .context_usage_percent
```

If approaching limit (>80%), consider:
- Starting a new session
- Increasing `max_context_tokens`
- Allowing automatic pruning

### 3. Clean Up Old Sessions

Periodically purge unused sessions:

```bash
# Remove sessions older than 7 days
ollama-prompt --purge 7

# Remove sessions older than 1 month
ollama-prompt --purge 30
```

### 4. Use Stateless Mode Appropriately

Use `--no-session` for:
- One-off questions
- Quick lookups
- Privacy-sensitive queries

**Don't use for:**
- Multi-turn conversations
- Code reviews across files
- Iterative problem-solving

### 5. Save Session IDs

For important conversations, save the session ID:

```bash
# Save to file
ollama-prompt --prompt "Important question" | jq -r .session_id > session-id.txt

# Resume later
SESSION_ID=$(cat session-id.txt)
ollama-prompt --prompt "Follow-up" --session-id $SESSION_ID
```

### 6. Model Consistency

Stick with the same model for a session:

```bash
# First prompt
ollama-prompt --prompt "Question" --model deepseek-v3.1:671b-cloud

# Follow-up (same model)
ollama-prompt --prompt "Follow-up" --session-id abc-123 --model deepseek-v3.1:671b-cloud
```

Different models may interpret context differently.

---

## Troubleshooting

### "Session not found" Error

**Problem:**
```json
{"error": "session management failed: Session not found: abc-123"}
```

**Solutions:**
1. Check session ID is correct (use `--list-sessions`)
2. Session may have been purged
3. Database may have been deleted/moved

### Context Not Being Used

**Problem:** Model doesn't remember previous exchanges.

**Check:**
```bash
ollama-prompt --session-info <session-id> | jq .message_count
```

**Common causes:**
1. Forgot to include `--session-id` flag
2. Used different session ID by mistake
3. Session pruned all old messages (check `context_usage_percent`)

### Token Limit Exceeded

**Problem:** Getting truncated responses or errors.

**Solutions:**
1. Increase limit: `--max-context-tokens 128000`
2. Start new session (context reset)
3. Use more concise prompts
4. Allow automatic pruning (already enabled by default)

### Database Locked Error

**Problem:**
```
sqlite3.OperationalError: database is locked
```

**Cause:** Multiple `ollama-prompt` processes accessing database simultaneously.

**Solution:** Wait for other processes to finish, or use `--no-session` for parallel queries.

### Disk Space Issues

**Check database size:**

**Windows:**
```powershell
Get-ChildItem $env:APPDATA\ollama-prompt\sessions.db
```

**Linux/Mac:**
```bash
du -h ~/.config/ollama-prompt/sessions.db
```

**Clean up:**
```bash
ollama-prompt --purge 7  # Remove sessions older than 7 days
```

---

## Advanced Usage

### Scripting with Sessions

**Bash:**
```bash
#!/bin/bash

# Start code review session
SESSION_ID=$(ollama-prompt --prompt "Starting code review of authentication module" | jq -r .session_id)

# Review multiple files
for file in src/auth/*.py; do
  ollama-prompt --prompt "Review @./$file" --session-id $SESSION_ID
done

# Get summary
ollama-prompt --prompt "Summarize all findings" --session-id $SESSION_ID
```

**PowerShell:**
```powershell
# Start code review session
$result = ollama-prompt --prompt "Starting code review" | ConvertFrom-Json
$sessionId = $result.session_id

# Review files
Get-ChildItem src\auth\*.py | ForEach-Object {
  ollama-prompt --prompt "Review @$($_.FullName)" --session-id $sessionId
}
```

### Parallel Stateless Queries

For performance with independent queries:

```bash
# Run 5 independent queries in parallel
for i in {1..5}; do
  ollama-prompt --prompt "Question $i" --no-session &
done
wait
```

**Note:** Use `--no-session` to avoid database locking with parallel execution.

---

## See Also

- [README.md](../README.md) - Main documentation
- [examples/session_usage.py](../examples/session_usage.py) - Python examples
- [Subprocess Best Practices](../ollama-prompt-subprocess-best-practices.md) - Agent orchestration patterns
