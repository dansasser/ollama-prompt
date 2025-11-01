# Session Management Quickstart

Get started with persistent conversations in ollama-prompt in under 5 minutes.

## 🚀 What Are Sessions?

Sessions automatically save your conversation history, allowing you to continue chats across multiple CLI invocations. Think of them as persistent chat threads that remember context.

**Why use sessions?**
- Continue conversations later without losing context
- Maintain separate discussion threads for different topics
- Perfect for multi-day projects or complex debugging sessions

## ✅ Prerequisites Checklist

Before starting with sessions, ensure you have:

- ✅ **Ollama CLI installed** (`ollama --version` should work)
- ✅ **For cloud models**: Authenticated (`ollama signin` completed)
- ✅ **ollama-prompt package installed** (`pip install ollama-prompt`)

**Quick verification:**
```bash
ollama list  # Should show available models (local and cloud)
```

*Note: You do NOT need to manually run `ollama serve` - Ollama automatically starts the server when needed. Sessions work with both local and cloud models. Cloud models require `ollama signin` authentication.*

## ⚡ Your First Session

### 1. Start a New Session (Auto-created)

Simply run ollama-prompt - sessions are created automatically with a unique ID:

```bash
ollama-prompt --prompt "Help me plan a Python web application" > conversation.json
```

**Output includes:**
```json
{
  "model": "deepseek-v3.1:671b-cloud",
  "response": "I'll help you plan a Python web application...",
  "session_id": "f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n",
  "done": true
}
```

Your session is automatically created and assigned a **UUID**. Save this UUID to continue the conversation later.

### 2. Continue Your Conversation

Extract the session_id from your previous output and use it to continue:

**Windows PowerShell:**
```powershell
# Extract session ID from JSON
$sessionId = (Get-Content conversation.json | ConvertFrom-Json).session_id

# Continue conversation with that UUID
ollama-prompt --session-id $sessionId --prompt "Now let's design the database schema"
```

**Bash/Unix:**
```bash
# Extract session ID from JSON
SESSION_ID=$(jq -r '.session_id' conversation.json)

# Continue conversation with that UUID
ollama-prompt --session-id $SESSION_ID --prompt "Now let's design the database schema"
```

The system loads your session by UUID and continues with full context.

## 🔍 Managing Your Sessions

### List All Sessions

See all your active conversations:

```bash
ollama-prompt --list-sessions
```

Example output:
```json
{
  "sessions": [
    {
      "session_id": "f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n",
      "model_name": "deepseek-v3.1:671b-cloud",
      "created_at": "2025-11-01T10:30:00",
      "last_used": "2025-11-01T14:45:00",
      "message_count": 5,
      "context_tokens": 1250
    }
  ],
  "total": 1
}
```

### View Session Details

Get complete history for a specific session:

```bash
ollama-prompt --session-info f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n
```

### Continue a Specific Session

Use the exact UUID from --list-sessions:

```bash
ollama-prompt --session-id f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n \
              --prompt "What was our last topic?"
```

## 💡 Practical Examples

### Example 1: Multi-day Project

**Day 1: Planning**
```bash
# Start conversation
ollama-prompt --prompt "I'm building a todo app. Help me outline the features." > day1.json

# Save the session ID for tomorrow
SESSION_ID=$(jq -r '.session_id' day1.json)
echo $SESSION_ID > session.txt
```

**Day 2: Implementation**
```bash
# Load session ID from yesterday
SESSION_ID=$(cat session.txt)

# Continue with full context
ollama-prompt --session-id $SESSION_ID \
              --prompt "Let's start with the React component structure"
```

### Example 2: Parallel Work Sessions

```bash
# Create output directory
mkdir -p ./sessions

# Session 1: Work project
ollama-prompt --prompt "Debug this production issue with authentication" > ./sessions/work.json
WORK_SESSION=$(jq -r '.session_id' ./sessions/work.json)

# Session 2: Personal project
ollama-prompt --prompt "Help me learn guitar chords" > ./sessions/personal.json
PERSONAL_SESSION=$(jq -r '.session_id' ./sessions/personal.json)

# Later: Continue work session
ollama-prompt --session-id $WORK_SESSION \
              --prompt "What was the auth error we were debugging?"

# Later: Continue personal session
ollama-prompt --session-id $PERSONAL_SESSION \
              --prompt "Now teach me the C major scale"
```

### Example 3: Session Cleanup

```bash
# List all sessions to find old ones
ollama-prompt --list-sessions | jq '.sessions[] | {id: .session_id, created: .created_at}'

# Remove sessions older than 30 days
ollama-prompt --purge 30
```

## 🚫 When to Use --no-session

Sometimes you want a one-off conversation without persistence:

```bash
ollama-prompt --no-session --prompt "Just help me with this quick regex"
```

Use `--no-session` for:
- Quick, disposable questions
- Sensitive information you don't want saved
- Temporary debugging sessions
- Batch processing independent prompts

**Output WITHOUT session_id:**
```json
{
  "model": "deepseek-v3.1:671b-cloud",
  "response": "Here's a regex pattern...",
  "done": true
}
```

## 📝 Key Points

**Session IDs are UUIDs:**
- Auto-generated (like `f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n`)
- Cannot create custom session names
- Must use exact UUID to continue conversation

**First call creates, subsequent calls continue:**
```bash
# Creates session
ollama-prompt --prompt "Question 1" > out.json

# Continues that session
ollama-prompt --session-id $(jq -r '.session_id' out.json) --prompt "Question 2"
```

**Sessions are stored locally:**
- Database: `~/.ollama-prompt/sessions.db`
- No cloud dependency
- Cross-platform compatible

## ✅ Next Steps

You're now ready to use sessions! Try these next:
- Run `ollama-prompt --list-sessions` to see your current sessions
- Create a new conversation and extract its session_id
- Continue that conversation using the UUID

For complete session documentation, see [Session Management Guide](session-management.md).

---

**Time spent:** ≈ 3 minutes reading → Lifetime of organized conversations!
