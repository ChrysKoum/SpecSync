# Design Document

## Overview

SpecSync is a commit-driven reliability layer that maintains synchronization between specifications, code, tests, and documentation. The system operates as a quality gate at commit-time, using Kiro's agentic capabilities combined with custom MCP tools and hooks to detect and resolve drift before changes enter the codebase.

The architecture follows a trigger-analyze-validate-suggest pattern:
1. Git commit triggers the pre-commit hook
2. MCP tool extracts git context (branch, staged diff)
3. Kiro agent analyzes changes against specs, tests, and docs
4. System validates alignment and suggests fixes if needed
5. Commit proceeds only when alignment is confirmed

## Architecture

### High-Level Architecture

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

## Components and Interfaces

### 1. MCP Git Context Tool

**Location:** `mcp/git_context/`

**Purpose:** Provides git repository context to Kiro agent

**Interface:**
```typescript
// Tool: get_staged_diff
// Returns staged changes and branch information

interface GitContextResponse {
  branch: string;           // Current branch name or commit SHA
  stagedFiles: string[];    // List of staged file paths
  diff: string;             // Full diff output from git diff --cached
  error?: string;           // Error message if git commands fail
}
```

**Implementation Details:**
- Uses Node.js child_process to execute git commands
- Handles errors gracefully (non-git directories, empty staging area)
- Returns structured JSON for Kiro consumption
- Supports detached HEAD state by returning commit SHA

### 2. Pre-Commit Hook

**Location:** `.kiro/hooks/precommit.json`

**Purpose:** Triggers Kiro validation on commit events

**Configuration:**
```json
{
  "trigger": "on_commit",
  "action": "send_message",
  "message": "Validate staged changes for spec-code-test-doc alignment using SpecForge rules"
}
```

**Behavior:**
- Executes before commit is finalized
- Sends validation prompt to Kiro
- Waits for Kiro's validation response
- Blocks commit if drift is detected

### 3. Steering Rules

**Location:** `.kiro/steering/rules.md`

**Purpose:** Guides Kiro's validation behavior and drift detection logic

**Key Rules:**
- File correlation patterns (e.g., `backend/handlers/user.py` → `specs/user-api.yaml`)
- Minimal change policy (only suggest necessary fixes)
- Validation priorities (spec alignment > test coverage > documentation)
- False positive handling (ignore generated files, vendor code)

### 4. Spec Repository

**Location:** `.kiro/specs/`

**Purpose:** Stores service specifications that define expected behavior

**Structure:**
```
.kiro/specs/
  ├── app.yaml              # Main service spec
  └── modules/
      ├── user-api.yaml     # User module spec
      └── auth-api.yaml     # Auth module spec
```

**Spec Format (YAML):**
```yaml
service:
  name: "example-service"
  version: "1.0.0"

endpoints:
  - path: "/users"
    method: "GET"
    description: "List all users"
    response:
      type: "array"
      items: "User"
    tests_required: true
    
  - path: "/users/{id}"
    method: "GET"
    description: "Get user by ID"
    parameters:
      - name: "id"
        type: "integer"
    response:
      type: "User"
    tests_required: true

models:
  User:
    fields:
      - name: "id"
        type: "integer"
      - name: "username"
        type: "string"
      - name: "email"
        type: "string"
```

### 5. Example FastAPI Service

**Location:** `backend/`

**Purpose:** Demonstrates SpecForge managing a real service

**Structure:**
```
backend/
  ├── main.py              # FastAPI app entry point
  ├── handlers/
  │   ├── user.py          # User endpoint handlers
  │   └── health.py        # Health check handler
  └── models.py            # Pydantic models
```

**Key Endpoints:**
- `GET /health` - Health check
- `GET /users` - List users
- `GET /users/{id}` - Get user by ID

### 6. Test Suite

**Location:** `tests/`

**Purpose:** Validates service behavior

**Structure:**
```
tests/
  ├── test_user_handlers.py    # User endpoint tests
  └── test_health.py            # Health check tests
```

### 7. Documentation

**Location:** `docs/`

**Purpose:** API documentation maintained by SpecForge

**Structure:**
```
docs/
  ├── index.md              # Overview
  ├── api/
  │   ├── users.md          # User API docs
  │   └── health.md         # Health API docs
  └── architecture.md       # System architecture
```

## Data Models

### GitContext

Represents the current state of staged changes:

```typescript
interface GitContext {
  branch: string;
  stagedFiles: string[];
  diff: string;
  timestamp: string;
}
```

### DriftReport

Represents detected misalignments:

```typescript
interface DriftReport {
  aligned: boolean;
  issues: DriftIssue[];
  suggestions: string[];
}

interface DriftIssue {
  type: 'spec' | 'test' | 'doc';
  severity: 'error' | 'warning';
  file: string;
  description: string;
  expectedBehavior: string;
  actualBehavior: string;
}
```

### ValidationResult

Final validation outcome:

```typescript
interface ValidationResult {
  success: boolean;
  message: string;
  driftReport?: DriftReport;
  allowCommit: boolean;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated to eliminate redundancy:

- Drift detection properties (3.2, 3.3, 3.4) share the same underlying mechanism
- Test coverage properties (4.2, 4.3, 4.4) can be unified
- Documentation alignment properties (5.1-5.5) overlap significantly
- Suggestion generation properties (6.1-6.4) are aspects of the same feature
- Example service properties (8.3-8.5) are just applications of general properties

The consolidated properties below provide unique validation value without redundancy.

### Core Properties

**Property 1: Validation triggers on commit**
*For any* commit attempt in a git repository, the SpecSync system should trigger validation before the commit is finalized.
**Validates: Requirements 1.1**

**Property 2: Aligned commits proceed**
*For any* staged changeset where code, tests, and documentation align with specifications, the validation should report success and allow the commit to proceed.
**Validates: Requirements 1.2, 3.4, 4.4, 5.5**

**Property 3: Drift blocks commits**
*For any* staged changeset containing drift (spec-code misalignment, missing tests, or outdated docs), the validation should block the commit and provide specific feedback about each misalignment.
**Validates: Requirements 1.3, 3.2, 3.3, 4.2, 4.3, 5.2, 5.3, 5.4**

**Property 4: Validation performance**
*For any* typical changeset (under 1000 lines of diff), validation should complete within 30 seconds.
**Validates: Requirements 1.4**

**Property 5: Staged changes preservation**
*For any* validation run, the staged changes before validation should be identical to the staged changes after validation, regardless of validation outcome.
**Validates: Requirements 1.5**

**Property 6: Git context extraction**
*For any* git repository state, the MCP tool should return structured data containing the current branch (or commit SHA in detached HEAD), list of staged files, and the complete diff output.
**Validates: Requirements 2.1, 2.2, 2.3, 2.5**

**Property 7: Git error handling**
*For any* git command failure (non-git directory, permission errors, etc.), the MCP tool should return an error message that identifies the specific failure reason.
**Validates: Requirements 2.4**

**Property 8: Multi-file validation**
*For any* commit with multiple staged files, the system should validate each file against its corresponding spec section and report alignment status for each file independently.
**Validates: Requirements 3.1, 3.5**

**Property 9: Test-code mapping**
*For any* staged code file, the system should identify which test files should cover that code based on project structure and naming conventions.
**Validates: Requirements 4.1**

**Property 10: Test-spec-code alignment**
*For any* modified test file, the system should validate that the tests align with both the corresponding code implementation and the spec requirements.
**Validates: Requirements 4.5**

**Property 11: API documentation verification**
*For any* staged change that modifies public APIs or interfaces, the system should verify that corresponding documentation exists and accurately describes the API behavior.
**Validates: Requirements 5.1**

**Property 12: Drift suggestions**
*For any* detected drift, the system should generate specific, actionable suggestions for resolving each misalignment, including exact modifications for specs, tests, or documentation.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

**Property 13: Suggestion prioritization**
*For any* drift report with multiple issues, suggestions should be ordered by impact (spec drift > test coverage > documentation) and presented in a logical sequence for resolution.
**Validates: Requirements 6.5**

**Property 14: Steering rule application**
*For any* validation run, the system should apply all rules defined in the steering document, including correlation patterns and minimal change policies.
**Validates: Requirements 7.1, 7.2, 7.3**

**Property 15: Steering rule hot-reload**
*For any* update to the steering rules document, the next validation should apply the new rules without requiring system restart.
**Validates: Requirements 7.4**

**Property 16: Alignment priority over rules**
*For any* conflict between steering rule preferences and detected drift, the system should prioritize alignment (flag the drift) and notify the developer of the conflict.
**Validates: Requirements 7.5**

**Property 17: Example service validation**
*For any* modification to the example FastAPI service, the system should validate changes against the service spec and verify test coverage for all endpoints.
**Validates: Requirements 8.3, 8.4, 8.5**

## Error Handling

### Git Command Failures

**Scenarios:**
- Non-git directory: Return clear error indicating git repository not found
- Empty staging area: Return empty diff with appropriate message
- Permission errors: Return error with permission details
- Detached HEAD: Return commit SHA instead of branch name

**Strategy:**
- Wrap all git commands in try-catch blocks
- Return structured error responses with error type and message
- Never crash the validation process due to git errors
- Provide actionable error messages to developers

### Spec Parsing Errors

**Scenarios:**
- Invalid YAML syntax: Report line number and syntax error
- Missing required fields: List missing fields
- Invalid spec structure: Describe expected structure

**Strategy:**
- Validate spec files before using them for validation
- Cache parsed specs to avoid repeated parsing
- Provide clear error messages with file paths and line numbers

### Validation Timeout

**Scenarios:**
- Large changesets exceeding 30-second limit
- Complex drift analysis taking too long

**Strategy:**
- Implement timeout mechanism for validation
- Return partial results if timeout occurs
- Suggest breaking large commits into smaller chunks

### Kiro Agent Failures

**Scenarios:**
- Kiro unavailable or not responding
- Kiro returns malformed response
- Kiro encounters internal error

**Strategy:**
- Implement retry logic with exponential backoff
- Fall back to basic validation if Kiro fails
- Log errors for debugging
- Never block commits indefinitely

## Testing Strategy

SpecForge will use a dual testing approach combining unit tests and property-based tests to ensure comprehensive coverage and correctness.

### Unit Testing

Unit tests will verify specific examples, edge cases, and integration points:

**MCP Tool Tests:**
- Test git context extraction with known repository states
- Test error handling for non-git directories
- Test detached HEAD state handling
- Test empty staging area handling

**Validation Logic Tests:**
- Test drift detection with specific code-spec mismatches
- Test suggestion generation for known drift scenarios
- Test steering rule application with sample rules
- Test multi-file validation with known file sets

**Integration Tests:**
- Test end-to-end commit flow with example service
- Test hook trigger mechanism
- Test Kiro agent interaction

**Framework:** pytest for Python components, Jest for Node.js MCP tool

### Property-Based Testing

Property-based tests will verify universal properties across all inputs using **Hypothesis** (Python) and **fast-check** (TypeScript/Node.js).

**Configuration:**
- Minimum 100 iterations per property test
- Each property test tagged with: `**Feature: specforge-core, Property {number}: {property_text}**`
- Each correctness property implemented by a SINGLE property-based test

**Key Property Tests:**

1. **Staged changes preservation** - Generate random git states, run validation, verify staging area unchanged
2. **Git context structure** - Generate random repository states, verify MCP tool always returns required fields
3. **Multi-file validation** - Generate random multi-file commits, verify each file validated independently
4. **Drift detection consistency** - Generate random code-spec pairs, verify drift detection is deterministic
5. **Suggestion completeness** - Generate random drift scenarios, verify suggestions provided for each issue
6. **Steering rule application** - Generate random rule sets and changesets, verify rules applied correctly
7. **Performance bounds** - Generate random typical changesets, verify validation completes within time limit

**Test Data Generators:**
- Git repository states (branches, staged files, diffs)
- Code files with varying complexity
- Spec definitions with different structures
- Test files with varying coverage
- Documentation with different formats
- Steering rules with various patterns

### Test Organization

```
tests/
  ├── unit/
  │   ├── test_mcp_tool.py
  │   ├── test_drift_detection.py
  │   ├── test_suggestions.py
  │   └── test_steering_rules.py
  ├── property/
  │   ├── test_properties_validation.py
  │   ├── test_properties_git.py
  │   └── test_properties_alignment.py
  ├── integration/
  │   └── test_commit_flow.py
  └── fixtures/
      ├── sample_repos/
      ├── sample_specs/
      └── sample_code/
```

### Testing the Example Service

The FastAPI example service serves as both a demonstration and a test case:
- Validate that SpecForge correctly manages the example service
- Use the example service to test real-world drift scenarios
- Verify documentation generation for the example API
- Ensure test coverage validation works with the example tests

## Implementation Notes

### Technology Stack

- **MCP Tool:** Node.js with TypeScript (for git command execution)
- **Example Service:** Python with FastAPI
- **Testing:** pytest + Hypothesis (Python), Jest + fast-check (Node.js)
- **Specs:** YAML format
- **Documentation:** Markdown

### Development Phases

1. **Phase 1:** MCP tool implementation and testing
2. **Phase 2:** Example FastAPI service with specs
3. **Phase 3:** Kiro hook and steering rules
4. **Phase 4:** Validation logic and drift detection
5. **Phase 5:** Suggestion generation
6. **Phase 6:** Integration and end-to-end testing

### Branding

**Project Name:** SpecSync
**Tagline:** "Keep your specs, code, tests, and docs in perfect sync"
**Value Proposition:** Commit-driven reliability layer that prevents drift before it enters your codebase

### Performance Considerations

- Cache parsed specs to avoid repeated file I/O
- Limit diff analysis to staged files only
- Use incremental validation for large commits
- Implement timeout mechanisms to prevent hanging

### Security Considerations

- Validate all file paths to prevent directory traversal
- Sanitize git command inputs to prevent injection
- Limit file size for diff analysis
- Run validation in isolated environment

### Extensibility

The architecture supports future extensions:
- Additional MCP tools for other VCS systems
- Custom validation rules per project
- Integration with CI/CD pipelines
- Support for additional languages and frameworks
- Plugin system for custom drift detectors
