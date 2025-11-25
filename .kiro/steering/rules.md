# SpecSync Steering Rules

This document defines the validation behavior and conventions for the SpecSync system. These rules guide how Kiro validates commits for spec-code-test-doc alignment.

## File Correlation Patterns

These patterns define how different artifact types relate to each other in the codebase.

### Code → Spec Mapping

- `backend/handlers/*.py` → `.kiro/specs/app.yaml` (endpoints section)
- `backend/models.py` → `.kiro/specs/app.yaml` (models section)
- `backend/*.py` → `.kiro/specs/app.yaml`

### Code → Test Mapping

- `backend/handlers/{module}.py` → `tests/unit/test_{module}.py`
- `backend/{module}.py` → `tests/unit/test_{module}.py`
- Any `backend/**/*.py` → `tests/unit/test_*.py` or `tests/integration/test_*.py`

### Code → Documentation Mapping

- `backend/handlers/*.py` (with public endpoints) → `docs/api/*.md`
- `backend/main.py` → `docs/architecture.md`
- Public API changes → `docs/index.md` (may need updates)

### Spec → Documentation Mapping

- `.kiro/specs/app.yaml` (endpoints) → `docs/api/*.md`
- `.kiro/specs/app.yaml` (models) → `docs/api/*.md` (schema sections)

## Minimal Change Policy

When suggesting fixes for drift, follow these principles:

1. **Suggest only necessary modifications** - Don't propose changes that aren't directly related to the detected drift
2. **Preserve existing structure** - Maintain the current organization of specs, tests, and docs unless restructuring is essential
3. **Incremental fixes** - Suggest the smallest change that resolves the alignment issue
4. **No over-engineering** - Don't suggest adding features or abstractions beyond what's needed for alignment

### Examples

**Good Suggestion:**
- Drift: New endpoint `/users/{id}` added to code but not in spec
- Suggestion: Add the `/users/{id}` endpoint definition to `.kiro/specs/app.yaml`

**Bad Suggestion:**
- Drift: New endpoint `/users/{id}` added to code but not in spec
- Suggestion: Restructure the entire spec file, add comprehensive validation schemas, create separate spec files per module, and implement API versioning

## Validation Priorities

When multiple types of drift are detected, prioritize them in this order:

1. **Spec Alignment** (Highest Priority)
   - Code must match spec definitions
   - New functionality must be specified
   - Removed functionality must be removed from specs

2. **Test Coverage** (Medium Priority)
   - All code changes must have corresponding tests
   - Tests must cover new functionality
   - Tests must be removed for deleted functionality

3. **Documentation** (Lower Priority)
   - Public APIs must be documented
   - Documentation must reflect current behavior
   - Internal implementation details don't require docs

### Rationale

Specs define the contract and expected behavior, so spec alignment is critical. Tests verify correctness, making them second priority. Documentation helps users but doesn't affect system correctness, so it's third priority.

## False Positive Handling

Ignore the following when detecting drift:

### Generated Files
- `**/__pycache__/**`
- `**/node_modules/**`
- `**/.venv/**`
- `**/dist/**`
- `**/*.pyc`
- `**/*.pyo`
- `**/*.egg-info/**`

### Vendor Code
- `**/vendor/**`
- `**/third_party/**`

### Configuration Files
- `.gitignore`
- `pytest.ini`
- `tsconfig.json`
- `package.json` (unless adding new dependencies that affect specs)
- `requirements.txt` (unless adding new dependencies that affect specs)

### Non-Functional Changes
- Whitespace-only changes
- Comment-only changes
- Code formatting changes (unless they affect public APIs)
- Import reordering (unless it changes behavior)

### Test Fixtures and Utilities
- `tests/fixtures/**` (don't require separate tests)
- `tests/conftest.py` (test infrastructure)
- Test helper functions (don't require separate tests)

## Conflict Resolution

### When Steering Rules Conflict with Detected Drift

**Priority: Alignment > Rules**

If a steering rule suggests ignoring a file, but that file contains genuine drift, the system MUST:

1. Flag the drift (alignment takes priority)
2. Notify the developer of the conflict
3. Suggest updating the steering rules if the drift is intentional

### Example Conflict Scenario

**Scenario:** Developer adds a new endpoint to `backend/handlers/admin.py`, but steering rules say to ignore `admin.py` files.

**Resolution:**
1. Detect drift: New endpoint not in spec
2. Flag the drift despite the ignore rule
3. Notify: "Drift detected in `backend/handlers/admin.py`. Note: This file matches an ignore pattern in steering rules. If this is intentional, update the spec and steering rules."

### When Multiple Correlation Patterns Match

If multiple patterns could apply to a file, use the most specific pattern:

- `backend/handlers/user.py` matches both:
  - `backend/handlers/*.py` → `.kiro/specs/app.yaml`
  - `backend/**/*.py` → `.kiro/specs/app.yaml`
- Use the first pattern (more specific)

## Hot-Reload Behavior

Changes to this steering rules document take effect on the next validation run. No system restart required.

### What Triggers Reload

- Any modification to `.kiro/steering/rules.md`
- File save detected by Kiro
- Next commit validation will use updated rules

### What Doesn't Trigger Reload

- Changes to other files in `.kiro/steering/`
- Comments or whitespace changes in this file (rules are still reloaded, but behavior is unchanged)

## Validation Workflow

When Kiro validates a commit, it follows this workflow:

1. **Load Steering Rules** - Parse this document and cache rules
2. **Get Git Context** - Use MCP tool to get staged diff and files
3. **Apply Correlation Patterns** - Map staged files to specs, tests, docs
4. **Check for False Positives** - Filter out ignored files
5. **Detect Drift** - Compare code vs spec, code vs tests, code vs docs
6. **Apply Validation Priorities** - Order issues by priority
7. **Generate Suggestions** - Create minimal, actionable fix suggestions
8. **Handle Conflicts** - Resolve any rule-drift conflicts
9. **Return Result** - Allow or block commit with detailed feedback

## Custom Project Conventions

### Naming Conventions

- Test files must be named `test_*.py` or `*_test.py`
- API documentation files should match endpoint paths: `/users` → `docs/api/users.md`
- Spec files use kebab-case: `user-api.yaml`, `auth-api.yaml`

### Code Organization

- All endpoint handlers go in `backend/handlers/`
- All data models go in `backend/models.py`
- All tests go in `tests/` with subdirectories: `unit/`, `integration/`, `property/`

### Documentation Standards

- All public endpoints must have documentation in `docs/api/`
- Documentation must include: description, request format, response format, example
- Architecture changes must update `docs/architecture.md`

## Edge Cases

### New Files Without Existing Specs

When a completely new module is added:
1. Require spec creation first
2. Suggest creating spec in `.kiro/specs/`
3. Block commit until spec exists

### Refactoring Without Behavior Changes

When code is refactored but behavior is unchanged:
1. Verify spec still matches behavior
2. Verify tests still pass
3. Allow commit if alignment maintained
4. Documentation updates optional for internal refactoring

### Experimental Features

For experimental or work-in-progress features:
1. Use feature flags in code
2. Mark as experimental in spec
3. Tests still required
4. Documentation can be minimal but must exist

## Examples

### Example 1: Adding a New Endpoint

**Staged Changes:**
- `backend/handlers/user.py` - Added `GET /users/{id}/posts` endpoint

**Expected Validation:**
1. Check `.kiro/specs/app.yaml` for endpoint definition
2. Check `tests/unit/test_user.py` for endpoint tests
3. Check `docs/api/users.md` for endpoint documentation

**If Drift Detected:**
- Suggestion 1: Add endpoint definition to `.kiro/specs/app.yaml`
- Suggestion 2: Add test for `GET /users/{id}/posts` in `tests/unit/test_user.py`
- Suggestion 3: Document endpoint in `docs/api/users.md`

### Example 2: Modifying a Model

**Staged Changes:**
- `backend/models.py` - Added `email_verified` field to `User` model

**Expected Validation:**
1. Check `.kiro/specs/app.yaml` models section for field definition
2. Check tests for field validation
3. Check API docs for field in response schemas

**If Drift Detected:**
- Suggestion 1: Add `email_verified` field to User model in `.kiro/specs/app.yaml`
- Suggestion 2: Add test for `email_verified` field validation
- Suggestion 3: Update response schemas in `docs/api/users.md`

### Example 3: Removing Functionality

**Staged Changes:**
- `backend/handlers/user.py` - Removed `DELETE /users/{id}` endpoint

**Expected Validation:**
1. Check if endpoint still defined in `.kiro/specs/app.yaml`
2. Check if tests still exist for deleted endpoint
3. Check if documentation still references endpoint

**If Drift Detected:**
- Suggestion 1: Remove endpoint definition from `.kiro/specs/app.yaml`
- Suggestion 2: Remove tests for `DELETE /users/{id}` from `tests/unit/test_user.py`
- Suggestion 3: Remove endpoint documentation from `docs/api/users.md`

## Rule Syntax Reference

### Correlation Pattern Syntax

```
<source_pattern> → <target_pattern>
```

- `*` matches any characters except `/`
- `**` matches any characters including `/`
- `{name}` captures a variable for use in target pattern

### Priority Syntax

```
1. <Category> (Priority Level)
   - Description
```

Priorities are ordered numerically (1 = highest)

### Ignore Pattern Syntax

```
<glob_pattern>
```

Standard glob patterns for file matching

## Maintenance

This steering rules document should be updated when:

- New file organization patterns emerge
- New types of artifacts are added (e.g., GraphQL schemas)
- Project conventions change
- False positives are consistently detected
- New validation priorities are needed

Always commit steering rule changes separately from code changes to make the rule evolution clear in git history.
