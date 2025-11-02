# ollama-prompt Complete Reference

**Purpose:** Authoritative reference combining code implementation details with practical best practices
**Based On:** Code analysis (cli.py, session_manager.py, session_utils.py) + ollama-prompt-subprocess-best-practices.md
**Last Updated:** 2025-11-01

---

## Table of Contents

1. [Overview](#overview)
2. [Session Management](#session-management)
3. [Command-Line Flags](#command-line-flags)
4. [File References](#file-references)
5. [Output Format](#output-format)
6. [Best Practices](#best-practices)
7. [Advanced Patterns](#advanced-patterns)
8. [Storage & Database](#storage--database)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What is ollama-prompt?

Command-line tool for interacting with Ollama models featuring:
- **Session management** - Persistent conversation context across CLI invocations
- **File references** - Inline local files with `@file` syntax
- **Subprocess-friendly** - JSON output for programmatic usage
- **Local storage** - SQLite database (no cloud dependency)

### Quick Start

```bash
# Simple query
ollama-prompt --prompt "Explain Rust ownership"

# With file reference
ollama-prompt --prompt "Review @./src/auth.py for security issues"

# Continue previous session
ollama-prompt --session-id <uuid-from-previous-output> --prompt "What about the API layer?"
```

---

## Prerequisites & Setup

### Ollama CLI Installation

**Installation Required:**
- Download and install Ollama from [ollama.com](https://ollama.com)
- Follow platform-specific installation instructions (Windows, macOS, or Linux)
- Ollama CLI automatically starts the server when needed

**How Ollama Works:**
- The Ollama CLI automatically starts a local server at `http://localhost:11434`
- This server acts as a proxy for both local and cloud models
- You do NOT need to manually run `ollama serve` before using ollama-prompt
- The server starts automatically when you use any Ollama command

**Verification:**
```bash
# Check Ollama installation
ollama --version

# List available models (confirms Ollama is working)
ollama list
```

### Model Setup: Local vs Cloud

**Local Models:**
```bash
# Pull models to your local machine
ollama pull llama2:13b
ollama pull codellama:7b
ollama pull mistral:7b
```

**Cloud Models (Including Default):**
```bash
# Authenticate with Ollama account (required for cloud models)
ollama signin
# Follow the prompts to create/login to your ollama.com account

# Pull cloud model metadata (recommended for faster access)
ollama pull deepseek-v3.1:671b-cloud
```

**Available Cloud Models:**
- `deepseek-v3.1:671b-cloud` (default)
- `gpt-oss:20b-cloud`, `gpt-oss:120b-cloud`
- `kimi-k2:1t-cloud`
- `qwen3-coder:480b-cloud`
- `glm-4.6:cloud`
- `minimax-m2:cloud`

**Model Availability Check:**
```bash
# List all available models (local and cloud)
ollama list
```

### Authentication for Cloud Models

**Cloud Model Workflow:**
1. Local Ollama CLI automatically starts a server that proxies requests to Ollama's cloud infrastructure
2. Authentication handled via `ollama signin`
3. ollama-prompt works transparently with both local and cloud models

**Troubleshooting Cloud Access:**
```bash
# Re-authenticate if needed
ollama signin

# Verify cloud model is available
ollama list | grep cloud

# Test cloud model access with ollama-prompt
ollama-prompt --prompt "test" --model deepseek-v3.1:671b-cloud --no-session
```

### Troubleshooting Common Issues

**"Connection refused" Error:**
```bash
# Solution: Verify Ollama CLI is installed and try running a command
ollama list

# The above command will automatically start the Ollama server
# If still failing, check Ollama installation:
ollama --version
```

**"Model not found" Error (Cloud Models):**
```bash
# Solution: Authenticate and pull cloud model
ollama signin
ollama pull deepseek-v3.1:671b-cloud
```

**"Authentication required" Error:**
```bash
# Solution: Sign in to Ollama account
ollama signin
```

### Quick Setup Test
```bash
# Complete setup verification
ollama --version && ollama list

# If both commands succeed, ollama-prompt should work with both local and cloud models
```

---

## Session Management

### How Sessions Work

**Code:** `session_manager.py` lines 66-98

#### Auto-Creation (No --session-id flag)

**Behavior:**
- Generates UUID session ID automatically
- Stores in SQLite database
- Returns `session_id` in JSON output

**Example:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze codebase structure"
```

**Output:**
```json
{
  "model": "deepseek-v3.1:671b-cloud",
  "response": "...",
  "session_id": "f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n"
}
```

#### Session Continuation (With --session-id)

**Behavior:**
- Loads existing session by UUID
- Prepends conversation context
- Updates session with new exchange

**Example:**
```bash
ollama-prompt --session-id f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n \
              --prompt "Now analyze the auth module"
```

#### CRITICAL: Custom IDs Don't Work

**WRONG:**
```bash
ollama-prompt --session-id my-review --prompt "..."
# ERROR: Session not found: my-review
```

**Reason:** `--session-id` only accepts existing UUIDs from database

#### Multi-Turn Workflow

```bash
# STEP 1: Create session
ollama-prompt --prompt "Review @./src/auth.py" > ./ollama-output/turn1.json
# Extract: "session_id": "f8e3c2a1-..."

# STEP 2: Continue
ollama-prompt --session-id f8e3c2a1-... \
              --prompt "Check @./src/api.py integration" > ./ollama-output/turn2.json

# STEP 3: Summary
ollama-prompt --session-id f8e3c2a1-... \
              --prompt "Summarize all issues" > ./ollama-output/summary.json
```

### Stateless Mode

```bash
ollama-prompt --no-session --prompt "One-off query"
```

**Behavior:**
- No session created
- No database storage
- No `session_id` in output

**Use When:**
- One-off queries
- Batch processing independent prompts
- Testing without context

### Session Utilities

#### List Sessions

```bash
ollama-prompt --list-sessions
```

**Output:**
```json
{
  "sessions": [{
    "session_id": "f8e3c2a1-...",
    "model_name": "deepseek-v3.1:671b-cloud",
    "created_at": "2025-11-01T10:30:00",
    "last_used": "2025-11-01T14:45:00",
    "message_count": 5,
    "context_tokens": 1250
  }],
  "total": 1
}
```

#### Session Details

```bash
ollama-prompt --session-info f8e3c2a1-...
```

**Shows:**
- Full message history
- Token usage
- Context percentage
- Metadata

#### Purge Old Sessions

```bash
ollama-prompt --purge 7  # Remove sessions older than 7 days
```

### Context Management

**Default Limit:** 64,000 tokens

**Override:**
```bash
ollama-prompt --max-context-tokens 100000 --prompt "..."
```

**Auto-Pruning:**
- Triggers at 90% of limit
- Prunes to 80% of limit
- Removes oldest message pairs
- Automatic (no user action needed)

**Token Estimation:** 4 characters = 1 token

---

## Command-Line Flags

### Model & Generation

```bash
--model <name>          # Default: deepseek-v3.1:671b-cloud
--temperature <float>   # Default: 0.1
--max_tokens <int>      # Default: 2048
--think                 # Enable thinking mode
```

**Temperature Guidelines:**
- `0.0-0.2` - Code generation, deterministic output
- `0.2-0.4` - Code analysis, factual responses
- `0.5-0.7` - Documentation, creative writing

### File References

```bash
--repo-root <path>           # Base directory (default: .)
--max-file-bytes <int>       # Max bytes per file (default: 200,000)
```

### Session Management

```bash
--session-id <uuid>          # Continue existing session
--no-session                 # Stateless mode
--max-context-tokens <int>   # Override limit (default: 64,000)
```

### Utilities

```bash
--list-sessions              # List all sessions
--purge <days>               # Remove old sessions
--session-info <uuid>        # Show session details
```

---

## File References

### Syntax

**Valid patterns (require path separator):**
- `@./relative/file.py`
- `@../parent/file.py`
- `@/absolute/path.py`
- `@src/file.py`

**Invalid (not expanded):**
- `@username` (no /)
- `@file` (no /)

### Examples

```bash
# Single file
ollama-prompt --prompt "Analyze @./src/auth.py"

# Multiple files
ollama-prompt --prompt "Compare @./src/v1.py and @./src/v2.py"

# Mixed paths
ollama-prompt --prompt "Review @./src/auth.py and @./tests/test_auth.py"
```

### File Expansion

**Process:**
1. Find `@file` tokens
2. Read files (bounded by --max-file-bytes)
3. Inline with delimiters
4. Send expanded prompt to model

**Format:**
```
--- FILE: ./src/auth.py START ---
<file contents>
--- FILE: ./src/auth.py END ---
```

**Truncation:**
If file exceeds max_file_bytes:
```
[TRUNCATED: file larger than max_bytes]
```

---

## Output Format

### Standard Output (With Session)

```json
{
  "model": "deepseek-v3.1:671b-cloud",
  "created_at": "2025-11-01T10:30:00Z",
  "response": "The actual markdown response...",
  "done": true,
  "session_id": "f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n",
  "total_duration": 1234567890,
  "load_duration": 123456,
  "prompt_eval_count": 10,
  "prompt_eval_duration": 987654,
  "eval_count": 50,
  "eval_duration": 1234567
}
```

### Stateless Output

Same structure WITHOUT `session_id` field

### Response Field

Contains markdown content:
```json
{
  "response": "# Analysis\n\n## Findings\n\n1. Security issue..."
}
```

**Why .json extension?**
- File format is JSON (parseable)
- Response content is markdown (readable)
- Preserves metadata

---

## Best Practices

### Directory Structure

**Always use dedicated output directory:**

```bash
mkdir -p ./ollama-output
```

**Benefits:**
- Prevents clutter
- Easy cleanup
- Clear separation
- Simple .gitignore

### File Naming

**Pattern:**
```
./ollama-output/analysis01.json
./ollama-output/analysis02.json
./ollama-output/synthesis.json
```

### Standard Command Template

```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analysis prompt" \
              > ./ollama-output/result.json
```

**Always specify:**
- `--model` (explicit)
- `--temperature` (controlled)
- `--max_tokens` (limited)
- Output redirect to `./ollama-output/`

---

## Advanced Patterns

### CAL Method: Parallel Analysis

**Problem:** Large codebase exhausts token budget

**Solution:** Parallel subprocess analysis

```bash
mkdir -p ./ollama-output

# Launch 4 concurrent analyses
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze CLI layer in @./src/cli.py" \
              > ./ollama-output/analysis01.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze API layer in @./src/api.py" \
              > ./ollama-output/analysis02.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze database layer in @./src/db.py" \
              > ./ollama-output/analysis03.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze business logic in @./src/core.py" \
              > ./ollama-output/analysis04.json &

wait
echo "Batch complete"

# Synthesize findings
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 12000 \
              --prompt "Synthesize architecture from:
@./ollama-output/analysis01.json
@./ollama-output/analysis02.json
@./ollama-output/analysis03.json
@./ollama-output/analysis04.json" \
              > ./ollama-output/synthesis.json
```

**Benefits:**
- 4 analyses in ~60 seconds (vs 240 sequential)
- Fresh token budget per subprocess
- Scales to large codebases

**Limit:** Max 4 concurrent

### Session-Based Multi-Turn

```bash
# Create session
ollama-prompt --prompt "Review @./src/auth.py" > ./ollama-output/turn1.json

# Extract session_id
SESSION_ID=$(jq -r '.session_id' ./ollama-output/turn1.json)

# Continue with context
ollama-prompt --session-id $SESSION_ID \
              --prompt "Check @./src/api.py integration" > ./ollama-output/turn2.json

# Summary with full context
ollama-prompt --session-id $SESSION_ID \
              --prompt "Summarize all issues" > ./ollama-output/summary.json
```

### Chaining with jq

```bash
# Extract session_id
SESSION_ID=$(ollama-prompt --prompt "Start" | tee output.json | jq -r '.session_id')

# Extract response content
ollama-prompt --prompt "Analyze" | jq -r '.response' > analysis.md

# Check if session exists
ollama-prompt --list-sessions | jq '.sessions[] | select(.session_id == "f8e3c2a1-...")'
```

---

## Storage & Database

### Location

**Default:** `~/.ollama-prompt/sessions.db`

### Schema

**sessions table:**
- `session_id` (TEXT PRIMARY KEY) - UUID
- `context` (TEXT) - Cached conversation text
- `history_json` (TEXT) - Message array JSON
- `max_context_tokens` (INTEGER)
- `created_at` (TEXT) - ISO 8601
- `last_used` (TEXT) - ISO 8601
- `model_name` (TEXT)
- `system_prompt` (TEXT)
- `metadata_json` (TEXT)

### Message Storage

**Dual system:**

**1. JSON (history_json):**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Analyze code",
      "timestamp": "2025-11-01T10:30:00",
      "tokens": 123
    },
    {
      "role": "assistant",
      "content": "Analysis...",
      "timestamp": "2025-11-01T10:30:05",
      "tokens": 456
    }
  ]
}
```

**2. Cached text (context):**
```
User: Analyze code
Assistant: Here's the analysis...
```

**Purpose:** Dual storage for performance and recovery
- JSON messages: Full history with metadata
- Cached text: Fast context prepending (no JSON parsing needed)

---

## Troubleshooting

### Session Not Found Error

**Error:**
```
ERROR: Session not found: abc-123
```

**Cause:** Invalid session UUID or session doesn't exist

**Solutions:**
```bash
# List all sessions to find correct UUID
ollama-prompt --list-sessions

# Use exact UUID from list
ollama-prompt --session-id <uuid-from-list> --prompt "..."
```

### Custom Session ID Not Working

**Error:**
```
ERROR: Session not found: my-custom-name
```

**Cause:** Trying to use custom session ID

**Solution:** Session IDs MUST be UUIDs from previous sessions. Cannot create custom IDs.

**Correct workflow:**
```bash
# First call creates session
ollama-prompt --prompt "..." > output.json

# Extract UUID
SESSION_ID=$(jq -r '.session_id' output.json)

# Continue with that UUID
ollama-prompt --session-id $SESSION_ID --prompt "..."
```

### File Reference Not Expanding

**Problem:** `@./file.py` not being inlined

**Causes:**
1. Missing path separator (use `@./file.py` not `@file.py`)
2. File doesn't exist
3. File outside repo-root

**Solutions:**
```bash
# Check file exists
ls ./src/auth.py

# Use correct syntax with path separator
ollama-prompt --prompt "Analyze @./src/auth.py"

# Specify repo-root if needed
ollama-prompt --repo-root /path/to/project --prompt "Analyze @./src/auth.py"
```

### Context Limit Exceeded

**Problem:** Session approaching token limit

**Check usage:**
```bash
ollama-prompt --session-info <uuid>
# Look at context_usage_percent
```

**Solutions:**
```bash
# Start new session
ollama-prompt --prompt "Fresh start"

# Increase limit
ollama-prompt --max-context-tokens 100000 --prompt "..."

# Use stateless mode
ollama-prompt --no-session --prompt "..."
```

### Conflicting Flags Error

**Error:**
```
ERROR: --session-id and --no-session are mutually exclusive
```

**Cause:** Using both `--session-id` and `--no-session`

**Solution:** Choose one:
```bash
# With session
ollama-prompt --session-id <uuid> --prompt "..."

# Without session
ollama-prompt --no-session --prompt "..."
```

### Database Locked

**Problem:** SQLite database locked

**Causes:**
- Multiple ollama-prompt processes accessing database
- Stale lock from crashed process

**Solutions:**
```bash
# Wait for other processes to complete
ps aux | grep ollama-prompt

# If needed, kill stale processes
kill <pid>

# Database location
ls ~/.ollama-prompt/sessions.db
```

### Large File Truncation

**Problem:** File content truncated in response

**Cause:** File exceeds --max-file-bytes

**Solution:**
```bash
# Increase limit
ollama-prompt --max-file-bytes 500000 --prompt "Analyze @./large-file.py"

# Or split analysis
ollama-prompt --prompt "Analyze first half of @./large-file.py lines 1-500"
```

### Session Pruning Unexpected

**Problem:** Old messages disappeared from session

**Cause:** Auto-pruning at 90% of max_context_tokens

**Check:**
```bash
ollama-prompt --session-info <uuid>
# Check context_usage_percent
```

**Solutions:**
- Expected behavior (keeps recent messages)
- Increase max-context-tokens if needed
- Start new session for different topic

### Output Not Redirecting

**Problem:** Output not saving to file

**Wrong:**
```bash
ollama-prompt --prompt "..." --output file.json  # No --output flag exists
```

**Correct:**
```bash
ollama-prompt --prompt "..." > ./ollama-output/result.json
```

---

## Summary

**Key Concepts:**
- Sessions auto-create (UUID session IDs)
- Use `--session-id <uuid>` to continue
- File refs use `@./path` syntax
- Output is JSON (response field has markdown)
- Parallel analysis with max 4 concurrent
- Stateless mode with `--no-session`

**Common Patterns:**
```bash
# Single query
ollama-prompt --prompt "Question"

# With file
ollama-prompt --prompt "Analyze @./file.py"

# Multi-turn session
ollama-prompt --prompt "Start" > out1.json
SESSION=$(jq -r '.session_id' out1.json)
ollama-prompt --session-id $SESSION --prompt "Continue"

# Parallel batch
for i in 1 2 3 4; do
  ollama-prompt --prompt "Analyze part $i" > analysis$i.json &
done
wait

# Stateless
ollama-prompt --no-session --prompt "One-off query"
```

**Reference Files:**
- Database: `~/.ollama-prompt/sessions.db`
- Best practices: `ollama-prompt-subprocess-best-practices.md`
- Use cases: `docs/guides/use-cases.md`

---

*End of Reference*
