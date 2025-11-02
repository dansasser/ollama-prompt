# ollama-prompt

[![PyPI version](https://badge.fury.io/py/ollama-prompt.svg)](https://badge.fury.io/py/ollama-prompt)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
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
- **Subprocess-Friendly** - Designed for agent orchestration and automation
- **Cloud & Local Models** - Works with both Ollama cloud models and local instances
- **Cross-Platform** - Windows, macOS, Linux with Python 3.7+

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
- Python 3.7 or higher
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

**vs. Direct Ollama API:**
- Session persistence (no manual context management)
- Structured JSON output (token counts, timing, metadata)
- File reference syntax (no manual file reading)

**vs. Other CLI Tools:**
- Session-first design (context by default)
- Subprocess-optimized (perfect for agent orchestration)
- Local-first (SQLite, no cloud dependency)

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
