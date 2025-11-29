# Usage Tracking and Breaking Change Detection

This document describes the usage tracking and breaking change detection features in SpecSync Bridge.

## Overview

SpecSync Bridge now includes two powerful features to help manage API contracts across repositories:

1. **Usage Tracking**: Automatically records which endpoints consumers are using
2. **Breaking Change Detection**: Warns providers when changes might break consumer code

## Usage Tracking

### How It Works

When a consumer syncs a provider's contract, Bridge automatically:

1. Scans the consumer's codebase for API calls
2. Matches API calls to endpoints in the provider's contract
3. Records usage locations (file and line number)
4. Stores expectations in `.kiro/contracts/{dependency}-expectations.yaml`

### Example

After syncing the backend contract, a consumer's expectations file might look like:

```yaml
dependency: backend
last_updated: "2024-11-27T15:30:00Z"
expectations:
  - endpoint: "GET /users"
    status: "using"
    usage_locations:
      - "src/api/users.ts:15"
      - "src/components/UserList.tsx:23"
  
  - endpoint: "GET /users/{id}"
    status: "using"
    usage_locations:
      - "src/api/users.ts:28"
      - "src/components/UserProfile.tsx:10"
```

### Benefits

- **Automatic**: No manual tracking required
- **Accurate**: Based on actual code analysis
- **Detailed**: Includes exact file locations
- **Offline**: Works with cached contracts

## Breaking Change Detection

### How It Works

Providers can detect breaking changes by comparing two contract versions:

```python
from backend.bridge_breaking_changes import (
    BreakingChangeDetector,
    format_breaking_changes
)
from backend.bridge_models import load_contract_from_yaml

# Load contracts
old_contract = load_contract_from_yaml(".kiro/contracts/provided-api-old.yaml")
new_contract = load_contract_from_yaml(".kiro/contracts/provided-api.yaml")

# Detect changes
detector = BreakingChangeDetector()
changes = detector.detect_breaking_changes(old_contract, new_contract)

# Display results
print(format_breaking_changes(changes))
```

### Change Types

#### 1. Endpoint Removed (Error)

When an endpoint with consumers is removed:

```
🚨 ERROR: endpoint_removed
  DELETE /users/{id}
  Affected Consumers: admin-panel
  Suggestion: Consider deprecating instead of removing, or notify consumers
```

#### 2. Endpoint Modified (Warning)

When an endpoint with consumers is modified:

```
⚠️  WARNING: endpoint_modified
  GET /users/{id}
  Affected Consumers: frontend, mobile
  Suggestion: Verify changes are backward compatible, or notify consumers
```

#### 3. Unused Endpoint (Info)

When an endpoint has no consumers:

```
ℹ️  INFO: unused_endpoint
  GET /admin/stats
  Suggestion: This endpoint may be safe to remove or deprecate
```

### Integration with Workflow

Breaking change detection can be integrated into your CI/CD pipeline:

```bash
# Before deploying changes
python -m backend.bridge_breaking_changes \
  --old .kiro/contracts/provided-api-old.yaml \
  --new .kiro/contracts/provided-api.yaml
```

If breaking changes are detected, the pipeline can:
- Block deployment
- Send notifications to affected teams
- Create tickets for coordination
- Generate migration guides

## Consumer Expectations Recording

### Automatic Recording

Consumer expectations are automatically recorded during sync:

```python
from backend.bridge_sync import SyncEngine
from backend.bridge_models import BridgeConfig

config = BridgeConfig()
config.load()

engine = SyncEngine(config)
result = engine.sync_dependency("backend")

# Expectations are automatically recorded in:
# .kiro/contracts/backend-expectations.yaml
```

### Manual Recording

You can also manually record expectations:

```python
from backend.bridge_breaking_changes import BreakingChangeDetector

detector = BreakingChangeDetector()

# Load expectations from consumer code
expectations = detector.load_consumer_expectations("backend")

# Update provider contract with consumer info
detector.update_contract_with_consumers(
    contract_path=".kiro/contracts/provided-api.yaml",
    consumer_name="frontend",
    expectations=expectations
)
```

## Best Practices

### For Providers

1. **Check for breaking changes before deploying**
   ```bash
   python -m backend.bridge_breaking_changes --check
   ```

2. **Review unused endpoints regularly**
   - Endpoints with no consumers may be safe to remove
   - Consider deprecation before removal

3. **Communicate changes to consumers**
   - Use the affected consumers list to notify teams
   - Provide migration guides for breaking changes

4. **Use semantic versioning**
   - Major version bump for breaking changes
   - Minor version bump for new features
   - Patch version bump for bug fixes

### For Consumers

1. **Sync contracts regularly**
   ```bash
   specsync bridge sync
   ```

2. **Run drift detection before deploying**
   ```bash
   specsync bridge validate
   ```

3. **Keep expectations up to date**
   - Expectations are automatically updated during sync
   - Review expectations file periodically

4. **Monitor provider changes**
   - Subscribe to provider contract updates
   - Test against new contracts before they're deployed

## Example Workflow

### Provider Workflow

1. Developer makes changes to API
2. Contract is extracted from code
3. Breaking change detection runs
4. If breaking changes detected:
   - Review affected consumers
   - Coordinate with consumer teams
   - Plan migration strategy
5. Deploy changes
6. Commit updated contract

### Consumer Workflow

1. Sync provider contract
2. Expectations are automatically recorded
3. Drift detection runs
4. If drift detected:
   - Review drift issues
   - Update code to match contract
   - Re-run validation
5. Deploy changes

## API Reference

### BreakingChangeDetector

```python
class BreakingChangeDetector:
    def __init__(self, repo_root: str = ".")
    
    def detect_breaking_changes(
        self, 
        old_contract: Contract, 
        new_contract: Contract
    ) -> List[BreakingChange]
    
    def load_consumer_expectations(
        self, 
        dependency_name: str
    ) -> Dict[str, List[str]]
    
    def update_contract_with_consumers(
        self, 
        contract_path: str,
        consumer_name: str,
        expectations: Dict[str, List[str]]
    ) -> None
```

### BreakingChange

```python
@dataclass
class BreakingChange:
    type: str  # "endpoint_removed", "endpoint_modified", "unused_endpoint"
    severity: str  # "error", "warning", "info"
    endpoint: str
    method: str
    message: str
    affected_consumers: List[str]
    suggestion: str
```

## Troubleshooting

### Expectations Not Recording

**Problem**: Expectations file is empty or missing

**Solutions**:
- Ensure API calls are in supported format (requests, httpx, aiohttp)
- Check that contract sync completed successfully
- Verify file patterns include your code files

### False Positives in Breaking Changes

**Problem**: Changes flagged as breaking but aren't

**Solutions**:
- Review the specific change details
- Check if consumers list is accurate
- Consider if change is truly backward compatible

### Missing Consumer Information

**Problem**: Contract doesn't show consumers

**Solutions**:
- Ensure consumers have synced the contract
- Check that expectations files exist
- Verify consumer expectations are being recorded

## Future Enhancements

- Real-time notifications for breaking changes
- Automated migration guide generation
- Visual dependency graphs
- Contract versioning and compatibility checking
- Integration with API gateways
