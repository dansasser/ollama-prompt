# Implementation Plan Addendum: Updated Compaction Thresholds

**Date:** December 8, 2025  
**Reason:** Based on Manus team's context engineering best practices  
**Source:** https://www.philschmid.de/context-engineering-part-2

---

## What Changed

### Compaction Thresholds Lowered

**Previous thresholds:**
```python
SOFT_THRESHOLD = 0.60      # 60% full
HARD_THRESHOLD = 0.75      # 75% full
EMERGENCY_THRESHOLD = 0.90 # 90% full
```

**New thresholds:**
```python
SOFT_THRESHOLD = 0.50      # 50% full
HARD_THRESHOLD = 0.65      # 65% full
EMERGENCY_THRESHOLD = 0.80 # 80% full
```

---

## Why This Change

### Context Rot Prevention

The Manus team (who built the AI agent system this is based on) shared their learnings about "context rot" - the degradation of reasoning quality that occurs when context windows get too full.

**Key insight:** Don't wait until you're at 75% or 90% to compact. Start earlier to maintain reasoning quality throughout the conversation.

### The Problem with High Thresholds

When you wait until 75% or 90% full to compact:
- Model reasoning quality has already degraded
- KV cache is nearly full, causing slowdowns
- Emergency compaction is more lossy (you're forced to summarize more aggressively)

### The Benefit of Lower Thresholds

Starting compaction at 50% instead of 60%:
- Maintains consistent reasoning quality
- Gives more headroom for complex operations
- Allows gentler, more reversible compaction
- Prevents emergency situations

---

## Impact on User Experience

### Before (Old Thresholds)

| Usage | Level | Action |
|-------|-------|--------|
| 0-60% | 0 | No compaction |
| 60-75% | 1 | Soft (file compression) |
| 75-90% | 2 | Hard (message pruning) |
| 90%+ | 3 | Emergency (LLM summarization) |

**Problem:** User experiences degraded quality from 75-90% before hard compaction kicks in.

### After (New Thresholds)

| Usage | Level | Action |
|-------|-------|--------|
| 0-50% | 0 | No compaction |
| 50-65% | 1 | Soft (file compression) |
| 65-80% | 2 | Hard (message pruning) |
| 80%+ | 3 | Emergency (LLM summarization) |

**Benefit:** User maintains high reasoning quality throughout. Emergency compaction is rare.

---

## Concrete Example

### Scenario: 16K Token Context Window

#### Old Thresholds
- **0-9.6K tokens:** No action
- **9.6-12K tokens:** Compress files
- **12-14.4K tokens:** Prune messages (quality degrading)
- **14.4K+ tokens:** Emergency summarization (quality poor)

**Problem:** User spends 2.4K tokens (12-14.4K) in degraded quality zone.

#### New Thresholds
- **0-8K tokens:** No action
- **8-10.4K tokens:** Compress files
- **10.4-12.8K tokens:** Prune messages (quality still good)
- **12.8K+ tokens:** Emergency summarization (rarely reached)

**Benefit:** User maintains quality until 12.8K. More headroom. Emergency is rare.

---

## Implementation Notes

### No Architecture Changes

This is a **parameter tuning change**, not an architecture change. The graduated compaction strategy remains the same:

1. Level 1: Rule-based file compression (reversible)
2. Level 2: Vector-based message pruning (selective)
3. Level 3: LLM summarization (lossy)

**Only the trigger points changed.**

### Backward Compatibility

No impact on existing code or sessions. This is a configuration change that improves behavior.

### Testing Adjustments

Update test assertions to expect compaction at the new thresholds:

```python
# Old test
assert compaction_level == 0 when usage < 0.60

# New test
assert compaction_level == 0 when usage < 0.50
```

---

## References

- **Article:** [Context Engineering for AI Agents: Part 2](https://www.philschmid.de/context-engineering-part-2)
- **Key Quote:** "If a model has a 1M context window, performance often degrades around < 256k. Don't wait for the API to throw an error. Monitor your token count and implement Compaction or Summarization cycle before you hit the 'rot' zone to maintain reasoning quality."
- **Principle:** Prefer raw > Compaction > Summarization, but start compacting earlier than you think you need to.

---

## Action Items for Development Team

1. **Update `context_manager.py`** with new threshold values (lines 466-468 in implementation plan)
2. **Update test assertions** to expect compaction at new thresholds
3. **Update documentation** to reflect new behavior
4. **No other code changes required** - this is a configuration update

---

## Summary

**What:** Lowered compaction thresholds from 60/75/90 to 50/65/80  
**Why:** Prevent context rot and maintain reasoning quality  
**Impact:** Better user experience, rare emergency compaction, consistent quality  
**Effort:** Minimal - just update threshold constants
