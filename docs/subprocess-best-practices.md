# ollama-prompt Subprocess Best Practices

**Purpose:** Standardized patterns for using ollama-prompt as a subprocess in multi-agent analysis workflows.

**Last Updated:** 2025-10-26

---

## Directory Structure

### Always Use Dedicated Output Directory

```bash
# Create output directory for subprocess results
mkdir -p ./ollama-output
```

**Why:**
- Prevents directory bloat in working directory
- Makes cleanup easy (delete entire folder)
- Clear separation between analysis outputs and project files
- Easier to .gitignore if needed

**Directory Name:** `ollama-output` (standardized across all projects)

---

## File Naming Convention

### Use JSON Extension

```bash
# CORRECT - Use .json extension
ollama-prompt --prompt "..." > ./ollama-output/analysis01.json

# WRONG - Don't use .md extension
ollama-prompt --prompt "..." > analysis.md
```

**Why .json:**
- ollama-prompt outputs JSON format:
  ```json
  {
    "model": "deepseek-v3.1:671b-cloud",
    "response": "Actual markdown content here...",
    "done": true,
    "eval_count": 1234
  }
  ```
- Even though `response` field contains markdown, the file format is JSON
- Allows programmatic parsing of metadata (model, token counts, etc.)

### Sequential Numbering

```bash
./ollama-output/analysis01.json
./ollama-output/analysis02.json
./ollama-output/analysis03.json
./ollama-output/synthesis.json
```

**Pattern:**
- `analysis##.json` - Individual analyses
- `synthesis.json` - Final synthesis combining all analyses

---

## Standard Command Template

### Basic Subprocess Call

```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analysis prompt text here" \
              > ./ollama-output/analysis01.json
```

**Required Parameters:**
- `--model` - Explicit model specification (don't rely on defaults)
- `--temperature` - Control randomness (0.4 recommended for analysis)
- `--max-tokens` - Limit response length
- `--prompt` - Analysis instructions

**Output Redirection:**
- Always use `> ./ollama-output/filename.json`
- Captures full JSON response
- Preserves metadata (token counts, timing, etc.)

---

## CAL Method: File Reference Chaining

### Pattern for Iterative Multi-Batch Analysis

**Batch 1: Initial Analysis**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analyze the CLI structure in @./repos/project/cli.py.
                        Focus on argument parsing and integration points." \
              > ./ollama-output/analysis01.json
```

**Batch 2: Building on Previous Results**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --file-reference ./ollama-output/analysis01.json \
              --prompt "Building on findings in @./ollama-output/analysis01.json,
                        now analyze the API integration in @./repos/project/api.py.
                        How do CLI and API layers connect?" \
              > ./ollama-output/analysis02.json
```

**Batch 3: Synthesis Across Multiple Analyses**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 8000 \
              --file-reference ./ollama-output/analysis01.json \
              --file-reference ./ollama-output/analysis02.json \
              --prompt "Considering findings in @./ollama-output/analysis01.json
                        and @./ollama-output/analysis02.json, create a unified
                        implementation plan that integrates both CLI and API layers." \
              > ./ollama-output/synthesis.json
```

### Key CAL Method Principles

**Token Economy:**
- Claude reads: Executive summaries from subprocess outputs (2-5K tokens)
- Subprocess reads: Full file contents via @file references (0 Claude tokens)
- Result: Linear Claude context growth instead of exponential

**File Reference Syntax:**
```bash
--file-reference ./path/to/file      # Single file
--file-reference ./file1 \           # Multiple files
--file-reference ./file2
```

**Chaining Pattern:**
```
analysis01.json
    ↓
analysis02.json (references analysis01.json)
    ↓
analysis03.json (references analysis01.json + analysis02.json)
    ↓
synthesis.json (references all previous analyses)
```

---

## Parallel Subprocess Execution

### Launching Multiple Analyses Concurrently

```bash
# Create output directory
mkdir -p ./ollama-output

# Launch 4 concurrent analyses
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analyze CLI structure..." \
              > ./ollama-output/cli-analysis.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \

              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analyze API integration..." \
              > ./ollama-output/api-analysis.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Design database schema..." \
              > ./ollama-output/database-design.json &

ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Create implementation roadmap..." \
              > ./ollama-output/roadmap.json &

# Wait for all to complete
wait

echo "All analyses complete. Results in ./ollama-output/"
```

**Execution Time:**
- Single batch: ~60-90 seconds (regardless of parallel count)
- Processes run independently on separate Ollama instances

**When to Use Parallel:**
- Independent analysis domains (CLI, API, database, etc.)
- No dependencies between analyses
- Maximum of 4 concurrent processes

---

## Reading Subprocess Results

### Extract Response Content (Bash)

```bash
# Read just the response field from JSON
cat ./ollama-output/analysis01.json | jq -r '.response'

# Read with metadata
cat ./ollama-output/analysis01.json | jq '{model, eval_count, response}'
```

### Reading from Claude's Context

When Claude needs to read subprocess output:
```python
# Read the JSON file
with open('./ollama-output/analysis01.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    response_content = data['response']

# response_content contains the markdown analysis
```

---

## Complete Example: 4-Batch CAL Analysis

### Scenario: Analyze session memory implementation for ollama-prompt

**Setup:**
```bash
mkdir -p ./ollama-output
```

**Batch 1: CLI Structure**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analyze @./repos/ollama-prompt/cli.py for current argument
                        parsing structure. Identify where new session management flags
                        should be added. Provide line numbers and integration points." \
              > ./ollama-output/analysis01-cli.json &
```

**Batch 2: API Integration**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analyze @./repos/ollama-prompt/cli.py focusing on the
                        ollama.generate() API call. How does context flow? Where should
                        session context be injected and updated?" \
              > ./ollama-output/analysis02-api.json &
```

**Batch 3: Database Design**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 8000 \
              --prompt "Design a complete SQLite database schema for session persistence.
                        Include: table structure, indexes, cross-platform path handling,
                        and SessionManager class implementation." \
              > ./ollama-output/analysis03-database.json &
```

**Batch 4: Implementation Roadmap**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 8000 \
              --prompt "Create a phased implementation roadmap for adding session memory.
                        Break into phases with tasks, files to modify, success criteria,
                        and timeline estimates." \
              > ./ollama-output/analysis04-roadmap.json &
```

**Wait for completion:**
```bash
wait
echo "All 4 analyses complete in ./ollama-output/"
```

**Synthesis (Sequential, after parallel batch):**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 12000 \
              --file-reference ./ollama-output/analysis01-cli.json \
              --file-reference ./ollama-output/analysis02-api.json \
              --file-reference ./ollama-output/analysis03-database.json \
              --file-reference ./ollama-output/analysis04-roadmap.json \
              --prompt "Based on analyses in @./ollama-output/analysis01-cli.json,
                        @./ollama-output/analysis02-api.json,
                        @./ollama-output/analysis03-database.json, and
                        @./ollama-output/analysis04-roadmap.json, create a comprehensive
                        unified implementation plan with: architecture overview, database
                        design with code, CLI integration points, API handling, complete
                        implementation roadmap, risk assessment, and testing strategy." \
              > ./ollama-output/comprehensive-plan.json
```

---

## Cleanup and Maintenance

### Remove Old Analyses

```bash
# Remove entire output directory
rm -rf ./ollama-output

# Remove specific analysis
rm ./ollama-output/analysis01.json
```

### Archive for Future Reference

```bash
# Archive analyses before cleanup
tar -czf ollama-output-archive-2025-10-26.tar.gz ./ollama-output/

# Remove originals
rm -rf ./ollama-output
```

---

## .gitignore Recommendation

Add to `.gitignore`:
```
# Subprocess analysis outputs
ollama-output/
```

**Why:**
- Analyses are temporary working files
- Can be regenerated from source code
- Reduce repository size
- Keep git history clean

**Exception:**
- If analyses are valuable documentation, archive them separately
- Don't commit raw subprocess outputs to main project

---

## Error Handling

### Check for Subprocess Completion

```bash
# Launch with error checking
if ollama-prompt --prompt "..." > ./ollama-output/analysis.json; then
    echo "Analysis completed successfully"
else
    echo "ERROR: Subprocess failed"
    exit 1
fi
```

### Verify Output File Created

```bash
# Check file exists and is non-empty
if [ -s ./ollama-output/analysis.json ]; then
    echo "Output file created successfully"
else
    echo "ERROR: Output file missing or empty"
fi
```

### Validate JSON Format

```bash
# Verify valid JSON
if jq empty ./ollama-output/analysis.json 2>/dev/null; then
    echo "Valid JSON output"
else
    echo "ERROR: Invalid JSON format"
fi
```

---

## Performance Considerations

### Token Limits

**Standard Analysis:**
- `--max-tokens 6000` - Sufficient for most analyses
- Produces ~1500-2000 words of analysis

**Comprehensive/Synthesis:**
- `--max-tokens 8000-12000` - For synthesis across multiple analyses
- Allows detailed integration of findings

### Temperature Settings

**Analysis Tasks:**
- `--temperature 0.4` - Balanced (recommended)
- Provides consistent, focused analysis
- Some creativity without randomness

**Code Generation:**
- `--temperature 0.2` - More deterministic
- Better for precise code examples

**Creative Tasks:**
- `--temperature 0.6-0.8` - More variation
- Better for brainstorming, alternatives

---

## Quick Reference

### Standard Single Analysis
```bash
mkdir -p ./ollama-output
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --prompt "Analysis prompt" \
              > ./ollama-output/analysis01.json
```

### CAL Method File Chaining
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max-tokens 6000 \
              --file-reference ./ollama-output/analysis01.json \
              --prompt "Building on @./ollama-output/analysis01.json..." \
              > ./ollama-output/analysis02.json
```

### Parallel Execution (4 max)
```bash
mkdir -p ./ollama-output
ollama-prompt --prompt "..." > ./ollama-output/analysis01.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis02.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis03.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis04.json &
wait
```

---

## Summary

**Key Principles:**
1. ✅ Always use `./ollama-output/` directory
2. ✅ Always use `.json` extension
3. ✅ Always specify model, temperature, max-tokens explicitly
4. ✅ Use sequential numbering for analyses
5. ✅ Use file references for CAL method chaining
6. ✅ Maximum 4 concurrent processes
7. ✅ Add ollama-output/ to .gitignore

**Benefits:**
- Clean, organized working directory
- Token-efficient multi-batch analysis
- Reproducible subprocess executions
- Clear audit trail of analyses
- Easy cleanup and maintenance

**When to Use:**
- Code analysis requiring multiple perspectives
- Large codebase exploration
- Architecture planning with domain separation
- Iterative refinement across multiple rounds
- Any task where Claude's context limits would be exceeded by direct reading
