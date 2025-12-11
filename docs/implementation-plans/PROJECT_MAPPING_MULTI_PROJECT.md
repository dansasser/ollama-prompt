# Project Mapping: Multi-Project Scenarios

**Date:** December 8, 2025  
**Addendum to:** PROJECT_MAPPING_DESIGN.md  
**Topic:** Handling multiple projects, nested projects, and cross-project tasks

---

## The Scenarios You're Asking About

### 1. Opening at Different Levels

**Scenario:**
```bash
# User might do any of these:
ollama-prompt --project ./                    # Root (monorepo)
ollama-prompt --project ./backend             # Just backend
ollama-prompt --project ./frontend            # Just frontend
ollama-prompt --project ./backend/api         # Nested sub-project
```

**Question:** Does each get mapped separately? Are they related?

### 2. Tasks Spanning Multiple Projects

**Scenario:**
```bash
# User wants to work across projects:
ollama-prompt --project ./backend --project ./frontend \
  --prompt "Add a new user profile endpoint and update the UI"
```

**Question:** Can you specify multiple projects? How does the agent navigate between them?

### 3. Nested/Related Projects

**Scenario:**
```
my-app/
├── backend/     (Python, Flask)
├── frontend/    (React)
├── shared/      (TypeScript types)
└── docker/      (Config)
```

**Question:** If you map `./`, does it understand the sub-projects? Or do you need to map each separately?

---

## The Answer: Yes, I Considered It (But Didn't Make It Explicit)

### What I Already Designed

The database schema I created **does** support multiple projects:

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,  -- ← Each project gets unique ID
    root_path TEXT NOT NULL,      -- ← Different paths = different projects
    ...
);
```

**This means:**
- `./` → project_id: `root-abc123`
- `./backend` → project_id: `backend-def456`
- `./frontend` → project_id: `frontend-ghi789`

**All three can coexist in the database.**

### What I Didn't Design

**Multi-project relationships:**
- No `parent_project_id` field (for nested projects)
- No `--project` flag accepting multiple values
- No cross-project dependency tracking
- No "active projects" concept (which projects are in current session)

**Let me fix that.**

---

## Updated Design: Multi-Project Support

### Database Schema Changes

#### Add to `projects` table:

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    root_path TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_scanned_at TEXT NOT NULL,
    file_count INTEGER,
    total_size_kb INTEGER,
    entry_points TEXT,
    languages TEXT,
    
    -- NEW: Multi-project support
    parent_project_id TEXT,           -- NULL if root project
    project_type TEXT,                -- 'root', 'subproject', 'standalone'
    related_projects TEXT,            -- JSON array of related project_ids
    
    FOREIGN KEY (parent_project_id) REFERENCES projects(project_id)
);
```

#### New table: `session_projects`

```sql
CREATE TABLE session_projects (
    session_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,  -- One primary project per session
    added_at TEXT NOT NULL,
    PRIMARY KEY (session_id, project_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
```

**Purpose:** Track which projects are active in each session.

---

## Scenario 1: Opening at Different Levels

### How It Works

**User opens root:**
```bash
ollama-prompt --project ./
```

**What happens:**
1. Scans `./` and detects sub-projects (backend/, frontend/)
2. Creates project entries:
   - `root-abc123` (parent, type='root')
   - `backend-def456` (child, parent_id='root-abc123', type='subproject')
   - `frontend-ghi789` (child, parent_id='root-abc123', type='subproject')
3. Injects **hierarchical summary** into context:

```
PROJECT: my-app (root)
├── backend/ (Python, 25 files)
│   └── Entry: main.py, api.py
├── frontend/ (React, 30 files)
│   └── Entry: index.tsx, App.tsx
└── shared/ (TypeScript, 5 files)
```

**User opens sub-project:**
```bash
ollama-prompt --project ./backend
```

**What happens:**
1. Scans `./backend` only
2. Creates project entry (or loads existing):
   - `backend-def456` (type='standalone' if no parent detected)
3. Injects **focused summary**:

```
PROJECT: backend (Python)
Entry: main.py, api.py
Modules: database/ (5), api/ (10), utils/ (8)
```

### The Rule

**Each path gets its own project_id, but the system detects relationships.**

---

## Scenario 2: Tasks Spanning Multiple Projects

### CLI Support for Multiple Projects

**New syntax:**
```bash
# Multiple --project flags
ollama-prompt --project ./backend --project ./frontend \
  --prompt "Add user profile endpoint and update UI"

# Or comma-separated
ollama-prompt --project ./backend,./frontend \
  --prompt "Add user profile endpoint and update UI"
```

### How It Works

**What happens:**
1. Both projects are scanned/loaded
2. Both are added to `session_projects` table
3. **Combined summary** injected into context:

```
ACTIVE PROJECTS (2):

PROJECT 1: backend (primary)
├── Entry: main.py, api.py
└── Modules: database/, api/, utils/

PROJECT 2: frontend
├── Entry: index.tsx, App.tsx
└── Modules: components/, services/, hooks/

CROSS-PROJECT NOTES:
- frontend/services/api.ts calls backend API
- shared/ types used by both
```

**Context usage:** ~4KB (2KB per project)

### Primary vs. Secondary Projects

**The first `--project` is primary:**
```bash
ollama-prompt --project ./backend --project ./frontend
#                       ^^^^^^^^^ primary
```

**Why it matters:**
- Agent starts work in primary project
- File references default to primary (e.g., `@./main.py` = `backend/main.py`)
- Secondary projects are "context" for understanding dependencies

**To reference secondary project files:**
```bash
@frontend:./App.tsx  # Explicit project prefix
```

---

## Scenario 3: Nested/Related Projects (Monorepo)

### Automatic Sub-Project Detection

**When you map a root project, the system detects sub-projects:**

**Directory structure:**
```
my-app/
├── backend/
│   ├── pyproject.toml   ← Python project marker
│   └── main.py
├── frontend/
│   ├── package.json     ← Node project marker
│   └── src/
└── shared/
    └── types/
```

**Mapping `./` detects:**
1. **Root project** (`my-app`)
2. **Sub-project** (`backend`) - has `pyproject.toml`
3. **Sub-project** (`frontend`) - has `package.json`
4. **Shared directory** (`shared`) - not a project, just files

### The Mapping Strategy

**Option 1: Hierarchical (default)**
```bash
ollama-prompt --project ./ --hierarchical
```

**Creates:**
- 1 root project (my-app)
- 2 sub-projects (backend, frontend)
- All linked via `parent_project_id`

**Context injection:**
```
PROJECT: my-app (monorepo)
├── backend/ (Python, 25 files)
├── frontend/ (React, 30 files)
└── shared/ (5 files)
```

**Option 2: Flat (treat each as independent)**
```bash
ollama-prompt --project ./ --flat
```

**Creates:**
- 1 root project (my-app) with all files flattened

**Context injection:**
```
PROJECT: my-app (60 files)
Entry: backend/main.py, frontend/src/index.tsx
Modules: backend/database/, frontend/components/, ...
```

### Which to Use?

| Scenario | Use | Why |
|----------|-----|-----|
| **Monorepo with distinct projects** | Hierarchical | Preserves boundaries, clearer navigation |
| **Single project with subdirs** | Flat | Simpler, no artificial boundaries |
| **Cross-project work** | Hierarchical | Agent understands relationships |

---

## Context Management with Multiple Projects

### How Context Manager Handles Multiple Projects

**The project summaries are treated as "pinned context":**

```python
class ContextManager:
    def __init__(self):
        self.pinned_content = []  # Never compress
        self.messages = []
        
    def add_project_summary(self, summary: str):
        """Add project summary as pinned content."""
        self.pinned_content.append({
            'type': 'project_map',
            'content': summary,
            'tokens': self._estimate_tokens(summary)
        })
    
    def _soft_compact(self):
        """Level 1: Compress files, but NEVER compress project maps."""
        # Project maps are pinned, always stay in context
        pass
```

**Why pinned?**
- Project maps are small (2-3KB each)
- They're essential for navigation
- Compressing them defeats the purpose

**What if you have 10 projects?**
- 10 projects × 2KB = 20KB
- That's too much for pinned content
- **Solution:** Only keep active projects in context

### Active vs. Inactive Projects

**Rule:** Only projects specified in `--project` are "active" for the current session.

**Example:**
```bash
# Session 1: Only backend is active
ollama-prompt --project ./backend --prompt "Fix the API"
# Context: backend map (2KB)

# Session 2: Both are active
ollama-prompt --project ./backend --project ./frontend \
  --prompt "Add feature across both"
# Context: backend map (2KB) + frontend map (2KB) = 4KB

# Session 3: Switch to frontend only
ollama-prompt --project ./frontend --prompt "Update UI"
# Context: frontend map (2KB)
```

**The `session_projects` table tracks this.**

---

## Cross-Project Dependencies

### Detecting Cross-Project References

**When scanning projects, detect imports/references across projects:**

**Example:**
```python
# frontend/services/api.ts
import { UserType } from '../../shared/types/user';

const API_URL = 'http://localhost:5000';  // ← References backend
```

**Project mapper detects:**
- `frontend` depends on `shared/types/user`
- `frontend` calls backend API (via URL pattern)

**Stores in `project_dependencies` table:**
```sql
INSERT INTO project_dependencies VALUES (
    1,
    'frontend-ghi789',
    'frontend/services/api.ts',
    'shared/types/user.ts',
    'import'
);

INSERT INTO project_dependencies VALUES (
    2,
    'frontend-ghi789',
    'frontend/services/api.ts',
    'backend:api',  -- Cross-project reference
    'api_call'
);
```

### Using Cross-Project Dependencies

**Agent can ask:**
```python
mapper.get_dependencies('frontend-ghi789')
# Returns:
# {
#   'internal': ['shared/types/user.ts'],
#   'cross_project': ['backend:api']
# }
```

**Agent reasoning:**
- "User wants to change frontend API calls"
- "Frontend depends on backend:api"
- "I should check backend API structure before changing frontend"

**Agent action:**
```bash
# Automatically loads backend project map
mapper.load_project('backend-def456')
```

---

## Updated CLI Interface

### New Flags

```bash
# Multiple projects
--project <path> [--project <path> ...]

# Hierarchical vs flat scanning
--hierarchical  # Detect sub-projects (default for monorepos)
--flat          # Treat as single project

# Auto-detect related projects
--auto-related  # Automatically load related projects when dependencies detected

# List projects
--list-projects

# Show project relationships
--show-project-tree <project_id>
```

### Examples

**Example 1: Monorepo with auto-detection**
```bash
ollama-prompt --project ./ --hierarchical --auto-related \
  --prompt "Add authentication to backend and update frontend"
```

**What happens:**
1. Scans `./` hierarchically
2. Detects backend and frontend sub-projects
3. Detects cross-project dependencies (frontend → backend)
4. Loads both projects into session
5. Injects combined map into context

**Example 2: Work on single sub-project**
```bash
ollama-prompt --project ./backend --prompt "Optimize database queries"
```

**What happens:**
1. Loads only backend project
2. Injects backend map (2KB)
3. Agent works in isolation

**Example 3: Explicitly specify multiple projects**
```bash
ollama-prompt --project ./backend --project ./shared \
  --prompt "Update shared types and backend models"
```

**What happens:**
1. Loads backend (primary) and shared (secondary)
2. Injects both maps (4KB total)
3. Agent can reference both: `@./models.py` (backend) and `@shared:./types.ts`

---

## Storage Implications

### How Much Space?

**Scenario: Large monorepo**
- Root project: 500 files
- 5 sub-projects: 100 files each
- Total: 1000 files

**Database storage:**
- `projects` table: 6 rows (1 root + 5 sub)
- `project_files` table: 1000 rows
- `project_dependencies` table: ~500 rows (estimated)

**Total:** ~2MB in SQLite (very manageable)

**Context usage:**
- If all 6 projects active: 6 × 2KB = 12KB
- Typically 1-2 projects active: 2-4KB

---

## Summary

### Yes, I Considered Multiple Projects

**But I didn't make it explicit. Here's the full design:**

| Scenario | How It's Handled |
|----------|-----------------|
| **Different levels** | Each path gets unique project_id, can be mapped independently |
| **Multiple projects** | `--project` flag accepts multiple values, all loaded into session |
| **Nested projects** | `parent_project_id` links sub-projects to root, hierarchical scanning |
| **Cross-project deps** | Detected during scan, stored in `project_dependencies` table |
| **Context management** | Project maps are "pinned" (never compressed), only active projects in context |

### The Key Additions

1. **`parent_project_id`** field in `projects` table
2. **`session_projects`** table to track active projects per session
3. **`--project` flag accepts multiple values**
4. **`--hierarchical` flag for monorepo scanning**
5. **Cross-project dependency detection**
6. **Project prefix syntax** for file references (`@frontend:./App.tsx`)

### Implementation Impact

**Original estimate:** 5-6 days for basic project mapping

**With multi-project support:** 7-8 days (adds ~2 days for relationship handling)

**Worth it?** Absolutely. This is the difference between "works on toy projects" and "works on real codebases."
