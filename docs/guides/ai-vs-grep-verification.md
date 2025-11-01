# Use Case: AI Analysis vs Grep Verification

**Category:** Development Best Practices
**Scenario:** Auditing documentation for technical accuracy
**Tools:** ollama-prompt + grep/deterministic verification
**Lesson:** Combine AI understanding with deterministic validation

---

## Problem Statement

You need to audit documentation files for flag/command errors. The documentation spans 1,195 lines across 5 files with multiple instances of potential flag typos.

**Challenge:**
- Manual review is tedious and error-prone
- Need to find ALL instances of specific errors
- Want to understand context of errors
- Must be confident in completeness

---

## Approach 1: AI Analysis Only ❌

### What Was Done

```bash
# Create audit prompt with all files referenced
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.2 \
              --max_tokens 12000 \
              --no-session \
              --prompt "Audit these files for flag errors:
@./docs/subprocess-best-practices.md
@./docs/guides/use-cases.md
@./docs/sessions/quickstart.md
@./docs/integrations/claude-code.md
@./docs/README.md

Find all incorrect flags and report:
- File name
- Location
- Incorrect flag
- Correct flag
- Context" > ollama-output/flag-audit.json
```

### AI Analysis Results

**Reported Findings:**
- Total errors: 28
- `--session` → `--session-id`: 23 instances
- `--max-tokens` → `--max_tokens`: 1 instance
- `--keep-alive` (invalid): 3 instances
- `--no-stream` (invalid): 1 instance

**Time:** ~60 seconds
**Confidence:** High (AI seemed thorough)

---

## Approach 2: Grep Verification ✅

### What Was Done

```bash
# Count --session errors
grep -rn "\-\-session " docs/ | wc -l
# Result: 53

# Count --max-tokens errors
grep -rn "\-\-max-tokens" docs/ | wc -l
# Result: 3

# Count --keep-alive errors
grep -rn "\-\-keep-alive" docs/ | wc -l
# Result: 9

# Count --no-stream errors
grep -rn "\-\-no-stream" docs/ | wc -l
# Result: 2
```

### Grep Results

**Actual Findings:**
- Total errors: **67**
- `--session` → `--session-id`: **53** instances
- `--max-tokens` → `--max_tokens`: **3** instances
- `--keep-alive` (invalid): **9** instances
- `--no-stream` (invalid): **2** instances

**Time:** ~5 seconds
**Confidence:** 100% (deterministic)

---

## The Gap

| Error Type | AI Found | Grep Found | Missed | Miss Rate |
|------------|----------|------------|--------|-----------|
| `--session` | 23 | 53 | 30 | 57% |
| `--max-tokens` | 1 | 3 | 2 | 67% |
| `--keep-alive` | 3 | 9 | 6 | 67% |
| `--no-stream` | 1 | 2 | 1 | 50% |
| **TOTAL** | **28** | **67** | **39** | **58%** |

**AI missed 39 out of 67 errors (58% miss rate)**

---

## Why AI Missed Errors

### Root Causes Identified

1. **Token Limits**
   - 5 files = ~9,000 tokens input
   - AI may have truncated analysis
   - Later sections got less attention

2. **Pattern Fatigue**
   - After finding many instances of same error
   - AI may summarize instead of enumerate
   - "Multiple instances" != actual count

3. **Context Window Management**
   - AI prioritized understanding over counting
   - Focused on unique error types
   - Didn't exhaustively track every instance

4. **Probabilistic Nature**
   - AI generates probable completions
   - Not designed for exhaustive enumeration
   - Better at "find types" than "count instances"

---

## Best Practice: Hybrid Approach ✅

### Step 1: AI for Understanding

Use AI to:
- Identify ERROR TYPES
- Understand context
- Explain WHY something is wrong
- Suggest how to fix

```bash
ollama-prompt --prompt "What flag errors might exist in @file.md?" \
              > understanding.json
```

**AI Output:**
```json
{
  "response": "Found these error patterns:
  1. --session should be --session-id (for continuing sessions)
  2. --max-tokens should be --max_tokens (underscore not hyphen)
  3. --keep-alive is not a valid ollama-prompt flag
  ..."
}
```

### Step 2: Grep for Exhaustive Count

Use grep to:
- Count EXACT instances
- Get line numbers
- Verify completeness
- Generate fix list

```bash
# For each pattern AI identified, grep to count
grep -rn "\-\-session " docs/ > session-errors.txt
grep -rn "\-\-max-tokens" docs/ > max-tokens-errors.txt
grep -rn "\-\-keep-alive" docs/ > keep-alive-errors.txt
```

**Grep Output:**
```
docs/subprocess-best-practices.md:41:ollama run --session my-chat
docs/subprocess-best-practices.md:44:ollama run --session my-chat
docs/subprocess-best-practices.md:50:ollama run --session chat1
...
(53 total lines)
```

### Step 3: Combine Results

**AI provides:**
- ✅ Understanding of error types
- ✅ Context of why errors matter
- ✅ Suggested corrections

**Grep provides:**
- ✅ Exhaustive instance count
- ✅ Exact locations
- ✅ Complete fix list

---

## Implementation Example

### Complete Audit Workflow

```bash
#!/bin/bash
# hybrid-audit.sh - Combine AI and grep for complete audit

echo "=== Phase 1: AI Analysis ==="
ollama-prompt --prompt "Audit @./docs/*.md for flag errors" \
              > ai-analysis.json

echo "AI found these error types:"
cat ai-analysis.json | jq -r '.response' | grep "Error type"

echo ""
echo "=== Phase 2: Grep Verification ==="

# Extract patterns from AI analysis
PATTERNS=(
    "\-\-session "
    "\-\-max-tokens"
    "\-\-keep-alive"
    "\-\-no-stream"
)

# Count each pattern
for pattern in "${PATTERNS[@]}"; do
    count=$(grep -r "$pattern" docs/ | wc -l)
    echo "Pattern '$pattern': $count instances"
    grep -rn "$pattern" docs/ > "errors-${pattern//\-/}.txt"
done

echo ""
echo "=== Phase 3: Generate Fix Plan ==="
echo "AI understanding + Grep counts = Complete fix plan"
```

**Output:**
```
=== Phase 1: AI Analysis ===
AI found these error types:
Error type: --session should be --session-id
Error type: --max-tokens should be --max_tokens
Error type: --keep-alive is invalid

=== Phase 2: Grep Verification ===
Pattern '--session ': 53 instances
Pattern '--max-tokens': 3 instances
Pattern '--keep-alive': 9 instances
Pattern '--no-stream': 2 instances

=== Phase 3: Generate Fix Plan ===
AI understanding + Grep counts = Complete fix plan
```

---

## When to Use Each Approach

### Use AI When:
- ✅ Understanding new error types
- ✅ Explaining context and impact
- ✅ Suggesting solutions
- ✅ Identifying patterns you didn't know existed
- ✅ First-pass analysis on large codebases

### Use Grep When:
- ✅ Counting exact instances
- ✅ Finding every occurrence
- ✅ Generating fix lists
- ✅ Verifying AI claims
- ✅ Final validation before fixes

### Use Both When:
- ✅ Auditing documentation
- ✅ Code reviews for specific patterns
- ✅ Migration tasks (old API → new API)
- ✅ Security audits (finding all instances of vulnerability)
- ✅ Style guide enforcement

---

## Lessons Learned

### Critical Insights

1. **AI excels at understanding, not enumeration**
   - AI identifies "what" and "why"
   - Grep finds "where" and "how many"

2. **Never trust AI counts without verification**
   - AI may say "multiple instances" = actually 53
   - Always verify with deterministic tools

3. **Token limits affect thoroughness**
   - Large files → AI may skip sections
   - Grep processes everything

4. **Combine strengths for best results**
   - AI for intelligence
   - Grep for exhaustiveness
   - Together = complete solution

### Best Practices

```bash
# DON'T: Trust AI count
ollama-prompt --prompt "How many times does X appear in @files?"
# AI might say "several" or miss instances

# DO: Use AI for patterns, grep for count
ollama-prompt --prompt "What patterns of X might be errors?"
grep -r "pattern" files/ | wc -l

# DON'T: Use grep without understanding
grep -r "API" codebase/
# 10,000 results - which ones matter?

# DO: Use AI to prioritize, grep to execute
ollama-prompt --prompt "What API patterns are deprecated?"
# AI says: "old_api() is deprecated"
grep -r "old_api()" codebase/
# Now you have meaningful results
```

---

## Real-World Impact

### In This Project

**Without Grep Verification:**
- Would have fixed 28 errors
- Left 39 errors unfixed
- Documentation would still be incorrect
- User commands would fail

**With Grep Verification:**
- Found all 67 errors
- Complete fix list generated
- Confidence in completeness
- Documentation will be accurate

### Time Investment

| Approach | Time | Accuracy | Completeness |
|----------|------|----------|--------------|
| AI Only | 60s | 42% | Incomplete |
| Grep Only | 5s | 100% | Complete but no context |
| AI + Grep | 65s | 100% | Complete with understanding |

**Extra 5 seconds = 58% improvement in accuracy**

---

## Workflow Template

### For Future Documentation Audits

```bash
# 1. AI Analysis (understanding)
ollama-prompt --prompt "Analyze @docs/*.md for these error types:
- Flag typos
- Invalid flags
- Deprecated syntax
List error TYPES you find." > analysis.json

# 2. Review AI findings
cat analysis.json | jq -r '.response'

# 3. Grep verification (counting)
# For each error type AI found:
grep -rn "pattern" docs/ | wc -l
grep -rn "pattern" docs/ > detailed-errors.txt

# 4. Compare results
echo "AI found: X error types"
echo "Grep found: Y total instances"

# 5. Generate fix plan
# Use AI understanding + grep locations
```

---

## Summary

**Key Takeaway:** Combine AI analysis with deterministic verification for complete, accurate results.

**The Formula:**
```
AI Analysis (understanding) + Grep Verification (counting) = Complete Solution
```

**Verification Command:**
```bash
# After ANY AI audit, always verify:
grep -r "pattern-ai-found" target-files/ | wc -l
```

**Remember:**
- AI is smart but not exhaustive
- Grep is exhaustive but not smart
- Together they're unstoppable

---

## Related Use Cases

- Use Case #1: Complex Feature Implementation (benefits from AI understanding)
- Use Case #2: Iterative Code Debugging (needs grep verification)
- Use Case #7: Troubleshooting System Issues (combine both for log analysis)

---

**Last Updated:** 2025-11-01
**Validated With:** Real-world documentation audit (67 errors found)
**Tools Required:** ollama-prompt, grep, jq (optional)
