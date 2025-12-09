# Implementation Plans for Advanced Features

This directory contains comprehensive implementation plans for adding advanced context management and project mapping capabilities to `ollama-prompt`.

## Overview

These plans were developed to transform `ollama-prompt` from a CLI tool into a full coding agent with intelligent context management, project understanding, and semantic search capabilities.

## Documents

### Core Implementation Plans

1. **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)**
   - Master implementation plan covering all 4 phases
   - Timeline: 3-4 weeks with 1-2 developers
   - Phases: File Chunking, Database Upgrade, Context Management, Semantic Search

2. **[IMPLEMENTATION_PLAN_ADDENDUM.md](./IMPLEMENTATION_PLAN_ADDENDUM.md)**
   - Updated compaction thresholds based on Manus context engineering best practices
   - Lowers thresholds from 60/75/90 to 50/65/80 to prevent "context rot"

### Feature-Specific Designs

3. **[PROJECT_MAPPING_DESIGN.md](./PROJECT_MAPPING_DESIGN.md)**
   - Complete design for project mapping as a first-class feature
   - Database schema, CLI interface, and integration with context management
   - Should be implemented as Phase 0 (before the existing 4 phases)

4. **[PROJECT_MAPPING_MULTI_PROJECT.md](./PROJECT_MAPPING_MULTI_PROJECT.md)**
   - Addendum covering multi-project scenarios
   - Monorepo support, nested projects, cross-project dependencies
   - Hierarchical vs. flat scanning strategies

5. **[chunking_strategy.md](./chunking_strategy.md)**
   - Three-tier approach to file chunking
   - Tier 1: Smart Summarization (95% savings)
   - Tier 2: Targeted Extraction (80-95% savings)
   - Tier 3: Semantic Chunking with embeddings (98% savings)

6. **[context_compaction_strategy.md](./context_compaction_strategy.md)**
   - Four-level dynamic context compaction system
   - Automatic triggering based on usage thresholds
   - Graduated strategies from rule-based to LLM-based

7. **[database_upgrade_strategy.md](./database_upgrade_strategy.md)**
   - Schema upgrade from V1 (JSON blobs) to V2 (structured tables)
   - Six tables: sessions, messages, file_references, file_chunks, embeddings, compaction_history
   - Automatic migration with zero data loss

### Supporting Documents

8. **[decision_flow.md](./decision_flow.md)**
   - Visual decision flow for automatic context compaction
   - Shows how the system chooses between Level 1, 2, and 3 compaction

9. **[article_analysis.md](./article_analysis.md)**
   - Analysis of Manus team's context engineering article
   - Validation of our design decisions
   - Recommendation to lower compaction thresholds

10. **[context_manager_implementation.py](./context_manager_implementation.py)**
    - Complete working implementation of the automatic context manager
    - Production-ready code with all three compaction levels
    - Can be integrated directly into the codebase

## Implementation Order

### Recommended Sequence

**Phase 0: Project Mapping** (7-8 days)
- Implement project scanning and mapping
- Database schema for projects
- CLI integration with `--project` flag
- Multi-project support

**Phase 1: File Chunking** (4-5 days)
- Smart file summarization
- Targeted extraction syntax
- Integration with file operations

**Phase 2: Database Upgrade** (3-4 days, can run in parallel with Phase 1)
- Schema migration from V1 to V2
- Structured tables for messages, files, chunks
- Automatic migration for existing users

**Phase 3: Context Management** (5-6 days)
- Automatic compaction system
- Three-level graduated strategy
- Integration with session management

**Phase 4: Semantic Search** (4-5 days)
- Vector embeddings generation
- SQLite BLOB storage
- Cosine similarity search

**Total Timeline:** 4-5 weeks with 1 developer, 3-4 weeks with 2 developers

## Key Design Decisions

### 1. SQLite for Everything

**Decision:** Use SQLite for all storage (sessions, projects, embeddings)

**Rationale:**
- Zero configuration (built into Python)
- Single file portability
- Sufficient performance for local CLI tool
- No external dependencies

### 2. Graduated Compaction Strategy

**Decision:** Three levels of compaction (rule-based → vector-based → LLM-based)

**Rationale:**
- Start with cheap, fast methods (rules)
- Escalate to smarter methods only when needed
- Preserve information quality as long as possible

### 3. Project Mapping as First-Class Feature

**Decision:** Separate project mapping from context management

**Rationale:**
- Different concerns (structure vs. memory)
- Different lifetimes (per-project vs. per-session)
- Project maps feed into context management

### 4. Lower Compaction Thresholds

**Decision:** Start compacting at 50% instead of 60%

**Rationale:**
- Prevents "context rot" (degraded reasoning at high token counts)
- Maintains consistent quality throughout conversation
- Based on Manus team's production experience

## Success Metrics

### Technical Metrics

- Context window usage reduced by 60-90%
- Conversation length increased to 50-100+ messages
- Files per session increased to 10-20
- Emergency compaction rate < 5%

### User Experience Metrics

- Agent can navigate projects without repeated file reads
- Conversations maintain quality throughout
- No manual context management required
- Cross-session continuity (agent "remembers" projects)

## Testing Strategy

### Unit Tests

- File chunker (parsing, summarization)
- Context manager (compaction logic)
- Project mapper (scanning, dependencies)
- Database migrations

### Integration Tests

- End-to-end conversation with compaction
- Multi-project workflows
- Session persistence and restoration
- Cross-project dependency resolution

### Performance Tests

- Context compaction speed (< 1 second)
- Project scanning speed (< 5 seconds for 100 files)
- Vector search speed (< 200ms for 1000 embeddings)

## Deployment

### Backward Compatibility

All changes are backward compatible:
- Existing sessions migrate automatically
- Old CLI syntax continues to work
- New features are opt-in (via flags)

### Rollout Strategy

1. Deploy Phase 0 (project mapping) as standalone feature
2. Test with early adopters
3. Deploy Phase 1-2 together (chunking + database)
4. Deploy Phase 3 (context management)
5. Deploy Phase 4 (semantic search) as final enhancement

## Contributing

These plans are comprehensive but not set in stone. Feedback and improvements are welcome.

### How to Contribute

1. Review the relevant plan document
2. Open an issue with questions or suggestions
3. Submit PRs with improvements to the plans
4. Implement features following the plans

## Questions?

For questions about these plans, open an issue in the repository or contact the maintainer.

---

**Last Updated:** December 8, 2025  
**Status:** Ready for implementation  
**Estimated Effort:** 4-5 weeks (1 developer) or 3-4 weeks (2 developers)
