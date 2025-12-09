# Project Mapping as a First-Class Feature

**Date:** December 8, 2024  
**For:** ollama-prompt Development Team  
**Topic:** Should project mapping be part of context management or a separate feature?

---

## The Question

**You asked:** "A good coding agent will map out the entire project first when you start a deep dive or direct it to a project instead of just diving in with an agenda first. I'm not sure if that goes in current context a file or a data store. Should we consider this as part of our context management and should we also make this action a first class citizen?"

**Short answer:** **Yes, make it a first-class citizen. No, it's not part of context management - it's a separate feature that FEEDS INTO context management.**

---

## What You're Describing

### The Problem

When a coding agent (or human) starts working on a project, diving straight into code without understanding the structure leads to:

- **Context thrashing** - constantly asking "where is X?" or "how does Y relate to Z?"
- **Missed dependencies** - changing file A breaks file B because you didn't know they were connected
- **Inefficient navigation** - reading the same files multiple times because you forgot what's in them
- **Poor decision-making** - making architectural changes without understanding the full impact

### The Solution: Project Mapping

**Before doing ANY work, create a map of the project:**

1. **File structure** - what files exist, where they are
2. **Dependencies** - which files import/use which other files
3. **Entry points** - where does execution start (main.py, CLI, API endpoints)
4. **Key modules** - what are the core components (database, API, business logic)
5. **External dependencies** - what libraries/services does this use

**This map becomes the "working memory" for the entire session.**

---

## Is This Part of Context Management?

### No. Here's Why.

| Aspect | Context Management | Project Mapping |
|--------|-------------------|-----------------|
| **Purpose** | Manage token budget during conversation | Understand project structure before conversation |
| **When** | Continuous, reactive (during conversation) | One-time, proactive (before conversation) |
| **What** | Compress/summarize/prune existing context | Generate new structured knowledge |
| **Lifetime** | Per-session (changes as conversation evolves) | Per-project (persists across sessions) |
| **Storage** | Session database (messages table) | Project database (separate schema) |

**They're separate concerns:**

- **Context management** = "How do I fit this conversation into the token budget?"
- **Project mapping** = "What is this project and how does it work?"

---

## Where Does Project Mapping Fit?

### It's a First-Class Feature (Like Session Management)

**Current architecture:**

```
ollama-prompt
├── Session Management (first-class)
│   └── Tracks conversation history
├── File Operations (first-class)
│   └── Read/write/search files
└── Context Management (planned first-class)
    └── Compress/prune context
```

**Proposed architecture:**

```
ollama-prompt
├── Session Management (first-class)
│   └── Tracks conversation history
├── File Operations (first-class)
│   └── Read/write/search files
├── Context Management (planned first-class)
│   └── Compress/prune context
└── Project Mapping (NEW first-class)  ← ADD THIS
    └── Understand project structure
```

---

## How Project Mapping FEEDS INTO Context Management

### The Relationship

**Project mapping creates the knowledge that context management uses.**

**Example workflow:**

1. **User:** `ollama-prompt --project ./my-app --prompt "Add authentication"`

2. **Project Mapper runs FIRST:**
   - Scans `./my-app` directory
   - Identifies 50 files, 3 entry points, 5 core modules
   - Generates project map (2KB summary)
   - Stores in project database

3. **Project Map injected into context:**
   ```
   PROJECT: my-app
   Entry points: main.py, api.py, cli.py
   Core modules: auth (3 files), database (5 files), api (10 files)
   Dependencies: flask, sqlalchemy, bcrypt
   ```

4. **Conversation starts with map in context:**
   - User asks about authentication
   - Agent knows auth module exists (from map)
   - Agent reads only relevant files (auth/*.py)
   - Context manager compresses map if needed

**The map is INPUT to context management, not part of it.**

---

## Design: Project Mapping as First-Class Feature

### Database Schema

**New table: `projects`**

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    root_path TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_scanned_at TEXT NOT NULL,
    file_count INTEGER,
    total_size_kb INTEGER,
    entry_points TEXT,  -- JSON array
    languages TEXT      -- JSON array
);
```

**New table: `project_files`**

```sql
CREATE TABLE project_files (
    file_id INTEGER PRIMARY KEY,
    project_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,  -- 'python', 'javascript', 'markdown', etc.
    size_kb INTEGER,
    line_count INTEGER,
    last_modified TEXT,
    summary TEXT,  -- Generated summary (classes, functions, etc.)
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
```

**New table: `project_dependencies`**

```sql
CREATE TABLE project_dependencies (
    dependency_id INTEGER PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    target_file TEXT NOT NULL,
    dependency_type TEXT,  -- 'import', 'call', 'reference'
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
```

### CLI Interface

**New flag: `--project <path>`**

```bash
# Initialize project mapping
ollama-prompt --project ./my-app --prompt "What does this project do?"

# First time: scans project, generates map, stores in DB
# Subsequent times: loads map from DB (unless --rescan)

# Force rescan
ollama-prompt --project ./my-app --rescan --prompt "..."

# List mapped projects
ollama-prompt --list-projects
```

### New Module: `project_mapper.py`

```python
class ProjectMapper:
    """
    Map project structure and dependencies.
    """
    
    def scan_project(self, root_path: str) -> ProjectMap:
        """
        Scan project directory and generate map.
        
        Returns:
            ProjectMap with structure, dependencies, entry points
        """
        pass
    
    def get_project_summary(self, project_id: str) -> str:
        """
        Generate human-readable project summary for context injection.
        
        Returns:
            2-3KB summary of project structure
        """
        pass
    
    def find_entry_points(self, project_id: str) -> List[str]:
        """
        Identify main entry points (main.py, __init__.py, etc.)
        """
        pass
    
    def analyze_dependencies(self, project_id: str) -> Dict[str, List[str]]:
        """
        Build dependency graph (which files depend on which)
        """
        pass
```

---

## How This Works in Practice

### Scenario: User Starts Working on New Project

**Command:**
```bash
ollama-prompt --project ./my-app --prompt "Add user authentication"
```

**What happens:**

#### Step 1: Project Mapping (Automatic, First Time Only)

```
[Project Mapper] Scanning ./my-app...
[Project Mapper] Found 50 files (Python: 45, Config: 5)
[Project Mapper] Identified entry points: main.py, api.py
[Project Mapper] Analyzing dependencies...
[Project Mapper] Generated project map (2.1 KB)
[Project Mapper] Stored as project_id: my-app-abc123
```

#### Step 2: Inject Map into Context

```
PROJECT MAP: my-app
├── Entry Points
│   ├── main.py (CLI entry)
│   └── api.py (Flask API)
├── Core Modules
│   ├── database/ (5 files, SQLAlchemy ORM)
│   ├── api/ (10 files, Flask routes)
│   └── utils/ (8 files, helpers)
├── Dependencies
│   ├── External: flask, sqlalchemy, bcrypt, pytest
│   └── Internal: api → database, utils → database
└── Notes
    └── No existing auth module found
```

#### Step 3: Agent Uses Map to Work Efficiently

**Agent reasoning:**
- "User wants authentication"
- "Project map shows no auth module exists"
- "I need to create one"
- "It should integrate with database/ module (from dependency graph)"
- "I should add routes to api/ module"

**Agent actions:**
1. Read `database/models.py` to understand ORM structure
2. Create `auth/user.py` with User model
3. Create `auth/password.py` with hashing logic
4. Update `api/routes.py` to add `/login` and `/register` endpoints
5. Update project map with new auth module

**Context usage:**
- Project map: 2KB (stays in context the whole time)
- Only reads 3-4 relevant files (not all 50)
- Context manager compresses map if needed (Level 1)

---

## Integration with Existing Features

### How Project Mapping Integrates

| Feature | How It Uses Project Mapping |
|---------|----------------------------|
| **File Operations** | Uses map to suggest which files to read/write |
| **Directory Search** | Uses dependency graph to find related files |
| **Context Management** | Compresses map when context fills up |
| **Session Management** | Links sessions to projects for continuity |

### Example: Smart File Suggestions

**Without project mapping:**
```bash
User: "Where is the database connection code?"
Agent: "Let me search... @./src/:search:database"
# Searches all files, wastes tokens
```

**With project mapping:**
```bash
User: "Where is the database connection code?"
Agent: "Based on project map, it's in database/connection.py"
# Direct answer from map, no search needed
```

---

## Storage: Context vs. Database

### Your Question: "I'm not sure if that goes in current context a file or a data store"

**Answer: Both, but differently.**

### In Database (Persistent)

**What:** Full project map with all details

**Why:** Persists across sessions, doesn't consume tokens

**Schema:**
- `projects` table (metadata)
- `project_files` table (file details)
- `project_dependencies` table (dependency graph)

**Size:** Unlimited (not in context window)

### In Context (Temporary)

**What:** Compressed summary of project map

**Why:** Agent needs to "remember" project structure during conversation

**Format:**
```
PROJECT: my-app (50 files)
Entry: main.py, api.py
Modules: database/ (5), api/ (10), utils/ (8)
No auth module found
```

**Size:** 2-3KB (minimal context usage)

### The Flow

```
┌─────────────────────────────────────────────┐
│         Database (Persistent)               │
│  ┌──────────────────────────────────────┐   │
│  │ Full Project Map (unlimited size)    │   │
│  │ - 50 files with full details         │   │
│  │ - Complete dependency graph          │   │
│  │ - All metadata                       │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    ↓
           (compress to summary)
                    ↓
┌─────────────────────────────────────────────┐
│         Context Window (Temporary)          │
│  ┌──────────────────────────────────────┐   │
│  │ Project Summary (2-3KB)              │   │
│  │ - High-level structure               │   │
│  │ - Entry points                       │   │
│  │ - Key modules                        │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 0: Project Mapping (NEW)

**Add this BEFORE the existing 4 phases.**

**Duration:** 5-6 days  
**Priority:** High  
**Dependencies:** None  
**Deliverable:** Project mapping as first-class feature

### Tasks

#### Task 0.1: Database Schema

**File:** `ollama_prompt/session_db.py`

**Add tables:**
- `projects`
- `project_files`
- `project_dependencies`

**Acceptance Criteria:**
- [ ] Tables created with proper foreign keys
- [ ] Indexes on project_id and file_path
- [ ] Automatic migration for existing databases

#### Task 0.2: Project Mapper Module

**File:** `ollama_prompt/project_mapper.py`

**Implement:**
- `ProjectMapper` class
- `scan_project()` method
- `get_project_summary()` method
- `analyze_dependencies()` method

**Acceptance Criteria:**
- [ ] Can scan Python projects
- [ ] Identifies entry points
- [ ] Builds dependency graph
- [ ] Generates 2-3KB summary

#### Task 0.3: CLI Integration

**File:** `ollama_prompt/cli.py`

**Add flags:**
- `--project <path>`
- `--rescan`
- `--list-projects`

**Acceptance Criteria:**
- [ ] `--project` triggers automatic scan (first time)
- [ ] Subsequent calls load from DB
- [ ] `--rescan` forces re-scan
- [ ] Project summary injected into context

#### Task 0.4: Context Integration

**File:** `ollama_prompt/session_manager.py`

**Implement:**
- Load project summary when `--project` is used
- Inject summary into first message
- Link session to project_id

**Acceptance Criteria:**
- [ ] Project summary appears in context
- [ ] Summary is < 3KB
- [ ] Session tracks project_id

---

## Benefits

### Why This is Worth Building

| Benefit | Impact |
|---------|--------|
| **Faster navigation** | Agent knows where things are without searching |
| **Better decisions** | Understands dependencies before making changes |
| **Lower context usage** | 2KB summary vs. reading all files |
| **Cross-session continuity** | Map persists, agent "remembers" project |
| **Smarter suggestions** | Can recommend relevant files based on structure |

### Concrete Example

**Without project mapping:**
```
User: "Add caching to the API"
Agent: Reads 20 files to understand structure (15KB context)
Agent: Makes changes, misses a dependency
User: "It broke the database queries"
Agent: Reads 10 more files to debug (10KB more context)
Total: 25KB context, 2 rounds of debugging
```

**With project mapping:**
```
User: "Add caching to the API"
Agent: Checks project map (2KB in context)
Agent: Sees api/ depends on database/
Agent: Reads only api/routes.py and database/query.py (3KB)
Agent: Implements caching correctly
Total: 5KB context, 1 round, no debugging
```

**Savings: 80% less context, 50% faster**

---

## Summary

### The Answer to Your Question

**Should we make project mapping a first-class citizen?**

**Yes. Absolutely.**

**Should it be part of context management?**

**No. It's a separate feature that FEEDS INTO context management.**

**Where does it go?**

**Both:**
- **Database** - full project map (persistent, unlimited size)
- **Context** - compressed summary (temporary, 2-3KB)

### The Architecture

```
┌──────────────────────────────────────────────┐
│           ollama-prompt                      │
├──────────────────────────────────────────────┤
│  Phase 0: Project Mapping (NEW)              │
│  ├─ Scan project structure                   │
│  ├─ Build dependency graph                   │
│  ├─ Store in database                        │
│  └─ Inject summary into context              │
├──────────────────────────────────────────────┤
│  Phase 1: File Chunking                      │
│  Phase 2: Database Upgrade                   │
│  Phase 3: Context Management                 │
│  Phase 4: Semantic Search                    │
└──────────────────────────────────────────────┘
```

### Next Steps

1. **Add Phase 0 to implementation plan** (Project Mapping)
2. **Implement project_mapper.py module**
3. **Add database schema for projects**
4. **Integrate with CLI (--project flag)**
5. **Test with real projects**

**This is a game-changer for coding agent capabilities.**
