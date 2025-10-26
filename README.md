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
- Pipe results with `jq`:
  ```bash
  ollama-prompt --prompt "Critical design flaws in utils.py?" | jq .eval_count
  ```
- Integrate into agent loops or analytics dashboards via JSON output.

***

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
