# ollama-prompt

**Local Ollama CLI Tool for Deep Analysis**

## Overview

**ollama-prompt** is a cross-platform Python command-line utility to interact with a local Ollama server for advanced code analysis, prompt evaluation, and cost tracking. Send custom prompts to your preferred Ollama model and receive a structured JSON response with all server-side metadata: prompt, output, token counts, durations, and much more.

**Ideal for:**
- AGI agent orchestration
- Cost-aware code review workflows
- Analytics on token usage
- Integrating structured LLM output into your developer pipeline

## Features

- Flexible CLI flags: set prompt, model, temperature, and token count
- Prints **full verbose JSON**: includes response text, token usage (`prompt_eval_count`, `eval_count`), and engine stats
- Integrates easily into developer pipelines (PowerShell, Bash, agent loops)
- Works on Windows, Mac, Linux (Python 3.7+) with Ollama installed

***

## Installation

**Recommended (PyPI):**

```bash
pip install ollama-prompt
```

**Requirements:**
- Python 3.7 or higher
- Local Ollama server running (`ollama serve`)

**Alternative: Development/Manual Install**

Clone the repository and install in editable mode:

```bash
git clone https://github.com/dansasser/ollama-prompt.git
cd ollama-prompt
pip install -e .
```

***

## Usage

**Quick Start:**

You must have the Ollama server running locally:
```bash
ollama serve
```

**Basic Example:**
```bash
ollama-prompt --prompt "Summarize the architecture in src/modules." --model deepseek-v3.1:671b-cloud
```

**Custom Flags:**
```bash
ollama-prompt --prompt "Evaluate performance of sorting algorithms." --model deepseek-v3.1:671b-cloud --temperature 0.05 --max_tokens 4096
```

**Output Example (JSON):**
```json
{
  "model": "deepseek-v3.1:671b-cloud",
  "prompt_eval_count": 38,
  "eval_count": 93,
  "response": "...",
  "total_duration": 13300000,
  "prompt_eval_duration": 1000000,
  "eval_duration": 12200000,
  "done": true
}
```

**Advanced:**

### Inlining local files in prompts (new: @file refs)

You can reference local files directly inside a prompt using an `@` token. The CLI supports both Unix-style and Windows-style paths (forward and backslashes). When the CLI sees an `@path` token (for example `@./README.md` or `@docs\design.md`), it will read that file from disk (relative to `--repo-root`), inline its contents (bounded by `--max-file-bytes`), and send the combined prompt to the Ollama model. This lets remote orchestrators send only a short instruction like `analyze @./this-file.md` instead of embedding the full file content themselves.

Syntax and rules
- Token: `@<path>` where `<path>` must be path-like:
  - starts with `./`, `../`, `/`, `\` or
  - contains a path separator (`/` or `\`).
  This reduces accidental expansion of email-like tokens (e.g. `@user`).
- Examples of valid tokens:
  - Unix: `@./README.md`, `@src/module/file.py`, `@/home/dev/project/notes.md`
  - Windows: `@.\README.md`, `@src\module\file.py`, `@\C:\project\notes.md`
- Files are read from disk by the CLI process before calling the local Ollama server.
- Each referenced file is read up to `--max-file-bytes` bytes (default: 200000) and will be marked as `[TRUNCATED]` if larger.
- Paths are resolved relative to `--repo-root` (default: `.`). Absolute paths are allowed only if they reside inside `--repo-root`.

Examples
- Summarize a README (Unix):
```bash
ollama-prompt --prompt "@./README.md Summarize the contents of this README" --model deepseek-v3.1:671b-cloud
```

- Summarize a README (Windows PowerShell):
```powershell
ollama-prompt --prompt "@.\README.md Summarize the contents of this README" --model deepseek-v3.1:671b-cloud
```

- Ask for fixes for a file (repo located at C:\projects\app):
```bash
ollama-prompt --prompt "Find bugs in @src\app\main.py" \
  --repo-root C:\projects\app \
  --model deepseek-v3.1:671b-cloud
```

Flags to document
- `--repo-root`: Directory used to resolve `@file` references and to constrain file reads. Default is current working directory.
- `--max-file-bytes`: Maximum number of bytes to read and inline for each referenced file. Large files will be truncated and the model will see a `[TRUNCATED]` marker.
- Existing flags still apply: `--model`, `--temperature`, `--max_tokens`.

Security and operational notes
- Do not expose machines running this CLI (or its HTTP wrapper) to untrusted networks without authentication; the CLI will read local files and inline them into prompts.
- Use a restrictive `--repo-root` to avoid allowing arbitrary filesystem reads.
- Keep per-file limits (`--max-file-bytes`) conservative for very large repos.
- For reproducibility, include file metadata (commit hash or path/mtime) in prompts or outputs when necessary.
- For large repos prefer a retrieval/indexing layer (embeddings + vector DB) rather than inlining many big files in one prompt.


- Pipe results with `jq`:
  ```bash
  ollama-prompt --prompt "Critical design flaws in utils.py?" | jq .eval_count
  ```
- Integrate into agent loops or analytics dashboards via JSON output.

***

### Architecture: A Decoupled, Subprocess-as-Agent Model

`ollama-prompt` is built to be a foundational component for AGI agent orchestration. It enables a powerful, local-first architecture where a high-level orchestrator (like another AI or a CI/CD script) can spawn `ollama-prompt` commands as **decoupled, cost-aware "sub-agents."**

This subprocess model provides explicit, auditable receipts (the JSON output) for every task and allows for true OS-level parallelism.

To learn more about this design pattern and how to implement it:

* **[Subprocess Best Practices](ollama-prompt-subprocess-best-practices.md)**: A guide on how to safely and efficiently call `ollama-prompt` from a parent script.
* **[Architectural Comparison](sub-agents-compared.md)**: A document comparing this decoupled model to other integrated agent architectures.

## Troubleshooting

- If you get `ModuleNotFoundError: ollama`, ensure you ran `pip install ollama` in the correct Python environment.
- Ollama server must be running locally for requests to succeed (`ollama serve`).
- For maximum context windows, check your model’s max token support.

***

## Development & Contributing

**Editable Install:**

```bash
git clone https://github.com/dansasser/ollama-prompt.git
cd ollama-prompt
pip install -e .
```

**To contribute:**
- Fork the repo, create a branch, submit PRs.
- Open issues for bugs/feature requests.

***

## License

MIT License (see Ollama license for server terms).

## Credits

Developed by Daniel T Sasser II for robust code offload workflows, AGI agent orchestration, and token/cost analytics.

***


[1](https://pypi.org/project/ollama-prompt/)
