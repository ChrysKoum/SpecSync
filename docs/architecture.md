# SpecSync Architecture

## Overview

SpecSync is a commit-driven reliability layer that maintains synchronization between specifications, code, tests, and documentation. The system operates as a quality gate at commit-time, using Kiro's agentic capabilities combined with custom MCP tools and hooks to detect and resolve drift before changes enter the codebase.

## Core Concept

SpecSync follows a **trigger-analyze-validate-suggest** pattern:

1. **Trigger**: Git commit initiates the pre-commit hook
2. **Analyze**: MCP tool extracts git context (branch, staged diff)
3. **Validate**: Kiro agent analyzes changes against specs, tests, and docs
4. **Suggest**: System validates alignment and suggests fixes if needed
5. **Decision**: Commit proceeds only when alignment is confirmed

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Developer Workflow                       │
│                                                               │
│  git add files → git commit → SpecSync Validation            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Pre-Commit Hook                           │
│  (.kiro/hooks/precommit.json)                               │
│                                                               │
│  Triggers: On commit event                                   │
│  Action: Invoke Kiro agent with validation prompt           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    MCP Git Context Tool                      │
│  (mcp/git_context/)                                          │
│                                                               │
│  • Reads: git diff --cached                                  │
│  • Reads: git rev-parse --abbrev-ref HEAD                    │
│  • Returns: Structured git context                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Kiro Agent                              │
│  (Guided by .kiro/steering/rules.md)                        │
│                                                               │
│  1. Parse staged changes                                     │
│  2. Load relevant specs from .kiro/specs/                    │
│  3. Analyze drift:                                           │
│     • Spec ↔ Code alignment                                  │
│     • Code ↔ Test coverage                                   │
│     • Code ↔ Documentation sync                              │
│  4. Generate validation report                               │
│  5. Suggest fixes if drift detected                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Validation Result                         │
│                                                               │
│  ✓ Aligned → Commit proceeds                                 │
│  ✗ Drift detected → Block commit + Show suggestions          │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
[Developer] → [Git Commit] → [Hook Trigger] → [MCP Tool]
                                                    ↓
                                            [Git Context]
                                                    ↓
[Validation Report] ← [Drift Analysis] ← [Kiro Agent]
        ↓                                           ↑
[Commit Decision]                          [Steering Rules]
```

## Core Components

### 1. MCP Git Context Tool

**Location:** `mcp/`

**Technology:** Node.js with TypeScript

**Purpose:** Provides git repository context to Kiro agent

**Key Functions:**
- Executes `git diff --cached` to capture staged changes
- Executes `git rev-parse --abbrev-ref HEAD` for branch detection
- Returns structured JSON with branch, staged files, and diff content
- Handles errors gracefully (non-git directories, empty staging area)

**Interface:**
```typescript
interface GitContextResponse {
  branch: string;           // Current branch name or commit SHA
  stagedFiles: string[];    // List of staged file paths
  diff: string;             // Full diff output
  error?: string;           // Error message if git commands fail
}
```

### 2. Pre-Commit Hook

**Location:** `.kiro/hooks/precommit.json`

**Purpose:** Triggers Kiro validation on commit events

**Configuration:**
```json
{
  "trigger": "on_commit",
  "action": "send_message",
  "message": "Validate staged changes for spec-code-test-doc alignment"
}
```

**Behavior:**
- Executes before commit is finalized
- Sends validation prompt to Kiro
- Waits for Kiro's validation response
- Blocks commit if drift is detected

### 3. Specification Repository

**Location:** `.kiro/specs/`

**Format:** YAML

**Purpose:** Stores service specifications that define expected behavior

**Structure:**
```
.kiro/specs/
  ├── app.yaml              # Main service spec
  └── modules/
      ├── user-api.yaml     # User module spec
      └── auth-api.yaml     # Auth module spec
```

**Spec Contents:**
- Service metadata (name, version, description)
- Endpoint definitions (path, method, parameters, responses)
- Data model schemas
- Test requirements
- Documentation requirements

### 4. Steering Rules

**Location:** `.kiro/steering/rules.md`

**Purpose:** Guides Kiro's validation behavior and drift detection logic

**Key Rules:**
- **File Correlation Patterns**: Maps code files to spec sections
- **Minimal Change Policy**: Limits suggestions to necessary fixes only
- **Validation Priorities**: Spec alignment > test coverage > documentation
- **False Positive Handling**: Ignores generated files and vendor code

### 5. Validation Logic

**Location:** `backend/` (Python modules)

**Components:**
- **Drift Detector** (`drift_detector.py`): Compares code against specs
- **Test Analyzer** (`test_analyzer.py`): Validates test coverage
- **Doc Analyzer** (`doc_analyzer.py`): Checks documentation alignment
- **Suggestion Generator** (`suggestion_generator.py`): Creates fix suggestions
- **Validator** (`validator.py`): Orchestrates all validation steps

### 6. Example Service

**Location:** `backend/`

**Technology:** Python with FastAPI

**Purpose:** Demonstrates SpecSync managing a real service

**Structure:**
```
backend/
  ├── main.py              # FastAPI app entry point
  ├── handlers/
  │   ├── user.py          # User endpoint handlers
  │   └── health.py        # Health check handler
  └── models.py            # Pydantic models
```

## Commit Flow

### Normal Commit Flow (Aligned Changes)

```
1. Developer makes changes
   ├── Modifies backend/handlers/user.py
   ├── Updates tests/test_user_handlers.py
   └── Updates docs/api/users.md

2. Developer stages changes
   $ git add backend/handlers/user.py tests/test_user_handlers.py docs/api/users.md

3. Developer initiates commit
   $ git commit -m "Add user filtering feature"

4. Pre-commit hook triggers
   └── Kiro agent invoked with validation prompt

5. MCP tool extracts git context
   ├── Branch: main
   ├── Staged files: [user.py, test_user_handlers.py, users.md]
   └── Diff: [full diff content]

6. Kiro agent validates
   ├── Loads .kiro/specs/app.yaml
   ├── Applies .kiro/steering/rules.md
   ├── Checks spec-code alignment ✓
   ├── Checks test coverage ✓
   └── Checks documentation sync ✓

7. Validation succeeds
   └── Commit proceeds

8. Changes committed
   └── Git history updated
```

### Drift Detection Flow (Misaligned Changes)

```
1. Developer makes changes
   └── Modifies backend/handlers/user.py (adds new endpoint)

2. Developer stages changes
   $ git add backend/handlers/user.py

3. Developer initiates commit
   $ git commit -m "Add user search endpoint"

4. Pre-commit hook triggers
   └── Kiro agent invoked

5. MCP tool extracts git context
   ├── Branch: feature/user-search
   ├── Staged files: [user.py]
   └── Diff: [shows new endpoint]

6. Kiro agent validates
   ├── Loads .kiro/specs/app.yaml
   ├── Checks spec-code alignment ✗
   │   └── New endpoint not in spec
   ├── Checks test coverage ✗
   │   └── No tests for new endpoint
   └── Checks documentation sync ✗
       └── No docs for new endpoint

7. Validation fails - Drift detected
   ├── Issue 1: New endpoint /users/search not in spec
   ├── Issue 2: Missing tests for /users/search
   └── Issue 3: Missing documentation for /users/search

8. Suggestions generated
   ├── Add endpoint definition to .kiro/specs/app.yaml
   ├── Create tests in tests/test_user_handlers.py
   └── Document endpoint in docs/api/users.md

9. Commit blocked
   └── Developer must fix drift before committing

10. Developer fixes drift
    ├── Updates spec
    ├── Adds tests
    └── Updates docs

11. Developer re-attempts commit
    └── Validation succeeds → Commit proceeds
```

## Data Flow

### Validation Data Flow

```
┌──────────────┐
│ Git Staging  │
│    Area      │
└──────┬───────┘
       │
       ↓ (git diff --cached)
┌──────────────┐
│  MCP Tool    │
└──────┬───────┘
       │
       ↓ (GitContext JSON)
┌──────────────┐
│ Kiro Agent   │
└──────┬───────┘
       │
       ├─→ Load Specs (.kiro/specs/)
       ├─→ Load Rules (.kiro/steering/)
       ├─→ Analyze Drift
       │   ├─→ Spec Alignment
       │   ├─→ Test Coverage
       │   └─→ Doc Sync
       │
       ↓ (ValidationResult)
┌──────────────┐
│   Commit     │
│   Decision   │
└──────────────┘
```

## Key Design Principles

### 1. Commit-Time Validation

Validation occurs at commit-time rather than during development or CI/CD. This provides:
- **Immediate Feedback**: Developers know about drift before pushing
- **Prevention**: Drift never enters the codebase
- **Context**: Validation happens with full context of changes

### 2. Agentic Validation

Kiro agent performs intelligent analysis rather than simple rule matching:
- **Semantic Understanding**: Understands code intent, not just syntax
- **Context-Aware**: Considers project conventions and patterns
- **Adaptive**: Learns from steering rules and project structure

### 3. Multi-Artifact Alignment

Validates alignment across four artifacts:
- **Specifications**: What the system should do
- **Code**: What the system actually does
- **Tests**: Verification that code matches specs
- **Documentation**: Human-readable description of behavior

### 4. Actionable Suggestions

When drift is detected, the system provides:
- **Specific Issues**: Exact misalignments identified
- **Concrete Fixes**: Precise changes needed
- **Prioritization**: Issues ordered by impact
- **Context**: Why each change is needed

## Performance Considerations

### Validation Performance

- **Target**: Complete validation within 30 seconds for typical changesets
- **Optimization Strategies**:
  - Cache parsed specs to avoid repeated file I/O
  - Limit diff analysis to staged files only
  - Use incremental validation for large commits
  - Implement timeout mechanisms to prevent hanging

### Scalability

- **Small Commits**: < 1 second validation time
- **Medium Commits**: 5-10 seconds validation time
- **Large Commits**: Up to 30 seconds validation time
- **Timeout**: Partial results returned if 30-second limit exceeded

## Security Considerations

### Input Validation

- Validate all file paths to prevent directory traversal
- Sanitize git command inputs to prevent injection
- Limit file size for diff analysis

### Isolation

- Run validation in isolated environment
- No modification of staging area during validation
- Read-only access to repository during analysis

## Extensibility

The architecture supports future extensions:

- **Additional MCP Tools**: Support for other VCS systems (SVN, Mercurial)
- **Custom Validation Rules**: Project-specific drift detectors
- **CI/CD Integration**: Run validation in continuous integration pipelines
- **Language Support**: Extend to additional programming languages
- **Plugin System**: Custom drift detectors and suggestion generators

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| MCP Tool | Node.js + TypeScript | Git command execution |
| Example Service | Python + FastAPI | Demonstration service |
| Testing | pytest + Hypothesis | Unit and property-based tests |
| Specs | YAML | Service specifications |
| Documentation | Markdown | Human-readable docs |
| Hooks | Kiro Hooks | Commit-time triggers |

## Directory Structure

```
specsync/
├── .kiro/
│   ├── specs/
│   │   └── app.yaml              # Service specifications
│   ├── steering/
│   │   └── rules.md              # Validation rules
│   └── hooks/
│       └── precommit.json        # Pre-commit hook config
├── mcp/
│   ├── src/
│   │   ├── server.ts             # MCP server
│   │   ├── git.ts                # Git operations
│   │   └── types.ts              # TypeScript types
│   └── package.json
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── models.py                 # Data models
│   ├── handlers/
│   │   ├── health.py             # Health endpoint
│   │   └── user.py               # User endpoints
│   ├── drift_detector.py         # Drift detection logic
│   ├── test_analyzer.py          # Test coverage analysis
│   ├── doc_analyzer.py           # Documentation validation
│   ├── suggestion_generator.py   # Fix suggestions
│   └── validator.py              # Validation orchestrator
├── tests/
│   ├── unit/                     # Unit tests
│   ├── property/                 # Property-based tests
│   └── integration/              # Integration tests
└── docs/
    ├── index.md                  # Documentation home
    ├── architecture.md           # This document
    └── api/
        ├── health.md             # Health endpoint docs
        └── users.md              # User endpoint docs
```

## Conclusion

SpecSync provides a robust, commit-driven approach to maintaining alignment between specifications, code, tests, and documentation. By leveraging Kiro's agentic capabilities and custom MCP tools, the system prevents drift before it enters the codebase, ensuring long-term maintainability and reliability.
