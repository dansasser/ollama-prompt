# Context Window Optimization Strategy for ollama-prompt

## Executive Summary

This document outlines a practical strategy for implementing intelligent chunking and context window optimization in `ollama-prompt`. The goal is to reduce context window usage by 60-80% while maintaining or improving the usefulness of file references in prompts.

## The Problem

Currently, when a user references a file using `@./file.py`, the entire file content (up to 200KB) is embedded directly into the prompt. This creates several issues:

| Issue | Impact | Example |
|-------|--------|---------|
| **Context window bloat** | Large files consume most of the available context, leaving little room for conversation history | A 50KB file uses ~12,500 tokens, leaving only ~3,500 tokens in a 16K context window |
| **Irrelevant content** | Users often need only a small portion of a file, but get everything | Asking about one function in a 1000-line file sends all 1000 lines |
| **Poor scalability** | Referencing multiple files quickly exhausts the context window | 5 files × 50KB = 250KB ≈ 62,500 tokens (exceeds most models) |

## The Solution: Three-Tier Chunking Strategy

### Tier 1: Smart Summarization (Default)

When a file is referenced, instead of sending the full content, send a **structured summary** that preserves navigability while drastically reducing tokens.

**For code files:**
```
--- FILE: src/user_manager.py (SUMMARY) ---
Language: Python
Size: 1,247 lines, 45.2 KB
Last modified: 2024-12-07

Structure:
  - Imports: requests, sqlite3, hashlib, datetime
  - Classes:
    • UserManager (lines 45-890)
      - __init__(db_path)
      - create_user(username, email, password)
      - authenticate(username, password)
      - update_profile(user_id, **kwargs)
      - delete_user(user_id)
    • UserSession (lines 895-1100)
      - start_session(user_id)
      - validate_token(token)
      - end_session(session_id)
  - Functions:
    • hash_password(password) (line 25)
    • validate_email(email) (line 35)
  - Constants: MAX_LOGIN_ATTEMPTS=5, SESSION_TIMEOUT=3600

To see full content, use: @./src/user_manager.py:full
To see specific function, use: @./src/user_manager.py:create_user
--- FILE: src/user_manager.py (SUMMARY) END ---
```

**Context window savings:** ~95% (from 45KB to ~2KB)

**For text/markdown files:**
```
--- FILE: README.md (SUMMARY) ---
Type: Markdown documentation
Size: 523 lines, 18.4 KB

Sections:
  1. Installation (lines 1-45)
  2. Quick Start (lines 46-120)
  3. Configuration (lines 121-280)
  4. API Reference (lines 281-450)
  5. Contributing (lines 451-523)

Key topics: installation, configuration, API usage, contributing guidelines

To see full content, use: @./README.md:full
To see specific section, use: @./README.md:section:Installation
--- FILE: README.md (SUMMARY) END ---
```

**Context window savings:** ~90% (from 18KB to ~1.8KB)

### Tier 2: Targeted Extraction (User-Specified)

Allow users to request specific portions of a file using enhanced syntax:

| Syntax | What It Does | Context Savings |
|--------|--------------|-----------------|
| `@./file.py:full` | Send entire file (current behavior) | 0% (baseline) |
| `@./file.py:function_name` | Extract and send only the specified function/class | 80-95% |
| `@./file.py:lines:100-150` | Send only lines 100-150 | 70-99% |
| `@./file.py:section:Configuration` | Extract markdown section by heading | 60-90% |
| `@./file.py:search:pattern` | Send only lines matching pattern with context | 85-98% |

**Example - Function extraction:**
```python
# User prompt: "Explain how authentication works @./user_manager.py:authenticate"

# What gets sent to the model:
--- FILE: src/user_manager.py:authenticate ---
def authenticate(self, username, password):
    """
    Authenticate a user with username and password.
    
    Args:
        username: User's username
        password: Plain text password to verify
        
    Returns:
        dict: User data if successful, None if failed
    """
    user = self.db.get_user_by_username(username)
    if not user:
        return None
        
    if user['login_attempts'] >= MAX_LOGIN_ATTEMPTS:
        raise SecurityError("Account locked due to too many failed attempts")
        
    password_hash = hash_password(password)
    if password_hash == user['password_hash']:
        self.db.reset_login_attempts(user['id'])
        return user
    else:
        self.db.increment_login_attempts(user['id'])
        return None
--- FILE: src/user_manager.py:authenticate END ---
```

**Context window savings:** 95% (from 45KB to ~2KB)

### Tier 3: Semantic Chunking with Embeddings (Advanced)

For very large files or codebases, implement semantic chunking with vector embeddings:

1. **Chunk files intelligently** - split by function/class boundaries, not arbitrary line counts
2. **Generate embeddings** - use Ollama's embedding models (`nomic-embed-text`)
3. **Store in session DB** - extend SQLite with vector extension or use separate vector DB
4. **Query by relevance** - when a file is referenced, retrieve only the most relevant chunks

**Example workflow:**
```
User: "How does password hashing work? @./src/"

System:
1. Embeds the query: "How does password hashing work?"
2. Searches all chunks in src/ for semantic similarity
3. Retrieves top 3 most relevant chunks:
   - user_manager.py:hash_password (similarity: 0.92)
   - security.py:generate_salt (similarity: 0.78)
   - config.py:PASSWORD_HASH_ALGORITHM (similarity: 0.65)
4. Sends only those 3 chunks to the model
```

**Context window savings:** 90-98% (only relevant chunks sent)

## Implementation Plan

### Phase 1: Smart Summarization (Immediate - 2-3 days)

**Step 1:** Create a new module `ollama_prompt/file_chunker.py`

```python
import ast
import re
from typing import Dict, List, Any
from pathlib import Path

class FileChunker:
    """Intelligent file chunking and summarization."""
    
    def summarize_python(self, content: str, path: str) -> Dict[str, Any]:
        """Generate structured summary of Python file."""
        try:
            tree = ast.parse(content)
            
            summary = {
                "type": "python",
                "path": path,
                "lines": len(content.splitlines()),
                "size_kb": len(content) / 1024,
                "imports": self._extract_imports(tree),
                "classes": self._extract_classes(tree),
                "functions": self._extract_functions(tree),
                "constants": self._extract_constants(tree),
            }
            
            return summary
        except SyntaxError:
            return {"type": "python", "error": "Syntax error in file"}
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict]:
        """Extract class definitions with methods."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    {
                        "name": m.name,
                        "line": m.lineno
                    }
                    for m in node.body
                    if isinstance(m, ast.FunctionDef)
                ]
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": methods
                })
        return classes
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict]:
        """Extract top-level function definitions."""
        functions = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "line": node.lineno
                })
        return functions
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        return list(set(imports))[:10]  # Limit to 10 most important
    
    def _extract_constants(self, tree: ast.AST) -> List[Dict]:
        """Extract module-level constants."""
        constants = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        constants.append({
                            "name": target.id,
                            "line": node.lineno
                        })
        return constants[:10]  # Limit to 10
    
    def format_summary(self, summary: Dict) -> str:
        """Format summary as readable text for model."""
        lines = [
            f"Language: Python",
            f"Size: {summary['lines']} lines, {summary['size_kb']:.1f} KB",
            "",
            "Structure:"
        ]
        
        if summary.get('imports'):
            lines.append(f"  - Imports: {', '.join(summary['imports'][:5])}")
        
        if summary.get('classes'):
            lines.append("  - Classes:")
            for cls in summary['classes']:
                lines.append(f"    • {cls['name']} (line {cls['line']})")
                for method in cls['methods'][:5]:
                    lines.append(f"      - {method['name']}")
        
        if summary.get('functions'):
            lines.append("  - Functions:")
            for func in summary['functions'][:10]:
                lines.append(f"    • {func['name']} (line {func['line']})")
        
        if summary.get('constants'):
            lines.append("  - Constants:")
            for const in summary['constants']:
                lines.append(f"    • {const['name']} (line {const['line']})")
        
        lines.extend([
            "",
            f"To see full content, use: @{summary['path']}:full",
            f"To see specific function, use: @{summary['path']}:function_name"
        ])
        
        return "\n".join(lines)
```

**Step 2:** Modify `cli.py` to use summarization by default

```python
def read_file_snippet(path, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES, mode="summary"):
    """
    Safely read a file with optional summarization.
    
    Args:
        path: File path
        repo_root: Repository root
        max_bytes: Max bytes to read
        mode: "summary" (default), "full", or "extract:target"
    """
    # Read file securely
    result = read_file_secure(path, repo_root, max_bytes, audit=True)
    
    if not result["ok"]:
        return result
    
    # If mode is summary and file is large enough, summarize
    if mode == "summary" and len(result["content"]) > 5000:  # 5KB threshold
        chunker = FileChunker()
        
        # Detect file type
        if path.endswith('.py'):
            summary = chunker.summarize_python(result["content"], path)
            result["content"] = chunker.format_summary(summary)
            result["summarized"] = True
        # Add more file types: .js, .md, .java, etc.
    
    return result
```

**Step 3:** Update the file reference parser to support new syntax

```python
def expand_file_refs_in_prompt(prompt, repo_root=".", max_bytes=DEFAULT_MAX_FILE_BYTES):
    """Enhanced file reference expansion with chunking support."""
    
    # Updated pattern to capture mode suffix
    # Examples: @./file.py, @./file.py:full, @./file.py:function_name
    pattern = re.compile(r"@((?:\.\.?[/\\]|[/\\])[^\s@?!,;]+?)(?::(\w+))?(?:\b|$)")
    
    def _repl(m):
        path = m.group(1)
        mode = m.group(2) or "summary"  # Default to summary
        
        # Handle directory operations (existing code)
        if path.endswith('/') or ':list' in path or ':tree' in path:
            # ... existing directory handling ...
            pass
        else:
            # File reference with mode
            if mode == "full":
                res = read_file_snippet(path, repo_root, max_bytes, mode="full")
                label = f"FILE: {path} (FULL)"
            elif mode == "summary":
                res = read_file_snippet(path, repo_root, max_bytes, mode="summary")
                label = f"FILE: {path} (SUMMARY)"
            else:
                # Extract specific function/class
                res = extract_code_element(path, mode, repo_root, max_bytes)
                label = f"FILE: {path}:{mode}"
            
            if not res["ok"]:
                return f"\n\n--- {label} (ERROR: {res['error']}) ---\n"
            
            return (
                f"\n\n--- {label} START ---\n"
                f"{res['content']}\n"
                f"--- {label} END ---\n\n"
            )
    
    return pattern.sub(_repl, prompt)
```

### Phase 2: Targeted Extraction (1 week)

Implement function/class extraction using AST parsing:

```python
def extract_code_element(path: str, element_name: str, repo_root: str, max_bytes: int) -> Dict:
    """Extract a specific function or class from a Python file."""
    result = read_file_secure(path, repo_root, max_bytes, audit=True)
    
    if not result["ok"]:
        return result
    
    try:
        tree = ast.parse(result["content"])
        lines = result["content"].splitlines()
        
        # Search for the element
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name == element_name:
                    # Extract the source code for this node
                    start_line = node.lineno - 1
                    end_line = node.end_lineno
                    
                    extracted = "\n".join(lines[start_line:end_line])
                    
                    return {
                        "ok": True,
                        "path": path,
                        "content": extracted,
                        "element": element_name,
                        "lines": f"{start_line + 1}-{end_line}"
                    }
        
        return {
            "ok": False,
            "path": path,
            "error": f"Element '{element_name}' not found in file"
        }
    
    except SyntaxError as e:
        return {"ok": False, "path": path, "error": f"Syntax error: {e}"}
```

### Phase 3: Semantic Chunking (2-3 weeks)

**Step 1:** Extend session database schema

```sql
-- Add to session_db.py schema
CREATE TABLE IF NOT EXISTS file_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL,  -- 'function', 'class', 'section'
    chunk_name TEXT NOT NULL,  -- function/class name
    content TEXT NOT NULL,
    embedding BLOB,  -- Store as binary
    line_start INTEGER,
    line_end INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX idx_file_chunks_session ON file_chunks(session_id);
CREATE INDEX idx_file_chunks_path ON file_chunks(file_path);
```

**Step 2:** Implement embedding generation

```python
import ollama
import numpy as np

class EmbeddingManager:
    """Generate and manage embeddings for code chunks."""
    
    def __init__(self, model="nomic-embed-text"):
        self.model = model
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text using Ollama."""
        response = ollama.embeddings(model=self.model, prompt=text)
        return np.array(response["embedding"])
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def find_relevant_chunks(
        self, 
        query: str, 
        chunks: List[Dict], 
        top_k: int = 3
    ) -> List[Dict]:
        """Find most relevant chunks for a query."""
        query_embedding = self.generate_embedding(query)
        
        # Calculate similarity for each chunk
        similarities = []
        for chunk in chunks:
            chunk_embedding = np.frombuffer(chunk["embedding"], dtype=np.float32)
            similarity = self.cosine_similarity(query_embedding, chunk_embedding)
            similarities.append((similarity, chunk))
        
        # Sort by similarity and return top k
        similarities.sort(reverse=True, key=lambda x: x[0])
        return [chunk for _, chunk in similarities[:top_k]]
```

## Expected Results

| Metric | Before | After (Phase 1) | After (Phase 3) |
|--------|--------|-----------------|-----------------|
| **Avg tokens per file reference** | 12,500 | 500 | 200 |
| **Context window savings** | 0% | 96% | 98% |
| **Files per prompt** | 2-3 | 10-15 | 20-30 |
| **Relevance accuracy** | N/A | N/A | 85-90% |

## Migration Path

**For existing users:**
- Default behavior changes to summarization
- Add `--full-files` flag to restore old behavior
- Update documentation with new syntax

**Backward compatibility:**
- `@./file.py` → summary (new default)
- `@./file.py:full` → full content (old behavior)

## Next Steps

1. **Implement Phase 1** (smart summarization) - highest ROI, lowest complexity
2. **Test with real codebases** - measure actual context window savings
3. **Gather user feedback** - determine if Phase 2/3 are needed
4. **Iterate** - refine chunking strategies based on usage patterns

Would you like me to start implementing Phase 1 for you?
