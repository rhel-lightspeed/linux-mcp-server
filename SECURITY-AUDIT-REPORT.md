# Security Audit Report: linux-mcp-server

| Field | Value |
|-------|-------|
| **Date** | 2026-04-21 |
| **Tool** | skill-audit v0.1.0 |
| **Detected type** | mcp-server (python) |
| **Files scanned** | 161 |
| **Current score** | FAIL (62%) |
| **Estimated after fixes** | PASS (~90%) |

---

## Summary of Findings

| ID | Severity | Category | Title | Status |
|----|----------|----------|-------|--------|
| SEC-001 | Critical | Secrets | 257 false positives from package-lock.json | Blocks PASS |
| LIC-002 | Critical | Licensing | 96 source files missing SPDX headers | Blocks PASS |
| PRI-001 | Critical | Privacy | Real email in test file | Review needed |
| CTR-007 | Critical | Container | ENV sets sensitive-looking value in Containerfile | Review needed |
| CTR-003 | Recommended | Container | No .containerignore file | Improves score |
| LIC-005 | Recommended | Licensing | No copyright notices in source files | Improves score |
| DEP-002 | Recommended | Dependencies | 3 dependencies without upper bounds | See note |
| SBX-001 | Recommended | Sandbox | 5 test files write to absolute paths | Low risk |

---

## Critical Findings (blocks PASS -- must fix)

### SEC-001 -- 257 false positives from package-lock.json

All 257 "secrets" findings are SHA-512 integrity hashes in `mcp-app/package-lock.json`. These are npm package integrity checksums, not secrets. Example:

```
"integrity": "sha512-abc123..."
```

**Why this matters:** The scanner flags any string matching cryptographic hash patterns. With 257 hits, this single file dominates the score and pushes the overall result to FAIL.

**Action needed:**
- **Option A:** Add `mcp-app/package-lock.json` to `.gitignore`. The lock file is not currently ignored (checked `.gitignore`). Since the container build runs `npm install` from `package.json`, the lock file is regenerated at build time. Removing it from the repo would also reduce noise in diffs.
- **Option B:** No action from your side -- we have already excluded lock files from scanning on our end. However, Option A is still worth considering for general repo hygiene.

---

### LIC-002 -- 96 source files missing SPDX license headers

The repo is licensed Apache-2.0 but 96 `.py` and `.sh` files are missing SPDX headers. This is a gated category in the audit -- a FAIL here means an automatic overall FAIL regardless of other scores.

**Action needed:** Add the following line to the top of every `.py` and `.sh` file (after the shebang line, if present):

```python
# SPDX-License-Identifier: Apache-2.0
```

**Find all files that need updating:**

```bash
find . -name "*.py" -o -name "*.sh" | xargs grep -L SPDX
```

**Batch fix (one-liner for .py files without shebangs):**

```bash
find . -name "*.py" -exec grep -L SPDX {} \; | while read f; do
  sed -i '1i# SPDX-License-Identifier: Apache-2.0' "$f"
done
```

For files with shebangs (`#!/usr/bin/env python3`), insert the SPDX line on line 2 instead of line 1.

---

### PRI-001 -- Real email in test file

- **File:** `tests/connection/ssh/test_timeout.py`, line 111
- **Value:** `testuser@myhost.example.com`

The domain `example.com` is an IANA-reserved domain (RFC 2606), so this is likely acceptable. However, the scanner flags it because it matches the `user@host` email pattern.

**Action needed:** Confirm this is intentional. If so, no change is required -- we can add a suppression comment for future scans.

---

### CTR-007 -- ENV sets sensitive-looking value in Containerfile

- **File:** `Containerfile`, line 67
- **Value:** `ENV LINUX_MCP_SEARCH_FOR_SSH_KEY=True`

The scanner flagged this because the variable name contains `SSH_KEY`, which matches patterns for sensitive configuration. On inspection, this is a boolean flag that controls whether the application searches for SSH keys at runtime -- it does not contain a key or secret itself.

**Action needed:** This is a false positive given the actual value is just `True`. Two options:
1. **No change** -- we can add this to our suppression list.
2. **Consider renaming** to something less ambiguous, e.g., `LINUX_MCP_ENABLE_SSH_KEY_DISCOVERY=True`, to avoid triggering security scanners. This is optional.

---

## Recommended Findings (improves score, not blocking)

### CTR-003 -- No .containerignore file

The repo has no `.containerignore` file. Without one, `podman build` / `docker build` may copy unnecessary or sensitive files into the build context.

**Action needed:** Create `.containerignore` with:

```
.env
.env.*
.git
*.token
__pycache__
*.pyc
.pytest_cache
coverage/
.venv/
.vscode/
.idea/
*.egg-info/
```

---

### LIC-005 -- No copyright notices in source files

Source files have no copyright headers. While SPDX identifiers (LIC-002) are the blocker, adding copyright notices is best practice for Apache-2.0 licensed projects.

**Action needed:** Add below the SPDX header in each source file:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Red Hat, Inc.
```

Adjust the year and entity as appropriate for your project.

---

### DEP-002 -- 3 dependencies without upper bounds

Three dependencies in `pyproject.toml` use `>=` without an upper bound:

| Dependency | Current spec |
|-----------|-------------|
| `litellm` | `>=1.80.16` |
| `pydantic-settings` | `>= 2.12.0` |
| `pydantic` | `>= 2.12.5` |

**Note:** We see the comment in `pyproject.toml` explaining this is intentional due to your Renovate `in-range-only` strategy -- unbounded ranges ensure Renovate notifies you about all new versions, including major bumps with security fixes. This is a valid tradeoff.

**Action needed:** None required if the Renovate strategy is working as intended. The scanner flags this as a general best practice but your documented rationale is sound. For the audit, we can suppress this finding with a note.

---

### SBX-001 -- 5 test files write to absolute paths

Several test files reference absolute paths under `/var/log/`:

| File | Paths referenced |
|------|-----------------|
| `tests/test_config.py` | `/var/log/custom`, `/var/log/test`, `/var/log/my-app/2024` |
| `tests/utils/test_validation.py` | `/var/log/messages`, `/var/log/../../etc/hosts` |
| `tests/tools/test_logs.py` | `/var/log/test.log`, `/var/log/remote.log` |

These are in test files and appear to be used for config validation and path traversal checks (the `../../etc/hosts` path is a security test, which is good). Risk is low.

**Action needed:** Consider using `tmp_path` pytest fixtures or `/tmp` paths where possible. For path validation tests (like the traversal check), the current approach is fine.

---

## Clean Categories (no findings)

| Category | Grade | Notes |
|----------|-------|-------|
| Authentication patterns | A | No hardcoded credentials or auth bypasses |
| Network boundaries | A | Proper network access controls |
| Output safety | A | No injection or escape issues |

---

## How to Run the Audit Yourself

```bash
git clone git@gitlab.cee.redhat.com:afarley/ai-tool-security-check.git
cd ai-tool-security-check
python3 bin/skill-audit --fix-hints /path/to/linux-mcp-server/
```

The `--fix-hints` flag provides actionable fix suggestions for each finding.

---

## Score Breakdown

| Category | Current | After fixes |
|----------|---------|-------------|
| Secrets | F (257 false positives) | A (exclude lock files) |
| Licensing (SPDX) | F (96 files) | A (add headers) |
| Licensing (copyright) | C | A (add notices) |
| Privacy | B | A (confirm example.com) |
| Container | C | A (add .containerignore, review ENV) |
| Dependencies | B | B (intentional, suppressed) |
| Sandbox | B | B (test-only, low risk) |
| Auth patterns | A | A |
| Network | A | A |
| Output safety | A | A |
| **Overall** | **FAIL (62%)** | **PASS (~90%)** |

**The two highest-impact fixes are:**
1. Exclude `package-lock.json` from the repo or scanning (removes 257 false positives)
2. Add SPDX headers to all 96 source files (unblocks the licensing gate)

These two changes alone should move the score from FAIL to PASS.
