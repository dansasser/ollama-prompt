# ollama-prompt Documentation

**Complete guide to ollama-prompt v1.2.0 session management and best practices**

---

## Quick Navigation

### Getting Started
- [Session Management Quickstart](sessions/quickstart.md) - 5-minute introduction to sessions
- [Use Cases](guides/use-cases.md) - 12 real-world scenarios for session management

### Reference Documentation
- [Complete CLI Reference](reference.md) - Comprehensive command-line reference
- [Session Management Guide](sessions/session-management.md) - Sessions deep dive
- [AI vs Grep Verification](guides/ai-vs-grep-verification.md) - Analysis methodology guide

### Additional Resources
- [Examples](../examples/session_usage.py) - Runnable Python examples
- [Subprocess Best Practices](subprocess-best-practices.md) - Multi-agent workflow patterns
- [Architectural Comparison](sub-agents-compared.md) - Subprocess vs integrated agent systems

---

## What's New in v1.2.0

### Persistent Conversation Sessions
- **Auto-session creation** - Sessions created automatically by default
- **Context persistence** - Conversation history maintained across CLI invocations
- **Smart pruning** - Automatic context management when approaching token limits
- **Session utilities** - List, inspect, and manage sessions

### Key Features
```bash
# Auto-creates session (NEW in v1.2.0)
ollama-prompt --prompt "Hello"
# Output includes: "session_id": "abc-123-def-456"

# Continue conversation with full context
ollama-prompt --session-id abc-123-def-456 --prompt "What did I just say?"

# Opt-out for stateless operation
ollama-prompt --no-session --prompt "One-off query"
```

---

## Documentation Structure

### docs/ (this directory)
Reference documentation:
- **reference.md** - Complete CLI command reference (flags, options, examples)
- **README.md** - This navigation guide

### sessions/
Session management fundamentals:
- **quickstart.md** - Getting started in 5 minutes
- **session-management.md** - Comprehensive session guide (database, pruning, troubleshooting)

### guides/
Practical usage guides:
- **use-cases.md** - 12 real-world scenarios across 5 categories:
  - Software Development & Code Assistance
  - Data Analysis & Research
  - System Administration & DevOps
  - Learning & Knowledge Management
  - Multi-step Tasks & Automation
- **ai-vs-grep-verification.md** - AI analysis methodology and verification

### Additional Guides
Architecture and integration:
- **subprocess-best-practices.md** - Patterns for multi-agent workflows
- **sub-agents-compared.md** - Subprocess vs integrated agent architectures

---

## Common Workflows

### Multi-turn Conversations
```bash
# First question
ollama-prompt --prompt "Explain Python decorators"

# Follow-up (context preserved)
ollama-prompt --session-id <id> --prompt "Show me a practical example"

# Continue discussion
ollama-prompt --session-id <id> --prompt "How does this compare to Java annotations?"
```

### Code Review Across Files
```bash
# Start review session
ollama-prompt --prompt "Review @./src/auth.py for security issues"
# Gets session_id: abc-123

# Continue with related file (context preserved)
ollama-prompt --session-id abc-123 --prompt "Now review @./src/api.py. Does it follow the same patterns?"
```

### Subprocess Analysis (Claude Code Integration)
```bash
# Claude delegates analysis to ollama-prompt
mkdir -p ollama-output

# Analysis with session
ollama-prompt --prompt "Analyze @./codebase/module.py" \
              --model deepseek-v3.1:671b-cloud \
              > ollama-output/analysis01.json

# Continue analysis in same session
cat ollama-output/analysis01.json | python -c "import json; print(json.load(sys.stdin)['session_id'])"
# Use that session_id to continue
```

---

## Session Management Utilities

### List All Sessions
```bash
ollama-prompt --list-sessions
```

### Show Session Details
```bash
ollama-prompt --session-info <session-id>
```

### Cleanup Old Sessions
```bash
# Remove sessions older than 30 days
ollama-prompt --purge 30
```

---

## When to Use Sessions vs --no-session

### Use Sessions (default)
- Multi-turn conversations
- Code reviews across multiple files
- Iterative problem-solving
- Learning/tutorial workflows
- Debugging with context

### Use --no-session
- One-off queries
- Independent batch processing
- Testing/benchmarking
- Stateless API calls
- When context would be misleading

---

## Documentation Roadmap

### Completed
- [x] Session quickstart guide
- [x] Use cases documentation
- [x] Claude Code integration guide
- [x] Subprocess best practices

### Coming Soon
- [ ] Complete command reference
- [ ] FAQ and troubleshooting
- [ ] Advanced configuration guide
- [ ] Session storage internals
- [ ] Performance tuning guide

---

## Contributing

Found an issue or have suggestions? Please open an issue or PR at:
https://github.com/dansasser/ollama-prompt

---

## Version

**Documentation Version:** 1.2.0
**Last Updated:** 2025-11-01
**ollama-prompt Version:** v1.2.0+
