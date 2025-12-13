# Automatic Context Compaction Decision Flow

## How It Works in Practice

The system makes **automatic decisions** at every step. Here's the complete flow:

## Entry Point: Every Message

```
User/Assistant sends message
         ↓
   add_message() called
         ↓
   Message added to history
         ↓
   Token count updated
         ↓
   _auto_compact() triggered ← AUTOMATIC DECISION POINT
```

## Decision Tree

```
_auto_compact()
    ↓
Calculate usage = current_tokens / max_tokens
    ↓
    ├─ usage < 60% ──→ Level 0: Do nothing
    │                   └─ Return
    │
    ├─ usage 60-75% ──→ Level 1: Soft Compaction
    │                   └─ _soft_compact()
    │                       ↓
    │                   DECISION: Which files to compress?
    │                       ↓
    │                   RULE: Compress files not referenced in last 3 messages
    │                       ↓
    │                   Apply compression
    │                       ↓
    │                   Return tokens_freed
    │
    ├─ usage 75-90% ──→ Level 2: Hard Compaction
    │                   └─ _hard_compact()
    │                       ↓
    │                   DECISION: Which messages to keep?
    │                       ↓
    │                   Get current query (last user message)
    │                       ↓
    │                   Embed query with nomic-embed-text
    │                       ↓
    │                   Embed all old messages
    │                       ↓
    │                   Calculate cosine similarity for each
    │                       ↓
    │                   RULE: Keep top 50% by similarity score
    │                       ↓
    │                   RULE: Always keep last 5 messages
    │                       ↓
    │                   Remove low-scoring messages
    │                       ↓
    │                   Return tokens_freed
    │
    └─ usage > 90% ────→ Level 3: Emergency Compaction
                        └─ _emergency_compact()
                            ↓
                        STEP 1: Compress ALL files to summaries
                            ↓
                        STEP 2: Keep only last 4 messages (2 exchanges)
                            ↓
                        STEP 3: Summarize rest with LLM
                            ↓
                        Build summary prompt
                            ↓
                        Call ollama.generate() with llama3.2:3b
                            ↓
                        Replace old messages with summary
                            ↓
                        Return tokens_freed
```

## Concrete Example Walkthrough

### Scenario: User has a 20-message conversation

**Initial State:**
- Messages: 20
- Tokens: 8,000 / 16,000 (50%)
- Level: 0 (no compaction)

**Message 21 added:**
```python
cm.add_message('user', 'How does password hashing work?')
```

**Automatic Decision Flow:**

1. **Token count updated:** 8,000 → 10,000 (62.5%)

2. **_auto_compact() triggered automatically**

3. **_determine_compaction_level(0.625) called**
   ```python
   if 0.625 < 0.60:  # False
   elif 0.625 < 0.75:  # True
       return 1  # Soft compaction
   ```

4. **Level 1 selected: _soft_compact() called**

5. **Decision: Which files to compress?**
   ```python
   for file_path, info in file_references.items():
       if info['mode'] == 'full':
           messages_since = current_index - info['last_reference_index']
           if messages_since >= 3:  # Not used in last 3 messages
               compress_this_file()
   ```

6. **Result:**
   - Found: `user_manager.py` (referenced in message 5, now at message 21)
   - Messages since: 21 - 5 = 16 (> 3 threshold)
   - **DECISION: Compress this file**

7. **Compression applied:**
   - Before: 45KB (11,250 tokens)
   - After: 2KB (500 tokens)
   - **Tokens freed: 10,750**

8. **New state after compaction:**
   - File compressed: 11,250 → 500 tokens
   - Tokens freed: 10,750
   - New total: Below soft threshold

---

## Example 2: Hard Compaction with Relevance Scoring

**Initial State:**
- Messages: 20
- Tokens: 12,000 / 16,000 (75%)
- File in message 5: 5,000 tokens (full mode)
- Level: 0 (no compaction yet)

**Message 21 added:**
```python
cm.add_message('user', 'How does password hashing work?')  # 500 tokens
```

**Automatic Decision Flow:**

1. **Token count updated:** 12,000 → 12,500 (78%)

2. **_auto_compact() triggered**

3. **Level determined:** 78% → Level 2 (Hard Compaction)

4. **_hard_compact() called**

5. **Decision: Which messages to keep?**
   - Current query: "How does password hashing work?"
   - Embed query → vector
   - Embed all old messages (1-15) → vectors
   - Calculate similarity scores:
     ```
     Message 5 (about authentication): 0.85 (high similarity)
     Message 7 (about database): 0.45 (medium)
     Message 10 (about UI): 0.12 (low)
     ...
     ```

6. **Scoring results:**
   ```
   Message 5:  0.85 ← KEEP (top 50%)
   Message 7:  0.45 ← KEEP (top 50%)
   Message 12: 0.40 ← KEEP (top 50%)
   Message 3:  0.38 ← REMOVE (bottom 50%)
   Message 10: 0.12 ← REMOVE (bottom 50%)
   ...
   ```

7. **Compaction applied:**
   - Kept: 7 messages (top 50% by relevance)
   - Removed: 8 messages (bottom 50%)
   - Tokens freed: 3,500

8. **New state:**
   - Tokens: 12,500 - 3,500 = 9,000 (56%)
   - Back below soft threshold!

## Key Decision Points

### 1. When to Compact? (Automatic)

Thresholds per IMPLEMENTATION_PLAN_ADDENDUM.md:

```python
usage = current_tokens / max_tokens

if usage >= 0.80:
    level = 3  # Emergency
elif usage >= 0.65:
    level = 2  # Hard
elif usage >= 0.50:
    level = 1  # Soft
else:
    level = 0  # No compaction
```

### 2. Which Strategy to Use? (Automatic based on level)

**Level 1: Rule-Based**
```python
# DECISION: Compress files not used recently
for file in files:
    if messages_since_last_use(file) >= 3:
        compress(file)
```

**Level 2: Vector-Based**
```python
# DECISION: Keep most relevant messages
query_vector = embed(current_query)
for message in old_messages:
    message_vector = embed(message)
    score = cosine_similarity(query_vector, message_vector)

keep = top_50_percent(scored_messages)
```

**Level 3: LLM-Based**
```python
# DECISION: Let LLM decide what's important
summary = llm.summarize(
    messages,
    instructions="Keep: user goals, technical details, code refs"
)
```

### 3. What to Keep? (Automatic based on strategy)

| Level | What to Keep | How Decided |
|-------|--------------|-------------|
| **1** | Recent files | Rule: Last 3 messages |
| **2** | Relevant messages | Vector: Top 50% similarity |
| **3** | Critical info | LLM: Summarization prompt |

## No User Intervention Needed

The user just calls:
```python
cm.add_message('user', 'Some question')
```

Everything else happens automatically:
- ✅ Token counting
- ✅ Threshold checking
- ✅ Level selection
- ✅ Strategy application
- ✅ Compaction execution

## Cooldown Protection

To prevent thrashing (repeated compaction), the system has a cooldown:

```python
if messages_since_last_compaction < 2:
    # Don't compact yet, wait for more messages
    return
```

This prevents:
```
Message 20: 61% → Compact → 55%
Message 21: 60% → Compact → 54%  ← BAD (thrashing)
Message 22: 59% → Compact → 53%  ← BAD (thrashing)
```

Instead:
```
Message 20: 61% → Compact → 55%
Message 21: 60% → Skip (cooldown)
Message 22: 65% → Skip (cooldown)
Message 23: 70% → Compact → 60%  ← GOOD
```

## Summary: The System Decides Everything

| Question | Answer | How |
|----------|--------|-----|
| **When to compact?** | Automatically after each message | Check usage % against thresholds |
| **Which level to use?** | Based on usage % | 60-75% = L1, 75-90% = L2, >90% = L3 |
| **What to compress?** | Depends on level | L1: rules, L2: vectors, L3: LLM |
| **How much to remove?** | Depends on level | L1: stale files, L2: 50%, L3: aggressive |
| **When to stop?** | When usage drops below threshold | Automatic |

**The user never has to think about any of this.** It just works.
