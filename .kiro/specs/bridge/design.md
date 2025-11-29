# Design Document - SpecSync Bridge

## Overview

SpecSync Bridge is a decentralized contract synchronization system that enables API contract alignment across multiple repositories without requiring a shared parent folder. Each repository maintains its own contract cache for dependencies it interacts with, enabling offline validation and flexible deployment scenarios.

The system operates on a provider-consumer model where:
- **Providers** extract and publish API contracts from their codebase
- **Consumers** sync and cache contracts from their dependencies
- **Validation** detects drift between what consumers expect and what providers offer

**Key Design Principle:** Decentralized storage with git-based synchronization. Each repository stores only the contracts it needs, making the system scalable and flexible.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SpecSync Bridge                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Contract   │  │    Sync      │  │    Drift     │    │
│  │  Extractor   │  │   Engine     │  │  Detector    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                                │
│                   ┌────────▼────────┐                      │
│                   │  Contract Cache │                      │
│                   │  (.kiro/contracts/)                    │
│                   └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Repository Structure

Each repository maintains its own contract storage:

```
repository/
├── .kiro/
│   ├── contracts/
│   │   ├── provided-api.yaml      # What this repo provides (if provider)
│   │   ├── backend-api.yaml       # Cached contract from backend
│   │   └── auth-api.yaml          # Cached contract from auth service
│   └── settings/
│       └── bridge.json            # Bridge configuration
├── backend/                        # Application code
└── tests/                          # Tests
```

### Component Interaction Flow

```
Provider Repo:
  Code Changes → Contract Extractor → provided-api.yaml → Git Commit

Consumer Repo:
  Sync Command → Git Clone/Pull → Copy Contract → Local Cache → Validation
```

## Components and Interfaces

### 1. Contract Extractor

**Purpose:** Extract API contracts from source code (Python FastAPI, TypeScript Express, etc.)

**Interface:**
```python
class ContractExtractor:
    def __init__(self, repo_root: str)
    def extract_from_files(self, file_patterns: List[str]) -> Dict[str, Any]
    def save_contract(self, contract: Dict, output_path: str) -> Path
    
    # Private methods
    def _extract_from_file(self, file_path: Path) -> tuple
    def _extract_endpoint(self, node: ast.FunctionDef, file_path: Path) -> Optional[Dict]
    def _extract_return_type(self, node: ast.FunctionDef) -> Dict
    def _extract_parameters(self, node: ast.FunctionDef) -> List[Dict]
    def _extract_model(self, node: ast.ClassDef) -> Optional[Dict]
```

**Responsibilities:**
- Parse source code using AST (Abstract Syntax Tree)
- Identify API endpoints (decorators like `@app.get`, `@app.post`)
- Extract endpoint metadata (path, method, parameters, response types)
- Extract data models (Pydantic models, TypeScript interfaces)
- Aggregate contracts from multiple files
- Generate timestamped contract files

**Design Decision:** Use AST parsing instead of regex to ensure accurate extraction and handle complex code structures. This provides better reliability and maintainability.

### 2. Sync Engine

**Purpose:** Synchronize contracts between repositories using multiple sync methods

**Interface:**
```python
class SyncEngine:
    def __init__(self, config: BridgeConfig)
    def sync_dependency(self, dependency_name: str) -> SyncResult
    def sync_all_dependencies(self) -> List[SyncResult]
    
    # Sync method implementations
    def _sync_via_git(self, dependency: Dependency) -> SyncResult
    def _sync_via_http(self, dependency: Dependency) -> SyncResult
    def _sync_via_cloud(self, dependency: Dependency) -> SyncResult
    
    # Helper methods
    def _clone_or_pull_repo(self, git_url: str, temp_dir: Path) -> Path
    def _copy_contract_file(self, source: Path, dest: Path) -> None
    def _compare_contracts(self, old: Dict, new: Dict) -> ContractDiff
```

**Responsibilities:**
- Read bridge configuration
- Execute sync operations for configured dependencies
- Support multiple sync methods (git, HTTP, cloud storage)
- Handle temporary directories for git operations
- Compare old and new contracts to detect changes
- Update local contract cache
- Provide detailed sync results and error handling

**Design Decision:** Support multiple sync methods to accommodate different deployment scenarios. Git-based sync is the default for version control benefits, but HTTP and cloud storage options provide flexibility for CI/CD pipelines and real-time scenarios.

### 3. Drift Detector

**Purpose:** Identify mismatches between consumer expectations and provider contracts

**Interface:**
```python
class DriftDetector:
    def __init__(self, repo_root: str)
    def detect_drift(self, dependency_name: str) -> List[DriftIssue]
    def detect_all_drift(self) -> Dict[str, List[DriftIssue]]
    
    # Detection methods
    def _find_api_calls_in_code(self, file_patterns: List[str]) -> List[APICall]
    def _check_endpoint_exists(self, api_call: APICall, contract: Dict) -> Optional[DriftIssue]
    def _check_parameter_compatibility(self, api_call: APICall, endpoint: Dict) -> Optional[DriftIssue]
    def _check_response_compatibility(self, expected: Dict, actual: Dict) -> Optional[DriftIssue]
```

**Drift Types:**
- **Missing Endpoint:** Consumer calls endpoint not in provider contract
- **Parameter Mismatch:** Consumer passes parameters provider doesn't accept
- **Response Mismatch:** Consumer expects different response structure
- **Method Mismatch:** Consumer uses wrong HTTP method
- **Deprecated Endpoint:** Consumer uses endpoint marked as deprecated

**Design Decision:** Perform static analysis on consumer code to find API calls, then validate against cached contracts. This enables offline validation and catches issues before runtime.

### 4. Configuration Manager

**Purpose:** Manage bridge configuration and dependency definitions

**Interface:**
```python
class BridgeConfig:
    def __init__(self, config_path: str = ".kiro/settings/bridge.json")
    def load(self) -> Dict
    def save(self, config: Dict) -> None
    def add_dependency(self, name: str, dependency: Dependency) -> None
    def remove_dependency(self, name: str) -> None
    def get_dependency(self, name: str) -> Optional[Dependency]
    def list_dependencies(self) -> List[str]
```

**Configuration Schema:**
```json
{
  "bridge": {
    "enabled": true,
    "role": "consumer|provider|both",
    "repo_id": "string",
    
    "provides": {
      "contract_file": ".kiro/contracts/provided-api.yaml",
      "extract_from": ["backend/**/*.py"],
      "auto_update": true
    },
    
    "dependencies": {
      "backend": {
        "type": "http-api",
        "sync_method": "git|http|s3",
        "git_url": "https://github.com/org/repo.git",
        "contract_path": ".kiro/contracts/provided-api.yaml",
        "local_cache": ".kiro/contracts/backend-api.yaml",
        "sync_on_commit": true
      }
    }
  }
}
```

### 5. CLI Interface

**Purpose:** Provide command-line interface for bridge operations

**Commands:**
```bash
specsync bridge init [--role provider|consumer]
specsync bridge add-dependency <name> --git-url <url> [--contract-path <path>]
specsync bridge sync [dependency-name]
specsync bridge validate
specsync bridge status
```

**Interface:**
```python
class BridgeCLI:
    def init(self, role: str) -> None
    def add_dependency(self, name: str, git_url: str, contract_path: str) -> None
    def sync(self, dependency_name: Optional[str] = None) -> None
    def validate(self) -> None
    def status(self) -> None
```

## Data Models

### Contract Schema

```yaml
# Provider Contract (.kiro/contracts/provided-api.yaml)
version: "1.0"
repo_id: "backend"
role: "provider"
last_updated: "2024-11-27T15:00:00Z"

endpoints:
  - id: "get-user"
    path: "/users/{id}"
    method: "GET"
    status: "implemented"
    implemented_at: "2024-11-20T10:00:00Z"
    source_file: "backend/handlers/user.py"
    function_name: "get_user"
    
    parameters:
      - name: "id"
        type: "integer"
        required: true
        location: "path"
    
    response:
      status: 200
      type: "object"
      schema: "User"
    
    consumers: ["frontend", "mobile"]

models:
  User:
    fields:
      - name: "id"
        type: "integer"
      - name: "name"
        type: "string"
      - name: "email"
        type: "string"
```

### Dependency Configuration

```python
@dataclass
class Dependency:
    name: str
    type: str  # "http-api", "graphql", "grpc"
    sync_method: str  # "git", "http", "s3"
    git_url: Optional[str]
    contract_path: str
    local_cache: str
    sync_on_commit: bool
```

### Drift Issue

```python
@dataclass
class DriftIssue:
    type: str  # "missing_endpoint", "parameter_mismatch", etc.
    severity: str  # "error", "warning"
    endpoint: str
    method: str
    location: str  # File and line number
    message: str
    suggestion: str
```

### Sync Result

```python
@dataclass
class SyncResult:
    dependency_name: str
    success: bool
    changes: List[str]
    errors: List[str]
    timestamp: datetime
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property Reflection

After reviewing all testable criteria, several properties can be consolidated:

- Properties 1.2, 1.4, and 5.1 all test file creation - can be combined into "File operations create expected artifacts"
- Properties 2.2 and 2.5 both test sync results - can be combined into "Sync operations produce complete results"
- Properties 3.2, 3.3, and 3.4 all test drift reporting - can be combined into "Drift detection produces complete reports"
- Properties 6.2 and 6.3 both test temp directory handling - can be combined into "Git operations manage temporary resources"
- Properties 7.2 and 7.4 both test multi-sync reporting - can be combined into "Parallel sync operations report all results"

### Contract Extraction Properties

**Property 1: Endpoint extraction completeness**
*For any* Python file containing FastAPI endpoints, extracting the contract should produce entries for all decorated endpoint functions with their complete metadata (path, method, parameters, response type).
**Validates: Requirements 1.1, 1.3**

**Property 2: Multi-file aggregation**
*For any* set of Python files containing endpoints, extracting from all files should produce a single contract containing all endpoints from all files.
**Validates: Requirements 1.5**

**Property 3: Contract persistence**
*For any* extracted contract, saving it should create a file at the specified path containing all contract data and a valid ISO 8601 timestamp.
**Validates: Requirements 1.2, 1.4**

### Sync Properties

**Property 4: Sync retrieval**
*For any* valid dependency configuration with an accessible repository, running sync should successfully fetch the contract from the specified path.
**Validates: Requirements 2.1**

**Property 5: Sync result completeness**
*For any* successful sync operation, the result should include the cached contract file path, endpoint count, and list of changes since last sync.
**Validates: Requirements 2.2, 2.5**

**Property 6: Contract diff detection**
*For any* two different contract versions, computing the diff should identify all added, removed, and modified endpoints.
**Validates: Requirements 2.3**

**Property 7: Offline fallback**
*For any* sync operation that fails due to inaccessible repository, the system should use the cached contract if available and include a warning in the result.
**Validates: Requirements 2.4, 6.5**

### Drift Detection Properties

**Property 8: API call validation**
*For any* API call found in consumer code, validation should check whether a matching endpoint (same path and method) exists in the cached contract.
**Validates: Requirements 3.1**

**Property 9: Drift reporting completeness**
*For any* API call that doesn't match a contract endpoint, the drift report should include the endpoint path, method, source location, and a suggestion for remediation.
**Validates: Requirements 3.2, 3.3, 3.4**

**Property 10: Successful validation reporting**
*For any* validation where all API calls match contract endpoints, the result should indicate successful alignment with zero drift issues.
**Validates: Requirements 3.5**

### Usage Tracking Properties

**Property 11: Usage location tracking**
*For any* API call detected in consumer code, the system should record the file path and line number where it appears.
**Validates: Requirements 4.2**

**Property 12: Consumer expectation recording**
*For any* sync operation from a consumer repository, the cached contract should include a list of endpoints the consumer expects to use.
**Validates: Requirements 4.1**

**Property 13: Breaking change detection**
*For any* endpoint that is modified or removed in a provider contract, if that endpoint has recorded consumers, a warning should be generated.
**Validates: Requirements 4.3, 4.4**

**Property 14: Unused endpoint identification**
*For any* endpoint in a provider contract with zero recorded consumers, it should be marked as potentially removable.
**Validates: Requirements 4.5**

### Configuration Properties

**Property 15: Configuration initialization**
*For any* init operation, the system should create a valid bridge.json file at `.kiro/settings/bridge.json` with required fields.
**Validates: Requirements 5.1**

**Property 16: Dependency persistence**
*For any* add-dependency operation with valid parameters, the configuration should be updated to include the new dependency with all provided details (name, git_url, contract_path).
**Validates: Requirements 5.2**

**Property 17: Configuration validation**
*For any* configuration save operation, if required fields are missing, the operation should fail with a descriptive error.
**Validates: Requirements 5.3**

**Property 18: Multi-dependency sync support**
*For any* configuration with N dependencies (N ≥ 1), running sync-all should attempt to sync all N dependencies.
**Validates: Requirements 5.4**

**Property 19: Dependency removal cleanup**
*For any* remove-dependency operation, the cached contract file for that dependency should be deleted if it exists.
**Validates: Requirements 5.5**

### Git Operations Properties

**Property 20: Git sync independence**
*For any* valid git URL and contract path, sync should succeed regardless of the local repository location.
**Validates: Requirements 6.1**

**Property 21: Temporary resource management**
*For any* git sync operation, temporary directories should be created for git operations and cleaned up after completion (success or failure).
**Validates: Requirements 6.2, 6.3**

**Property 22: Git error clarity**
*For any* failed git operation, the error message should include the git command that failed and the underlying error reason.
**Validates: Requirements 6.4**

### Parallel Sync Properties

**Property 23: Parallel execution**
*For any* sync-all operation with multiple dependencies, syncs should execute concurrently (not sequentially).
**Validates: Requirements 7.1**

**Property 24: Parallel sync reporting**
*For any* multi-dependency sync operation, the result should include progress updates during execution and final status for each dependency.
**Validates: Requirements 7.2, 7.4**

**Property 25: Partial failure resilience**
*For any* multi-dependency sync where at least one sync fails, all other syncs should still complete and report their results.
**Validates: Requirements 7.3**

**Property 26: Multi-contract validation**
*For any* validation operation in a repository with N cached contracts (N ≥ 1), all N contracts should be checked for drift.
**Validates: Requirements 7.5**

## Error Handling

### Error Categories

1. **Configuration Errors**
   - Missing or invalid bridge.json
   - Missing required fields in dependency configuration
   - Invalid file patterns or paths
   - **Handling:** Fail fast with clear error message, suggest fix

2. **Git Operation Errors**
   - Repository not accessible (network, permissions)
   - Invalid git URL
   - Contract file not found in repository
   - Git command failures
   - **Handling:** Fall back to cached contract if available, show warning

3. **Extraction Errors**
   - Invalid Python syntax in source files
   - Unsupported framework or decorator patterns
   - File read permissions
   - **Handling:** Skip problematic files, log warning, continue with other files

4. **Validation Errors**
   - Cached contract not found
   - Invalid contract format
   - Code parsing failures
   - **Handling:** Report error, suggest running sync first

5. **File System Errors**
   - Permission denied writing contracts
   - Disk space issues
   - Path traversal attempts
   - **Handling:** Fail operation, provide clear error with path

### Error Recovery Strategies

**Graceful Degradation:**
- If sync fails, use cached contract (if available)
- If one file fails extraction, continue with others
- If one dependency sync fails, continue with others

**Clear Error Messages:**
```
❌ Failed to sync 'backend' dependency

Reason: Repository not accessible
Git URL: https://github.com/org/backend.git
Error: fatal: could not read from remote repository

Suggestions:
  1. Check network connection
  2. Verify repository URL
  3. Check git credentials
  4. Use cached contract: .kiro/contracts/backend-api.yaml (last synced: 2 hours ago)
```

**Retry Logic:**
- Git operations: Retry up to 3 times with exponential backoff
- HTTP sync: Retry up to 3 times
- File operations: No retry (fail immediately)

## Testing Strategy

### Unit Testing

**Contract Extractor Tests:**
- Test extraction from single file with one endpoint
- Test extraction from single file with multiple endpoints
- Test extraction with various parameter types
- Test extraction with various response types
- Test extraction from multiple files
- Test handling of invalid Python syntax
- Test handling of non-FastAPI decorators
- Test model extraction from Pydantic classes

**Sync Engine Tests:**
- Test git sync with valid repository
- Test git sync with invalid repository
- Test HTTP sync with valid endpoint
- Test HTTP sync with network failure
- Test contract diff computation
- Test temporary directory cleanup
- Test parallel sync execution
- Test partial failure handling

**Drift Detector Tests:**
- Test detection of missing endpoints
- Test detection of parameter mismatches
- Test detection of method mismatches
- Test successful validation (no drift)
- Test API call extraction from code
- Test usage location tracking

**Configuration Manager Tests:**
- Test config file creation
- Test adding dependencies
- Test removing dependencies
- Test config validation
- Test loading invalid config

### Property-Based Testing

Property-based tests will use **Hypothesis** (Python PBT library) to generate random inputs and verify properties hold across all cases.

**Test Configuration:**
- Minimum 100 iterations per property test
- Use Hypothesis strategies for generating valid contracts, endpoints, and configurations
- Each property test must reference its design document property number

**Generator Strategies:**
```python
# Example generators for property tests
@st.composite
def endpoint_strategy(draw):
    """Generate random valid endpoint definitions."""
    return {
        'path': draw(st.text(min_size=1).map(lambda s: f"/{s}")),
        'method': draw(st.sampled_from(['GET', 'POST', 'PUT', 'DELETE'])),
        'parameters': draw(st.lists(parameter_strategy())),
        'response': draw(response_strategy())
    }

@st.composite
def contract_strategy(draw):
    """Generate random valid contracts."""
    return {
        'version': '1.0',
        'repo_id': draw(st.text(min_size=1)),
        'endpoints': draw(st.lists(endpoint_strategy(), min_size=1)),
        'models': draw(st.dictionaries(st.text(), model_strategy()))
    }
```

### Integration Testing

**End-to-End Scenarios:**
1. Provider extracts contract → Consumer syncs → Consumer validates (no drift)
2. Provider extracts contract → Consumer syncs → Consumer adds new API call → Validation detects drift
3. Multi-repository scenario with 3+ repos
4. Offline scenario with cached contracts
5. Parallel sync with multiple dependencies

**Test Environment:**
- Use temporary directories for test repositories
- Mock git operations for controlled testing
- Use fixture contracts for predictable scenarios

### Testing Priorities

1. **Critical Path (Must Test):**
   - Contract extraction accuracy
   - Sync operations (git-based)
   - Drift detection accuracy
   - Configuration management

2. **Important (Should Test):**
   - Error handling and recovery
   - Parallel sync operations
   - Usage tracking
   - Temporary resource cleanup

3. **Nice to Have (Can Test):**
   - HTTP sync method
   - Cloud storage sync method
   - Performance with large contracts
   - CLI output formatting

## Implementation Phases

### Phase 1: Core Extraction and Storage (MVP)
**Goal:** Extract contracts from provider code and store them locally

**Components:**
- Contract Extractor (Python FastAPI support)
- Contract file format (YAML)
- Configuration Manager (basic)
- File system operations

**Deliverables:**
- Extract contracts from Python FastAPI code
- Save contracts to `.kiro/contracts/provided-api.yaml`
- Basic configuration file support

### Phase 2: Git-Based Sync
**Goal:** Sync contracts between repositories using git

**Components:**
- Sync Engine (git method only)
- Git operations (clone, pull)
- Contract diff computation
- Temporary directory management

**Deliverables:**
- Sync contracts from remote repositories
- Show changes between contract versions
- Cache contracts locally
- Clean up temporary files

### Phase 3: Drift Detection
**Goal:** Detect mismatches between consumer code and provider contracts

**Components:**
- Drift Detector
- Code parser (Python API calls)
- Validation logic
- Usage tracking

**Deliverables:**
- Find API calls in consumer code
- Validate against cached contracts
- Report drift issues with suggestions
- Track usage locations

### Phase 4: CLI and Automation
**Goal:** Provide user-friendly CLI and automation hooks

**Components:**
- CLI interface
- Command implementations
- Output formatting
- Git hook integration

**Deliverables:**
- `specsync bridge init`
- `specsync bridge add-dependency`
- `specsync bridge sync`
- `specsync bridge validate`
- `specsync bridge status`

### Phase 5: Advanced Features
**Goal:** Support additional sync methods and multi-repo scenarios

**Components:**
- HTTP sync method
- Cloud storage sync method
- Parallel sync operations
- Breaking change detection
- Consumer notification system

**Deliverables:**
- Multiple sync method support
- Parallel dependency syncing
- Impact analysis for providers
- Automated consumer notifications

## Design Decisions and Rationales

### 1. Decentralized Storage Model

**Decision:** Each repository stores only the contracts it needs in its own `.kiro/contracts/` directory.

**Rationale:**
- **Scalability:** No central bottleneck or shared storage
- **Flexibility:** Repos can be in different locations, organizations, or git providers
- **Offline Support:** Cached contracts enable validation without network access
- **Security:** Each repo controls its own contracts via git permissions
- **Simplicity:** No need for shared parent folders or complex path resolution

**Alternative Considered:** Centralized contract registry (rejected due to single point of failure and deployment complexity)

### 2. Git-Based Sync as Default

**Decision:** Use git clone/pull as the primary sync method.

**Rationale:**
- **Version Control:** Full history of contract changes
- **Audit Trail:** Who changed what and when
- **Existing Infrastructure:** Leverages existing git authentication and permissions
- **Reliability:** Git is battle-tested and widely available
- **Offline Capability:** Can work with cached contracts when offline

**Alternative Considered:** HTTP API sync (still supported as optional method for real-time scenarios)

### 3. AST-Based Contract Extraction

**Decision:** Use Abstract Syntax Tree parsing instead of regex or string matching.

**Rationale:**
- **Accuracy:** Correctly handles complex code structures
- **Reliability:** Immune to formatting variations
- **Maintainability:** Easier to extend for new patterns
- **Type Safety:** Can extract type annotations accurately

**Alternative Considered:** Regex-based extraction (rejected due to fragility and maintenance burden)

### 4. YAML Contract Format

**Decision:** Use YAML for contract files instead of JSON or custom format.

**Rationale:**
- **Readability:** Human-friendly for manual inspection
- **Comments:** Supports comments for documentation
- **Git-Friendly:** Diffs are readable in git
- **Flexibility:** Easy to extend with new fields

**Alternative Considered:** JSON (rejected due to lack of comments and less readable diffs)

### 5. Offline-First Validation

**Decision:** Validate against cached contracts, not live repositories.

**Rationale:**
- **Performance:** No network latency during validation
- **Reliability:** Works without network access
- **Developer Experience:** Fast feedback during development
- **CI/CD Friendly:** Predictable behavior in pipelines

**Trade-off:** Requires explicit sync to get latest contracts, but this is acceptable for the benefits gained.

### 6. Property-Based Testing Focus

**Decision:** Emphasize property-based testing over exhaustive unit tests.

**Rationale:**
- **Coverage:** Tests many more scenarios than hand-written examples
- **Bug Discovery:** Finds edge cases developers might miss
- **Specification:** Properties serve as executable specifications
- **Confidence:** Higher confidence in correctness across input space

**Complement:** Still use unit tests for specific examples and integration scenarios.

## Security Considerations

### Git Credential Handling
- Never store git credentials in bridge.json
- Use system git credential manager
- Support SSH keys and personal access tokens
- Respect .gitignore for sensitive files

### Path Traversal Prevention
- Validate all file paths before operations
- Restrict operations to `.kiro/` directory
- Sanitize user-provided paths
- Use Path.resolve() to prevent escaping

### Contract Validation
- Validate contract schema before processing
- Limit contract file size (prevent DoS)
- Sanitize extracted data before storage
- Validate git URLs before cloning

### Temporary File Security
- Use secure temporary directories
- Clean up temp files even on failure
- Set appropriate file permissions
- Avoid storing sensitive data in temp files

## Performance Considerations

### Contract Extraction
- **Optimization:** Cache AST parsing results for unchanged files
- **Parallelization:** Extract from multiple files concurrently
- **Expected Performance:** < 1 second for typical repository (10-50 files)

### Git Operations
- **Optimization:** Shallow clone (depth=1) for contract sync
- **Caching:** Reuse cloned repos when possible
- **Expected Performance:** 2-5 seconds per dependency (first sync), < 1 second (subsequent syncs)

### Drift Detection
- **Optimization:** Index contracts for fast lookup
- **Parallelization:** Validate multiple files concurrently
- **Expected Performance:** < 2 seconds for typical consumer codebase

### Parallel Sync
- **Concurrency:** Use thread pool for parallel git operations
- **Limit:** Max 5 concurrent syncs to avoid resource exhaustion
- **Expected Performance:** O(slowest dependency) instead of O(sum of all dependencies)

## Future Enhancements

### Language Support
- TypeScript/JavaScript (Express, NestJS)
- Go (Gin, Echo)
- Java (Spring Boot)
- Rust (Actix, Rocket)

### Contract Types
- GraphQL schemas
- gRPC protobuf definitions
- WebSocket events
- Message queue contracts

### Swagger/OpenAPI Integration
- Import contracts from existing Swagger/OpenAPI specifications
- Sync from Swagger endpoints (e.g., `/api/docs/swagger.json`)
- Validate that Swagger spec is up-to-date before import
- Convert OpenAPI 3.0/3.1 specs to Bridge contract format
- Support both static Swagger files and live API endpoints
- Detect drift between code and Swagger documentation

### Advanced Features
- Semantic versioning for contracts
- Contract compatibility checking
- Automated migration suggestions
- Visual dependency graphs
- Real-time sync via webhooks
- Contract testing integration

### Tooling Integration
- GitHub Actions integration
- GitLab CI integration
- Pre-commit hooks
- IDE plugins
- Slack/Discord notifications

## Appendix: Contract Examples

### Example 1: Simple REST API Contract

```yaml
version: "1.0"
repo_id: "user-service"
role: "provider"
last_updated: "2024-11-27T15:00:00Z"

endpoints:
  - id: "list-users"
    path: "/users"
    method: "GET"
    status: "implemented"
    implemented_at: "2024-11-20T10:00:00Z"
    source_file: "backend/handlers/user.py"
    function_name: "list_users"
    
    parameters:
      - name: "page"
        type: "integer"
        required: false
        default: 1
      - name: "limit"
        type: "integer"
        required: false
        default: 20
    
    response:
      status: 200
      type: "array"
      items:
        type: "object"
        schema: "User"
    
    consumers: ["frontend", "mobile"]

  - id: "get-user"
    path: "/users/{id}"
    method: "GET"
    status: "implemented"
    implemented_at: "2024-11-20T10:00:00Z"
    source_file: "backend/handlers/user.py"
    function_name: "get_user"
    
    parameters:
      - name: "id"
        type: "integer"
        required: true
        location: "path"
    
    response:
      status: 200
      type: "object"
      schema: "User"
    
    consumers: ["frontend", "mobile", "admin-panel"]

models:
  User:
    fields:
      - name: "id"
        type: "integer"
      - name: "name"
        type: "string"
      - name: "email"
        type: "string"
      - name: "created_at"
        type: "string"
        format: "datetime"
```

### Example 2: Consumer Expectations

```yaml
version: "1.0"
repo_id: "frontend"
role: "consumer"
depends_on: "user-service"
last_synced: "2024-11-27T15:30:00Z"

expectations:
  - endpoint: "GET /users"
    status: "using"
    first_used: "2024-11-20T12:00:00Z"
    usage_locations:
      - "src/api/users.ts:15"
      - "src/components/UserList.tsx:23"
    
  - endpoint: "GET /users/{id}"
    status: "using"
    first_used: "2024-11-20T12:00:00Z"
    usage_locations:
      - "src/api/users.ts:28"
      - "src/components/UserProfile.tsx:10"
      - "src/components/UserSettings.tsx:45"

# Cached copy of provider contract for offline validation
provider_contract:
  version: "1.0"
  repo_id: "user-service"
  last_updated: "2024-11-27T15:00:00Z"
  endpoints:
    - id: "list-users"
      path: "/users"
      method: "GET"
      status: "implemented"
    - id: "get-user"
      path: "/users/{id}"
      method: "GET"
      status: "implemented"
```

### Example 3: Drift Report

```yaml
validation_timestamp: "2024-11-27T16:00:00Z"
repository: "frontend"
dependencies_checked: ["user-service", "auth-service"]

drift_issues:
  - type: "missing_endpoint"
    severity: "error"
    dependency: "user-service"
    endpoint: "GET /users/{id}/posts"
    method: "GET"
    location: "src/api/users.ts:42"
    message: "Endpoint not found in user-service contract"
    suggestion: "Either sync the latest contract or remove this API call"
  
  - type: "parameter_mismatch"
    severity: "warning"
    dependency: "auth-service"
    endpoint: "POST /auth/login"
    method: "POST"
    location: "src/api/auth.ts:18"
    message: "Parameter 'remember_me' not in contract"
    suggestion: "Check if parameter name is correct or update contract"

summary:
  total_api_calls: 15
  validated_calls: 13
  drift_issues: 2
  status: "drift_detected"
```
