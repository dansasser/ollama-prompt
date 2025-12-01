# TODO: ollama-prompt Security Fixes

**Project Directory:** C:\Claude\repos\ollama-prompt-claude-security-fixes
**Date Created:** 2024-12-01
**Last Updated:** 2024-12-01

---

## Current Context

Working on security hardening for ollama-prompt. Phase 1 (PR #7 validation) is complete. Phase 2 (file reading security) is pending.

---

## Phase 1: PR #7 Validation - COMPLETE

- [x] Run full pytest suite (45/45 pass)
- [x] Review cli.py security changes
- [x] Review session_db.py security changes
- [x] Review session_manager.py security changes
- [x] Test model validation edge cases
- [x] Test SQL injection prevention
- [x] Test path traversal prevention
- [x] Test resource limits
- [x] Compare against main branch
- [x] Document issues (PR7-REVIEW-NOTES.md)
- [x] Fix Windows regex regression in cli.py
- [x] Fix Unicode console errors in test_security_fixes.py
- [x] Commit fixes to local branch (21dcc0a)
- [x] Push branch to dansasser/ollama-prompt
- [x] Comment on PR #7 with required fixes

**Branch:** ollama-prompt-claude-security-fixes
**Pushed to:** dansasser/ollama-prompt

---

## Phase 2: File Reading Security - PENDING

From gap analysis: `C:\Claude\repos\llm-filesystem-tools\docs\ollama-prompt-security-gap-analysis.md`

### Vulnerabilities to Fix

| Attack Vector | Severity | Current Status |
|--------------|----------|----------------|
| TOCTOU race condition | MEDIUM | NOT PROTECTED |
| Hardlinks | MEDIUM | NOT PROTECTED |
| Device files | MEDIUM | NOT PROTECTED |
| FIFOs/named pipes | MEDIUM | NOT PROTECTED |
| No audit trail | LOW | NOT PROTECTED |

Note: Direct symlink attacks ARE blocked by current commonpath check.

### Tasks

- [ ] **TOCTOU protection** - Open file first, validate on FD not path
- [ ] **Symlink blocking** - O_NOFOLLOW (Unix) / FILE_FLAG_OPEN_REPARSE_POINT (Windows)
- [ ] **File type validation** - Reject device files, FIFOs, sockets via fstat
- [ ] **Hardlink detection** (optional) - Check inode/nlink count
- [ ] **Audit logging** - Log all file access attempts with results
- [ ] **Attack scenario tests** - TOCTOU, symlinks, device files
- [ ] **Integration decision** - llm-fs-tools vs direct implementation

### Integration Options

**Option A: Integrate llm-fs-tools**
```python
from llm_fs_tools import read_file_secure
```

**Option B: Vendor security module**
Copy core security code into ollama_prompt package.

**Option C: Optional dependency**
```python
try:
    from llm_fs_tools import read_file_secure
    USE_SECURE_READ = True
except ImportError:
    USE_SECURE_READ = False
```

---

## Success Criteria

From gap analysis:

- [ ] Symlinks blocked at open time (O_NOFOLLOW or equivalent)
- [ ] TOCTOU window eliminated (FD-based validation)
- [ ] Device files, FIFOs, sockets rejected
- [ ] Hardlink detection (optional)
- [ ] Return format compatible with existing code
- [ ] Cross-platform (Windows + Linux + macOS)
- [ ] No breaking changes to CLI interface
- [ ] Tests for attack scenarios

---

## Related Files

- **Gap Analysis:** `C:\Claude\repos\llm-filesystem-tools\docs\ollama-prompt-security-gap-analysis.md`
- **Plan Updates:** `C:\Claude\repos\llm-filesystem-tools\docs\implementation-plan-v5-updates.md`
- **Review Notes:** `C:\Claude\repos\ollama-prompt-claude-security-fixes\PR7-REVIEW-NOTES.md`
- **llm-fs-tools:** `C:\Claude\repos\llm-filesystem-tools`
