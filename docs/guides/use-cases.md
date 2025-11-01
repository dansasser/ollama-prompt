# ollama-prompt Use Cases

**Purpose:** Practical examples showing how to use ollama-prompt for real-world software development tasks.

**Key Features:**
- Session management for multi-turn conversations
- File reference system with @file syntax
- Token-efficient analysis with CAL method
- Subprocess integration patterns

**Command Structure:**

All examples follow this pattern:
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Your prompt here"
```

**Output Directory:**

All outputs saved to `./ollama-output/` directory:
```bash
mkdir -p ./ollama-output
```

---

## Understanding Sessions

### How Sessions Work

**First Call (creates session):**
```bash
ollama-prompt --prompt "Your first question"
# Output includes: "session_id": "f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n"
```

**Continue Session (use the UUID from output):**
```bash
ollama-prompt --session-id f8e3c2a1-4b5d-6e7f-8g9h-0i1j2k3l4m5n \
              --prompt "Follow-up question"
```

**Key Points:**
- Sessions auto-create on first call (no flag needed)
- Session IDs are UUIDs (auto-generated, cannot be customized)
- Use `--session-id <uuid>` to continue existing session
- Use `--list-sessions` to see all session UUIDs
- Use `--session-info <uuid>` to see session details

**In examples below:** `<session-id>` represents the UUID you received from the first call.

---

## Use Case 1: Code Review Automation

### Scenario

You need to review a pull request with multiple changed files, checking for:
- Code quality issues
- Security vulnerabilities
- Best practices violations
- Performance concerns

### Single File Review

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Review @./src/auth.py for security issues, code quality, and best practices. Provide specific line numbers for issues found." \
              > ./ollama-output/review-auth.json
```

### Multi-File Review with Session

**Initial Review (creates session):**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Review @./src/auth.py focusing on authentication logic and security."
# Save the session_id from output
```

**Follow-up Review (maintains context):**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Now review @./src/api.py. Check if it properly uses the auth module we just reviewed."
```

**Final Summary:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Summarize all issues found across both files and prioritize by severity."
```

### Benefits

- Session maintains context across multiple files
- Consistent review standards applied
- Cross-file integration checking
- Comprehensive final summary

---

## Use Case 2: Documentation Generation

### Scenario

Generate comprehensive documentation from source code including API docs, usage examples, and README content.

### API Documentation

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --prompt "Generate comprehensive API documentation for @./src/api.py. Include: function signatures, parameters, return types, examples, and error handling." \
              > ./ollama-output/api-docs.json
```

### README Generation

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Generate a README.md for this project. Analyze @./setup.py and @./src/__init__.py to understand the project structure and dependencies."
```

### Tutorial Creation with Session

**Step 1: Outline**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Create an outline for a beginner's tutorial on using the authentication system in @./src/auth.py."
```

**Step 2: Write Tutorial**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 8000 \
              --session-id <session-id> \
              --prompt "Based on the outline we created, write the complete tutorial with code examples."
```

### Benefits

- Consistent documentation style
- Accurate technical details from source
- Progressive tutorial building with sessions

---

## Use Case 3: Refactoring Analysis

### Scenario

Analyze legacy code and provide refactoring recommendations with modernization strategies.

### Legacy Code Analysis

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --prompt "Analyze @./legacy/old_api.py. Identify: deprecated patterns, code smells, modernization opportunities, and breaking change risks." \
              > ./ollama-output/refactor-analysis.json
```

### Iterative Refactoring with Session

**Analysis Phase:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Analyze @./legacy/old_api.py and break down refactoring into phases."
```

**Design Phase:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Design the modernized version maintaining backward compatibility."
```

**Implementation Phase:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --session-id <session-id> \
              --prompt "Generate the refactored code based on our design."
```

### Benefits

- Phased refactoring approach
- Context preserved across analysis-design-implementation
- Risk assessment included

---

## Use Case 4: Bug Investigation

### Scenario

Investigate complex bugs requiring analysis of error logs, stack traces, and multiple code files.

### Error Log Analysis

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze this error log and identify root cause:

[ERROR] 2025-11-01 10:23:45 - Exception in handler
Traceback (most recent call last):
  File 'api.py', line 45, in handle_request
    result = process_data(data)
  File 'processor.py', line 123, in process_data
    return validate(data['user_id'])
KeyError: 'user_id'

Also check @./src/api.py and @./src/processor.py for the issue." \
              > ./ollama-output/bug-analysis.json
```

### Multi-Turn Debugging Session

**Initial Investigation:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Analyze this KeyError in @./src/processor.py line 123. What's the root cause?"
```

**Deeper Analysis:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Check @./src/api.py line 45. Is data validation missing before calling process_data?"
```

**Solution Development:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Generate a fix with proper error handling and validation."
```

### Benefits

- Session maintains investigation history
- Multi-file context for complex bugs
- Progressive hypothesis testing

---

## Use Case 5: Architecture Analysis

### Scenario

Understand codebase architecture, identify patterns, and analyze dependencies.

### Parallel Analysis (CAL Method)

**Setup:**
```bash
mkdir -p ./ollama-output
```

**Launch 4 Concurrent Analyses:**
```bash
# CLI Layer Analysis
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze CLI structure in @./src/cli.py. Identify: argument parsing, command flow, integration points." \
              > ./ollama-output/arch-cli.json &

# API Layer Analysis
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze API layer in @./src/api.py. Identify: endpoints, middleware, error handling." \
              > ./ollama-output/arch-api.json &

# Database Layer Analysis
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze database layer in @./src/db.py. Identify: models, queries, connections." \
              > ./ollama-output/arch-db.json &

# Business Logic Analysis
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze business logic in @./src/core.py. Identify: domain models, workflows." \
              > ./ollama-output/arch-core.json &

# Wait for all to complete
wait
echo "All analyses complete"
```

**Synthesis (after parallel batch):**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 12000 \
              --prompt "Synthesize findings from @./ollama-output/arch-cli.json, @./ollama-output/arch-api.json, @./ollama-output/arch-db.json, and @./ollama-output/arch-core.json. Create unified architecture overview with layer interactions and dependency graph." \
              > ./ollama-output/arch-synthesis.json
```

### Benefits

- Parallel processing (4 analyses in ~60 seconds)
- Comprehensive multi-layer understanding
- CAL method prevents token exhaustion

---

## Use Case 6: Test Generation

### Scenario

Generate comprehensive test suites including unit tests, integration tests, and edge cases.

### Unit Test Generation

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --prompt "Generate pytest unit tests for @./src/utils.py. Include: happy path, edge cases, error conditions, mocking examples." \
              > ./ollama-output/tests-utils.json
```

### Test Coverage Analysis with Session

**Coverage Check:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Analyze @./src/auth.py and @./tests/test_auth.py. Identify untested code paths."
```

**Generate Missing Tests:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --session-id <session-id> \
              --prompt "Generate tests for the untested paths we identified."
```

### Benefits

- Comprehensive test coverage
- Edge case identification
- Session maintains coverage analysis context

---

## Use Case 7: Security Audit

### Scenario

Audit codebase for security vulnerabilities, OWASP compliance, and best practices.

### Security Scan

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.3 \
              --max_tokens 8000 \
              --prompt "Security audit of @./src/auth.py. Check for: SQL injection, XSS, CSRF, insecure crypto, hardcoded secrets, OWASP Top 10 violations. Provide severity ratings." \
              > ./ollama-output/security-audit.json
```

### Multi-File Security Review

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.3 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Audit @./src/api.py for input validation and sanitization issues."
```

### Benefits

- Systematic security analysis
- OWASP compliance checking
- Prioritized vulnerability reporting

---

## Use Case 8: Performance Optimization

### Scenario

Identify performance bottlenecks and suggest optimizations.

### Performance Analysis

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze @./src/processor.py for performance issues. Identify: inefficient algorithms, unnecessary loops, memory leaks, database query issues." \
              > ./ollama-output/perf-analysis.json
```

### Optimization Session

**Bottleneck Identification:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Analyze @./src/data_pipeline.py and identify the top 3 performance bottlenecks."
```

**Optimization Design:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Design optimizations for the bottlenecks we identified."
```

### Benefits

- Data-driven optimization priorities
- Algorithm improvement suggestions
- Session maintains optimization context

---

## Use Case 9: Migration Planning

### Scenario

Plan framework migrations, identify breaking changes, and create migration roadmap.

### Migration Analysis

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --prompt "Analyze @./src/ for Flask-to-FastAPI migration. Identify: breaking changes, deprecated patterns, required refactoring, migration complexity." \
              > ./ollama-output/migration-analysis.json
```

### Phased Migration with Session

**Assessment:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Analyze @./src/app.py for Flask dependencies and patterns."
```

**Planning:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 8000 \
              --session-id <session-id> \
              --prompt "Create phased migration plan with backward compatibility strategy."
```

### Benefits

- Risk assessment included
- Phased approach reduces breaking changes
- Backward compatibility strategies

---

## Use Case 10: API Design Review

### Scenario

Review API design for REST principles, consistency, and best practices.

### API Review

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Review API design in @./src/api.py. Check: REST principles, HTTP methods, status codes, error responses, naming consistency, versioning." \
              > ./ollama-output/api-review.json
```

### Benefits

- REST compliance checking
- Consistency analysis
- Best practices validation

---

## Use Case 11: Dependency Analysis

### Scenario

Audit project dependencies for security, licensing, and version compatibility.

### Dependency Audit

**Command:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze @./requirements.txt and @./setup.py. Check for: outdated packages, security vulnerabilities, license conflicts, version compatibility issues." \
              > ./ollama-output/dep-audit.json
```

### Benefits

- Security vulnerability detection
- License compliance checking
- Update recommendations

---

## Use Case 12: Learning & Tutorial Generation

### Scenario

Learn new technology or generate educational content with session-based Q&A.

### Progressive Learning Session

**Initial Question:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Explain Rust ownership and borrowing with simple examples."
```

**Follow-up:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "I didn't understand the borrowing example. Can you explain with a different analogy?"
```

**Practice:**
```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.5 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Give me a practice exercise for ownership and borrowing based on what we've discussed."
```

### Benefits

- Personalized learning pace
- Context-aware explanations
- Progressive skill building

---

## Quick Reference

### Standard Command Template

```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Your prompt here"
```

### With Session

```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --session-id <session-id> \
              --prompt "Your prompt here"
```

### With File References

```bash
ollama-prompt --model deepseek-v3.1:671b-cloud \
              --temperature 0.4 \
              --max_tokens 6000 \
              --prompt "Analyze @./file1.py and @./file2.py"
```

### Output to File

```bash
ollama-prompt --prompt "..." > ./ollama-output/result.json
```

### Parallel Execution (max 4)

```bash
mkdir -p ./ollama-output
ollama-prompt --prompt "..." > ./ollama-output/analysis1.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis2.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis3.json &
ollama-prompt --prompt "..." > ./ollama-output/analysis4.json &
wait
```

### Session Management

```bash
# List sessions
ollama-prompt --list-sessions

# Session info
ollama-prompt --session-info <session-id>

# Purge old sessions
ollama-prompt --purge 7  # Remove sessions older than 7 days
```

---

## Best Practices

### Command Structure

1. **Always specify model explicitly** - Don't rely on defaults
2. **Use consistent temperature** - 0.4 for analysis, 0.2 for code, 0.5-0.6 for creative
3. **Set appropriate max_tokens** - 6000 for analysis, 8000+ for comprehensive tasks
4. **Use descriptive session IDs** - `code-review-pr-123` not `session1`

### File Organization

1. **Always use ./ollama-output/ directory** - Keep outputs organized
2. **Use .json extension** - Even though response is markdown, file format is JSON
3. **Sequential numbering** - analysis01.json, analysis02.json, etc.
4. **Add to .gitignore** - Don't commit temporary analysis files

### Session Management

1. **One session per project/task** - Maintain separate contexts
2. **Use sessions for multi-turn workflows** - Code review, debugging, learning
3. **Regular cleanup** - Use --purge to remove old sessions
4. **Descriptive names** - Help identify session purpose later

### CAL Method

1. **Parallel for independent analyses** - Max 4 concurrent processes
2. **Sequential for dependent tasks** - Use @file references to chain
3. **Synthesis after parallel** - Combine findings with @file references
4. **Token efficiency** - Use @file syntax to avoid copying content to Claude

### Performance

1. **Limit parallel processes to 4** - Prevents resource exhaustion
2. **Use appropriate token limits** - Don't over-allocate
3. **Monitor session growth** - Long sessions consume more memory
4. **Cleanup regularly** - Remove old ollama-output files

### Error Handling

1. **Check exit codes** - Verify subprocess succeeded
2. **Validate JSON output** - Use jq to verify format
3. **Test commands before automation** - Ensure they work as expected
4. **Have rollback strategy** - Keep backups before refactoring
