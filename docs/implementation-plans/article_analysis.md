# Article Analysis: Does This Change Our Design?

## Article: Context Engineering for AI Agents: Part 2
**Source:** https://www.philschmid.de/context-engineering-part-2
**Author:** Philipp Schmid (based on Manus team's learnings)

---

## Key Principles from Article

### 1. Context Compaction vs Summarization Hierarchy

**Article says:**
- **Prefer:** Raw > Compaction > Summarization
- **Context Compaction (Reversible):** Strip redundant info that exists in environment (e.g., file paths instead of full content)
- **Summarization (Lossy):** Use LLM to summarize, triggered at threshold (e.g., 128k tokens)
- **Keep recent turns raw** to preserve model's "rhythm" and formatting style

**Our design:**
- ✅ **We already have this:** Level 1 (soft compaction) = recompress files to summaries
- ✅ **We already have this:** Level 2 (hard compaction) = remove low-relevance messages
- ✅ **We already have this:** Level 3 (emergency) = LLM summarization
- ✅ **We already preserve recent messages** in all levels

**Verdict:** ✅ **No change needed.** Our graduated compaction strategy aligns perfectly.

---

### 2. Share Context by Communicating, Not Communicate by Sharing Context

**Article says:**
- Multi-agent systems fail due to "context pollution"
- Don't share full context unless absolutely necessary
- Discrete tasks = fresh sub-agent with minimal context
- Complex reasoning = share full history only when needed
- "Share memory by communicating, don't communicate by sharing memory" (GoLang principle)

**Our design:**
- ⚠️ **We're building a single-agent system** (ollama-prompt), not multi-agent
- ✅ **But this is relevant:** When ollama-prompt is called as a subprocess by Claude/Gemini, it IS a sub-agent
- ✅ **We already do this:** ollama-prompt gets discrete instructions, not Claude's full context

**Verdict:** ✅ **No change needed.** Our architecture already follows this (ollama-prompt as discrete subprocess).

---

### 3. Keep the Model's Toolset Small

**Article says:**
- 100+ tools = context confusion and hallucinations
- Use hierarchical action space:
  - Level 1: ~20 core tools (stable, cache-friendly)
  - Level 2: Use bash/CLI for utilities instead of specific tools
  - Level 3: Provide libraries/functions for complex logic chains

**Our design:**
- ✅ **We already do this:** llm-fs-tools provides a small, focused API
- ✅ **We use CLI utilities:** Directory operations (list, tree, search) are simple, not 100 different tools
- ✅ **We're not exposing 100 tools** to the model

**Verdict:** ✅ **No change needed.** We're already following this principle.

---

### 4. Treat "Agent as Tool" with Structured Schemas

**Article says:**
- Don't over-anthropomorphize agents
- Don't need "Org Chart" of agents (Manager, Designer, Coder)
- Treat agents as tools with structured input/output
- Use "MapReduce" pattern: main agent calls sub-agent, gets structured result

**Our design:**
- ✅ **This is exactly what ollama-prompt is:** A tool that Claude/Gemini calls
- ✅ **We return structured JSON:** Token counts, timing, session IDs
- ✅ **We're not building an org chart** of agents

**Verdict:** ✅ **No change needed.** This validates our subprocess architecture.

---

### 5. Best Practices

**Article says:**

#### Don't use RAG to manage tool definitions
- Fetching tool definitions dynamically breaks KV cache
- Creates shifting context that confuses the model

**Our design:**
- ✅ **We don't do this:** Our tools are static (llm-fs-tools API)
- ✅ **No dynamic tool fetching**

**Verdict:** ✅ **No change needed.**

---

#### Don't train your own models (yet)
- Models improve too fast
- Fine-tuning locks you into local optimum
- Use context engineering as flexible interface

**Our design:**
- ✅ **We're not training models:** We use Ollama's models
- ✅ **We're building context engineering:** Exactly what the article recommends

**Verdict:** ✅ **No change needed.** This validates our approach.

---

#### Define a "Pre-Rot Threshold"
- Don't wait for context window to fill completely
- Monitor token count and compact BEFORE hitting "rot zone"
- Example: If model has 1M context, compact at 256k

**Our design:**
- ✅ **We already have this:** Our thresholds are 60%, 75%, 90%
- ⚠️ **But:** Article suggests compacting earlier to maintain reasoning quality

**Verdict:** ⚠️ **CONSIDER ADJUSTMENT:** Should we lower our thresholds?

**Current:**
- Soft: 60% (9.6k / 16k)
- Hard: 75% (12k / 16k)
- Emergency: 90% (14.4k / 16k)

**Article suggests:**
- Start compacting earlier (maybe 50% or even 40%?)
- Don't wait until you're at 75% to do hard compaction

**Recommendation:** 
- **Lower Soft threshold to 50%** (8k / 16k)
- **Lower Hard threshold to 65%** (10.4k / 16k)
- **Lower Emergency threshold to 80%** (12.8k / 16k)

This gives more headroom and prevents "context rot" degradation.

---

#### Use "Agent-as-a-Tool" for Planning
- Don't keep a todo.md file in context (wastes tokens)
- Use a Planner sub-agent that returns structured Plan object
- Inject plan into context only when needed

**Our design:**
- ✅ **We don't have a persistent todo.md**
- ✅ **We're not wasting tokens on planning artifacts**

**Verdict:** ✅ **No change needed.**

---

#### Security & Manual Confirmation
- Sandbox isolation isn't enough
- Use human-in-the-loop for sensitive operations

**Our design:**
- ✅ **We have security:** llm-fs-tools provides TOCTOU protection, path validation
- ⚠️ **We don't have:** Human-in-the-loop confirmation

**Verdict:** ⚠️ **CONSIDER ADDING:** Optional confirmation mode for sensitive operations

**Recommendation:**
- Add `--require-confirmation` flag for file writes
- Add `--read-only` mode that blocks all writes
- Add audit logging (we already have this in llm-fs-tools)

---

## Summary: Does This Change Our Design?

### ✅ **Validated Decisions (No Changes Needed)**

1. **Graduated compaction strategy** (raw > compaction > summarization) ✅
2. **Subprocess architecture** (ollama-prompt as discrete tool) ✅
3. **Small, focused toolset** (llm-fs-tools API) ✅
4. **Structured output** (JSON with metadata) ✅
5. **No model training** (use context engineering) ✅
6. **No dynamic tool fetching** (static API) ✅

### ⚠️ **Recommended Adjustments**

#### 1. **Lower Compaction Thresholds** (Medium Priority)

**Why:** Article suggests compacting earlier to prevent "context rot" degradation

**Change:**
```python
# Current
SOFT_THRESHOLD = 0.60
HARD_THRESHOLD = 0.75
EMERGENCY_THRESHOLD = 0.90

# Recommended
SOFT_THRESHOLD = 0.50  # Start earlier
HARD_THRESHOLD = 0.65  # More aggressive
EMERGENCY_THRESHOLD = 0.80  # Leave more headroom
```

**Impact:** Better reasoning quality, less degradation at high token counts

---

#### 2. **Add Security Confirmation Modes** (Low Priority)

**Why:** Article recommends human-in-the-loop for sensitive operations

**Change:**
```python
# Add flags
--require-confirmation  # Prompt before file writes
--read-only            # Block all writes
--audit-log <path>     # Log all file operations
```

**Impact:** Better security for production use

---

## Final Verdict

**Does this article change our design?**

**90% No, 10% Yes.**

**What we got right:**
- Our graduated compaction strategy is exactly what Manus (the article's source) recommends
- Our subprocess architecture aligns with "agent as tool" principle
- Our small, focused toolset avoids "context confusion"
- Our structured output enables clean integration

**What we should adjust:**
1. **Lower compaction thresholds** (50%, 65%, 80% instead of 60%, 75%, 90%)
2. **Consider adding confirmation modes** for security-sensitive deployments

**Overall:** This article **validates** our design decisions. The only changes are **tuning parameters** (thresholds) and **optional features** (confirmation modes), not fundamental architecture changes.
