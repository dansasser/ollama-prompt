# Model Manifest System Implementation Plan

## Overview

ollama-prompt needs a model management system to:
1. Auto-detect available Ollama models and their capabilities
2. Store user preferences for which model to use for which task
3. Provide fallback chains when preferred models aren't available
4. Enable semantic scoring via embedding models

## Task Types

| Task | Description | Default Capability Detection |
|------|-------------|------------------------------|
| vision | Image analysis, OCR, screenshots, diagrams | `vl`, `vision`, `visual`, `multimodal` in name |
| architecture | System design, architectural analysis | Same as code + reasoning |
| code | Code review, security analysis, refactoring | `code`, `coder`, `deepseek`, `kimi` in name |
| reasoning | Multi-step reasoning, complex analysis | `thinking`, `reason` in name |
| security | Security analysis, vulnerability detection | Same as code |
| performance | Performance analysis, bottleneck detection | Same as code |
| general | General purpose / chat | Default fallback |
| embedding | Vector embeddings for semantic scoring | `embed`, `nomic`, `mxbai` in name |

## Manifest File

**Location (cross-platform):**
- **Windows:** `%APPDATA%\ollama-prompt\model-manifest.json`
- **macOS:** `~/Library/Application Support/ollama-prompt/model-manifest.json`
- **Linux:** `~/.config/ollama-prompt/model-manifest.json`

**Schema:**
```json
{
  "version": "1.0",
  "last_scan": "2025-12-13T10:30:00",
  "models": {
    "deepseek-v3.2:cloud": {
      "capabilities": ["code", "reasoning", "security", "performance"],
      "context_length": 128000,
      "supports_embedding": false,
      "auto_discovered": true
    },
    "nomic-embed-text": {
      "capabilities": ["embedding"],
      "embedding_dimensions": 768,
      "supports_embedding": true,
      "auto_discovered": true
    },
    "qwen3-next:80b-cloud": {
      "capabilities": ["vision", "code", "reasoning", "architecture"],
      "context_length": 128000,
      "supports_embedding": false,
      "auto_discovered": true
    }
  },
  "task_assignments": {
    "vision": "qwen3-next:80b-cloud",
    "architecture": "qwen3-next:80b-cloud",
    "code": "deepseek-v3.2:cloud",
    "reasoning": "deepseek-v3.2:cloud",
    "security": "deepseek-v3.2:cloud",
    "performance": "deepseek-v3.2:cloud",
    "general": "deepseek-v3.2:cloud",
    "embedding": "nomic-embed-text"
  },
  "fallback_chains": {
    "embedding": ["nomic-embed-text", "mxbai-embed-large", "all-minilm"],
    "vision": ["qwen3-vl:235b-instruct-cloud", "llava"],
    "code": ["deepseek-v3.2:cloud", "kimi-k2-thinking:cloud", "codellama"],
    "general": ["mistral-large-3:675b-cloud", "llama3.1"]
  }
}
```

## CLI Interface

### Model Scanning

```bash
# First run auto-scans, or manually trigger:
ollama-prompt --scan-models

# Output:
# Scanning available ollama models...
# Found 12 models
# Detected capabilities:
#   - deepseek-v3.2:cloud: code, reasoning, security, performance
#   - nomic-embed-text: embedding
#   - qwen3-next:80b-cloud: vision, code, reasoning
# Manifest saved to platform-specific config directory
```

### Setting Task Models

```bash
# Set specific model for a task type
ollama-prompt --set-vision-model qwen3-vl:235b-instruct-cloud
ollama-prompt --set-code-model deepseek-v3.2:cloud
ollama-prompt --set-embedding-model nomic-embed-text
ollama-prompt --set-general-model mistral-large-3:675b-cloud

# Each updates the manifest and confirms:
# Updated vision model to: qwen3-vl:235b-instruct-cloud
```

### Viewing Configuration

```bash
# Show current model assignments
ollama-prompt --show-models

# Output:
# Model Assignments:
# | Task         | Model                      | Status    |
# |--------------|----------------------------|-----------|
# | vision       | qwen3-next:80b-cloud       | available |
# | architecture | qwen3-next:80b-cloud       | available |
# | code         | deepseek-v3.2:cloud        | available |
# | reasoning    | deepseek-v3.2:cloud        | available |
# | security     | deepseek-v3.2:cloud        | available |
# | performance  | deepseek-v3.2:cloud        | available |
# | general      | mistral-large-3:675b-cloud | available |
# | embedding    | nomic-embed-text           | available |
```

## Implementation Modules

### 1. `ollama_prompt/model_scanner.py`

```python
"""
Model scanning and capability detection.
"""

class ModelScanner:
    """Scans ollama for available models and detects capabilities."""

    # Capability detection patterns
    CAPABILITY_PATTERNS = {
        "vision": ["vl", "vision", "visual", "multimodal", "llava"],
        "code": ["code", "coder", "deepseek", "kimi", "codellama"],
        "reasoning": ["thinking", "reason", "kimi"],
        "embedding": ["embed", "nomic", "mxbai", "minilm", "bge"],
        "general": ["llama", "mistral", "qwen", "gemma", "phi"]
    }

    # Known model families and their capabilities
    FAMILY_CAPABILITIES = {
        "deepseek": ["code", "reasoning", "security", "performance"],
        "kimi": ["code", "reasoning", "architecture", "security"],
        "qwen": ["vision", "code", "general"],
        "nomic": ["embedding"],
        "mxbai": ["embedding"],
        "llava": ["vision"],
        "mistral": ["general", "code"]
    }

    def scan(self) -> List[Dict]:
        """Scan ollama list and return model info."""
        pass

    def detect_capabilities(self, model_name: str) -> List[str]:
        """Detect capabilities from model name patterns."""
        pass

    def check_embedding_support(self, model_name: str) -> bool:
        """Test if model supports embedding API."""
        pass
```

### 2. `ollama_prompt/model_manifest.py`

```python
"""
Model manifest storage and retrieval.
"""

class ModelManifest:
    """Manages the model manifest file."""

    DEFAULT_PATH = Path.home() / ".config" / "ollama-prompt" / "model-manifest.json"

    def __init__(self, path: Optional[Path] = None):
        self.path = path or self.DEFAULT_PATH
        self._data = None

    def load(self) -> Dict:
        """Load manifest from disk."""
        pass

    def save(self) -> None:
        """Save manifest to disk."""
        pass

    def get_model_for_task(self, task: str) -> Optional[str]:
        """Get assigned model for task type."""
        pass

    def set_model_for_task(self, task: str, model: str) -> None:
        """Set model for task type."""
        pass

    def get_embedding_model(self) -> Optional[str]:
        """Get the configured embedding model."""
        pass

    def get_fallback_chain(self, task: str) -> List[str]:
        """Get fallback models for task."""
        pass

    def update_from_scan(self, scan_results: List[Dict]) -> None:
        """Update manifest with scan results."""
        pass
```

### 3. Integration Points

**VectorEmbedder:**
```python
# Before (hardcoded):
DEFAULT_MODEL = "nomic-embed-text"

# After (manifest-aware):
def __init__(self, model: str = None, manifest: ModelManifest = None):
    self.manifest = manifest or ModelManifest()
    self.model = model or self.manifest.get_embedding_model() or "nomic-embed-text"
```

**CLI (cli.py):**
```python
# Add model management argument group
model_group = parser.add_argument_group("Model Configuration")
model_group.add_argument("--scan-models", action="store_true")
model_group.add_argument("--show-models", action="store_true")
model_group.add_argument("--set-vision-model", type=str)
model_group.add_argument("--set-code-model", type=str)
model_group.add_argument("--set-embedding-model", type=str)
model_group.add_argument("--set-general-model", type=str)
# ... etc for other task types
```

**SessionManager:**
```python
# Pass manifest to ContextManager which passes to VectorEmbedder
def __init__(self, db_path=None, manifest=None):
    self.manifest = manifest or ModelManifest()
    # ...
```

## First Run Behavior

1. Check if manifest exists in platform-specific config directory
2. If not, auto-run scan:
   - Call `ollama list`
   - Detect capabilities for each model
   - Auto-assign best models per task type
   - Save manifest
3. Print summary of detected models and assignments
4. Continue with normal operation

## Compatibility with claude-ollama-agents Plugin

If `~/.claude/model-capabilities.json` exists:
- Read it as additional source of model info
- Merge capabilities (union of both)
- Prefer ollama-prompt's own manifest for task assignments

This allows users who have the Claude plugin to benefit from its model scanning, while ollama-prompt remains standalone.

## File Structure After Implementation

```text
ollama_prompt/
  __init__.py
  cli.py                    # Add model management flags
  model_scanner.py          # NEW - scan and detect capabilities
  model_manifest.py         # NEW - manifest storage/retrieval
  vector_embedder.py        # UPDATE - use manifest for model selection
  context_manager.py        # UPDATE - pass manifest through
  session_manager.py        # UPDATE - integrate ContextManager
  session_db.py
  file_chunker.py
  ...
```

## Testing

New test files:
- `tests/test_model_scanner.py` - Test capability detection patterns
- `tests/test_model_manifest.py` - Test manifest CRUD operations

## Migration

Existing users:
- First run after update will auto-scan and create manifest
- No breaking changes to existing CLI usage
- New flags are additive

## Future Enhancements

1. `--import-claude-manifest` - Import from claude-ollama-agents plugin
2. `--export-manifest` - Export manifest for sharing
3. Model benchmarking - Test response quality per task type
4. Auto-update - Periodic re-scan to detect new models
