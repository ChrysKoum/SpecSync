# SpecSync Bridge Components

This directory contains the core components for SpecSync Bridge, a decentralized contract synchronization system.

## Directory Structure

```
backend/
├── bridge_models.py              # Core data models and schemas
├── bridge_contract_extractor.py  # Contract extraction from code
├── bridge_sync.py                # Sync engine (to be implemented)
└── bridge_README.md              # This file

.kiro/
├── contracts/                    # Contract cache directory
│   ├── provided-api.yaml        # Contract this repo provides (if provider)
│   └── <dep>-api.yaml           # Cached contracts from dependencies
└── settings/
    └── bridge.json              # Bridge configuration
```

## Core Data Models

### Contract Schema Classes

- **Endpoint**: Represents an API endpoint with path, method, parameters, and response
- **Model**: Represents a data model with fields
- **Contract**: Complete API contract with endpoints and models

### Configuration Models

- **Dependency**: Configuration for a single dependency
- **BridgeConfig**: Main bridge configuration with dependencies
- **SyncResult**: Result of a sync operation
- **DriftIssue**: Represents a drift issue between consumer and provider

## Usage Examples

### Creating a Contract

```python
from backend.bridge_models import Contract, Endpoint

endpoint = Endpoint(
    id="get-users",
    path="/users",
    method="GET",
    status="implemented"
)

contract = Contract(
    version="1.0",
    repo_id="backend",
    role="provider",
    last_updated="2024-11-27T10:00:00Z",
    endpoints=[endpoint]
)

# Save to YAML
contract.save_to_yaml(".kiro/contracts/provided-api.yaml")
```

### Managing Configuration

```python
from backend.bridge_models import BridgeConfig, Dependency

# Create default config
config = BridgeConfig.create_default(role="consumer")

# Add a dependency
dep = Dependency(
    name="backend",
    type="http-api",
    sync_method="git",
    git_url="https://github.com/org/backend.git",
    contract_path=".kiro/contracts/provided-api.yaml",
    local_cache=".kiro/contracts/backend-api.yaml"
)

config.add_dependency("backend", dep)

# Validate configuration
errors = config.validate()
if errors:
    print("Configuration errors:", errors)
```

### Loading Contracts

```python
from backend.bridge_models import Contract

# Load from YAML
contract = Contract.load_from_yaml(".kiro/contracts/backend-api.yaml")

print(f"Contract has {len(contract.endpoints)} endpoints")
for endpoint in contract.endpoints:
    print(f"  {endpoint.method} {endpoint.path}")
```

## YAML Serialization

All contract and configuration data can be serialized to/from YAML:

- Contracts use YAML format for human readability and git-friendly diffs
- Configuration uses JSON format for consistency with other SpecSync settings
- All models provide `to_dict()` and `from_dict()` methods for serialization

## Validation

The `BridgeConfig.validate()` method checks:
- Required fields are present
- Role is valid (consumer, provider, or both)
- Dependencies have required fields based on sync method
- Git dependencies have git_url specified

## Next Steps

The following components need to be implemented:
1. Sync Engine (bridge_sync.py) - Git-based contract synchronization
2. Drift Detector - Detect mismatches between consumer and provider
3. CLI Interface - Command-line tools for bridge operations


## Integration with SpecSync Validation Workflow

Bridge is fully integrated with the SpecSync pre-commit validation workflow. When you commit code, SpecSync automatically runs bridge validation alongside standard validation checks.

### How It Works

1. **Pre-Commit Hook Triggers**: When you run `git commit`, the SpecSync pre-commit hook activates
2. **Standard Validation Runs**: SpecSync checks spec-code-test-doc alignment
3. **Bridge Validation Runs**: Bridge checks API contract drift against all configured dependencies
4. **Unified Report**: All issues are reported together in a single validation report

### What Bridge Validates

Bridge validation checks:
- **API Call Alignment**: All API calls in your code match endpoints in provider contracts
- **Method Matching**: HTTP methods (GET, POST, etc.) match between calls and contracts
- **Path Matching**: Endpoint paths match, including path parameters
- **Contract Availability**: All configured dependencies have cached contracts

### Validation Output

When bridge validation runs, you'll see:

```
🌉 Bridge Contract Status:
   ✓ All API calls align with contracts (2 dependencies checked)
```

Or if there are issues:

```
🌉 Bridge Contract Drift:
   Total: 3
   Dependencies: backend, auth-service
   • [backend] GET /users/profile
     API call to GET /users/profile does not match any endpoint in contract
   • [auth-service] POST /login
     Endpoint path exists but method is GET, not POST
```

### Configuration

Bridge validation is automatically enabled when:
1. Bridge is initialized (`specsync bridge init`)
2. Dependencies are configured in `.kiro/settings/bridge.json`
3. Contracts are synced (`specsync bridge sync`)

No additional configuration is needed - bridge validation integrates seamlessly with SpecSync.

### Disabling Bridge Validation

If you want to temporarily disable bridge validation:

1. **Option 1**: Remove or rename `.kiro/settings/bridge.json`
2. **Option 2**: Set all dependencies to have empty contract caches

Bridge validation will skip if no configuration is found, allowing commits to proceed normally.

### Bridge Validation Priority

Bridge validation follows SpecSync's validation priority model:

1. **Spec Alignment** (Highest Priority) - Code must match specs
2. **Test Coverage** (Medium Priority) - Code must have tests
3. **Documentation** (Lower Priority) - Public APIs must be documented
4. **Bridge Contracts** (Medium Priority) - API calls must match provider contracts

This means bridge issues are treated with medium priority - important but not blocking if other critical issues exist.

### Suggestions and Auto-Remediation

When bridge drift is detected, SpecSync provides:

- **Specific Suggestions**: Each drift issue includes a suggestion for how to fix it
- **Auto-Remediation Tasks**: If auto-remediation is enabled, bridge issues are included in the generated task list
- **Dependency Context**: Issues are grouped by dependency for easy understanding

Example suggestion:
```
💡 Suggestion:
   [backend] API call to GET /users/profile does not match any endpoint in contract
   → Did you mean one of these endpoints? GET /users/{id}, GET /users/me
   → Or sync the latest contract: specsync bridge sync backend
```

### Manual Bridge Validation

You can also run bridge validation manually at any time:

```bash
# Validate all dependencies
specsync bridge validate

# Check status of all dependencies
specsync bridge status

# Sync contracts before validating
specsync bridge sync
specsync bridge validate
```

### Best Practices

1. **Sync Regularly**: Run `specsync bridge sync` regularly to keep contracts up-to-date
2. **Check Before Committing**: Run `specsync bridge validate` before committing to catch issues early
3. **Monitor Dependencies**: Use `specsync bridge status` to see which dependencies need syncing
4. **Fix Drift Promptly**: Address bridge drift issues as they arise to avoid accumulation

### Troubleshooting

**Bridge validation not running?**
- Check that `.kiro/settings/bridge.json` exists
- Verify dependencies are configured
- Ensure contracts are synced

**Too many false positives?**
- Sync contracts to get latest versions: `specsync bridge sync`
- Check that API calls use correct paths and methods
- Verify contract extraction is working on provider side

**Validation too slow?**
- Bridge validation typically adds < 1 second to validation time
- If slower, check network connectivity for git operations
- Consider using cached contracts for offline work

