# ollama-prompt

[![PyPI version](https://badge.fury.io/py/ollama-prompt.svg)](https://badge.fury.io/py/ollama-prompt)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Quick Start](#quick-start) • [Documentation](docs/README.md) • [Use Cases](docs/guides/use-cases.md) • [Contributing](#contributing)

---

## What is ollama-prompt?

A lightweight Python CLI that transforms Ollama into a powerful analysis tool with:
- **Session persistence** - Multi-turn conversations with full context
- **Structured JSON output** - Token counts, timing, and metadata
- **File references** - Inline local files with `@file` syntax
- **Multi-agent orchestration** - Perfect for subprocess workflows

**Perfect for:** Terminal AI assistants (Claude, Codex, Gemini CLI), subprocess orchestration, and cost-aware workflows

---

## Primary Use Case: AI Agent Subprocess Integration

**Built for terminal-based AI assistants: Claude, Codex, Gemini CLI, and other interactive AI tools.**

When terminal AI agents need deep analysis but must preserve their context window, they delegate to ollama-prompt as a subprocess:

**How Claude Uses This:**
1. **Context Preservation** - Claude delegates heavy analysis without consuming its 200K token budget
2. **Structured Parsing** - JSON output with token counts, timing, and session IDs
3. **File Reference Chaining** - `@file` syntax lets Claude reference multiple files in one call
4. **Session Continuity** - Multi-turn analysis without manual context management

**Example Claude Code Workflow:**
```bash
# Claude delegates codebase analysis to ollama-prompt
ollama-prompt --prompt "Analyze @./src/auth.py for security issues" \
              --model deepseek-v3.1:671b-cloud \
              > analysis.json

# Claude parses JSON response and continues with its own reasoning
```

**Who Uses This:**
- **Primary:** Terminal AI assistants (Claude, Codex, Gemini CLI, Cursor)
- **Secondary:** Python scripts orchestrating multi-agent workflows
- **Advanced:** Custom AGI systems with local Ollama backends

**Learn More:** [Subprocess Best Practices](docs/subprocess-best-practices.md) | [Architectural Comparison](docs/sub-agents-compared.md)

---

## Features

- **Session Management** - Persistent conversations across CLI invocations
- **Rich Metadata** - Full JSON output with token counts, timing, and cost tracking
- **File References** - Reference local files with `@./path/to/file.py` syntax
- **Directory Operations** - List, tree view, and search with `@./dir/` syntax (full read access within repo root)
- **Secure File Access** - TOCTOU-safe operations with path validation via [llm-fs-tools](https://github.com/dansasser/llm-filesystem-tools)
- **Subprocess-Friendly** - Designed for agent orchestration and automation
- **Cloud & Local Models** - Works with both Ollama cloud models and local instances
- **Cross-Platform** - Windows, macOS, Linux with Python 3.10+

---

## Quick Start

**Prerequisites:** [Ollama CLI installed](https://ollama.com) (server starts automatically)

```bash
# 1. Install
pip install ollama-prompt

# 2. First question (creates session automatically)
ollama-prompt --prompt "What is 2+2?"

# 3. Follow-up with context
ollama-prompt --session-id <id-from-output> --prompt "What about 3+3?"
```

**Session created automatically!** See `session_id` in output.

**Next steps:** [5-Minute Tutorial](docs/sessions/quickstart.md) | [Full CLI Reference](docs/reference.md)

---

## Installation

### PyPI (Recommended)
```bash
pip install ollama-prompt
```

### Development Install
```bash
git clone https://github.com/dansasser/ollama-prompt.git
cd ollama-prompt
pip install -e .
```

### Prerequisites
- Python 3.10 or higher
- [Ollama](https://ollama.com) installed and running
- For cloud models: `ollama signin` (one-time authentication)

**Verify installation:**
```bash
ollama-prompt --help
ollama list  # Check available models
```

**Full setup guide:** [Prerequisites Documentation](docs/reference.md#prerequisites--setup)

---

## Usage

### Basic Example
```bash
ollama-prompt --prompt "Explain Python decorators" \
              --model deepseek-v3.1:671b-cloud
```

### Multi-Turn Conversation
```bash
# First question
ollama-prompt --prompt "Who wrote Hamlet?" > out.json

# Follow-up (remembers context)
SESSION_ID=$(jq -r '.session_id' out.json)
ollama-prompt --session-id $SESSION_ID --prompt "When was he born?"
```

### File Analysis
```bash
ollama-prompt --prompt "Review @./src/auth.py for security issues"
```

### Directory Operations

Reference entire directories with the `@./dir/` syntax:

```bash
# List directory contents
ollama-prompt --prompt "What's in @./src/?"

# Show directory tree
ollama-prompt --prompt "Show the structure: @./src/:tree"

# Search for pattern in files
ollama-prompt --prompt "Find TODO comments: @./src/:search:TODO"
```

> **⚠️ Security Note:** `ollama-prompt` has **read access to all files and directories** within the current working directory (repository root). File operations are TOCTOU-safe and validate paths to prevent traversal attacks, but the tool can read any accessible file. Only run in trusted directories.

**Directory Syntax:**
| Syntax | Description | Example |
|--------|-------------|---------|
| `@./dir/` | List directory contents | `@./src/` |
| `@./dir/:list` | Explicit list operation | `@./src/:list` |
| `@./dir/:tree` | Directory tree (depth=3) | `@./src/:tree` |
| `@./dir/:search:PATTERN` | Search for pattern | `@./src/:search:TODO` |

### Stateless Mode
```bash
ollama-prompt --prompt "Quick question" --no-session
```

**More examples:** [Use Cases Guide](docs/guides/use-cases.md) with 12 real-world scenarios

---

## Documentation

**[Complete Documentation](docs/README.md)** - Full guide navigation and reference

**Quick Links:**
- [5-Minute Quick Start](docs/sessions/quickstart.md)
- [Session Management Guide](docs/sessions/session-management.md)
- [Complete CLI Reference](docs/reference.md)

---

## Use Cases

**Software Development:**
- Multi-file code review with shared context
- Iterative debugging sessions
- Architecture analysis across modules

**Multi-Agent Systems:**
- Subprocess-based agent orchestration
- Context-aware analysis pipelines
- Cost tracking for LLM operations

**Data Analysis:**
- Sequential data exploration with memory
- Research workflows with source tracking
- Report generation with conversation history

**See all 12 scenarios:** [Use Cases Guide](docs/guides/use-cases.md)

---

## Why ollama-prompt?

`ollama-prompt` is a specialized tool. It's not a general-purpose CLI, but an **automation-first subprocess** designed to be called by other AI agents (like Claude or Gemini) to preserve their primary context window.

This table clarifies its niche compared to other common tools:

### Comparison of Ollama Interaction Methods

| Feature | **1. Direct Ollama API** | **2. `llm` (Simon Willison's Tool)** | **3. `ollama-prompt` (This Tool)** |
| :--- | :--- | :--- | :--- |
| **Primary Use** | Building custom applications (backend). | **Human-facing CLI:** A "workbench" for a user to interact with models. | **Automation-facing CLI:** A "subprocess" for *other programs* to call. |
| **Interface** | Raw HTTP / Code Library | Interactive, user-friendly CLI. | Single-line CLI command designed for scripts. |
| **Key "Win"** | Total flexibility. | **Universality:** Supports Ollama, OpenAI, Anthropic, etc. | **Automation:** Built to be called by other AI agents (like Claude/Gemini). |
| **Output Format** | Raw JSON response. | Plain text (default), with a flag for JSON (`--json`). | **Structured JSON** (default), with rich metadata (tokens, time). |
| **Session Memory** | **Manual:** You must track and resend the entire message history. | **Automatic:** Logs all prompts/responses to a local SQLite DB. | **Automatic (via flag):** Uses `--session-id` to persist context. |
| **File Handling** | **Manual:** Requires code to read the file and inject its content. | **Manual (via piping):** Requires `cat file.py \| llm -s "..."` | **Built-in:** `@./file.py` for files, `@./dir/` for directories (full read access). |

**Built for:**
- **Terminal AI assistants (Claude, Codex, Gemini CLI)** - Delegate analysis via subprocess
- **Context preservation** - Save your AI's token budget for reasoning
- **Multi-agent systems** - Orchestrate parallel analysis tasks
- **Cost-aware workflows** - Track token usage explicitly

**Architecture:** [Subprocess Best Practices](docs/subprocess-best-practices.md) | [Architectural Comparison](docs/sub-agents-compared.md)

---

## Troubleshooting

- If you get `ModuleNotFoundError: ollama`, ensure you ran `pip install ollama` in the correct Python environment.
- Ensure Ollama CLI is installed (`ollama --version` should work). The server starts automatically when needed.
- For maximum context windows, check your model's max token support.
- **Unexpected session_id in output?** Sessions are auto-created by default in v1.2.0+. This is normal behavior. Use `--no-session` for stateless operation.
- **Session context not persisting?** Ensure you're using the same `--session-id` value across invocations. Use `--list-sessions` to see available sessions.

---

## Contributing

We welcome contributions! Here's how to get started:

**Development Setup:**
```bash
git clone https://github.com/dansasser/ollama-prompt.git
cd ollama-prompt
pip install -e .
```

**Running Tests:**
```bash
pytest
```

**Contribution Guidelines:**
- Fork the repo and create a branch
- Write tests for new features
- Follow existing code style
- Submit PR with clear description

**Areas We Need Help:**
- Documentation improvements
- New use case examples
- Bug reports and fixes
- Feature suggestions

**Questions?** Open an [issue](https://github.com/dansasser/ollama-prompt/issues) or discussion.

---

## Community & Support

- **Bug Reports:** [GitHub Issues](https://github.com/dansasser/ollama-prompt/issues)
- **Discussions:** [GitHub Discussions](https://github.com/dansasser/ollama-prompt/discussions)
- **Documentation:** [docs/README.md](docs/README.md)
- **Troubleshooting:** [Reference Guide](docs/reference.md#troubleshooting-common-issues)

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

**Third-Party Licenses:**
- Uses [Ollama](https://ollama.com) (separate licensing)

---

## Credits

**Author:** [Daniel T. Sasser II](./AUTHOR)
- GitHub: [github.com/dansasser](https://github.com/dansasser)
- Blog: [dansasser.me](https://dansasser.me)

**Built With:**
- [Ollama](https://ollama.com) - Local LLM runtime
- [Python](https://python.org) - Language and ecosystem

**Acknowledgments:**
- Inspired by the need for structured, cost-aware LLM workflows
- Built for the AI agent orchestration community

---

[PyPI Package](https://pypi.org/project/ollama-prompt/)
