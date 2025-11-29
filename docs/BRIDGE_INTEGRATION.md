# Bridge Integration with SpecSync Validation

This document describes how SpecSync Bridge integrates with the SpecSync validation workflow to provide comprehensive contract validation during commits.

## Overview

SpecSync Bridge extends SpecSync's validation capabilities by adding API contract drift detection. When you commit code, SpecSync now validates:

1. **Spec Alignment**: Code matches specifications
2. **Test Coverage**: Code has appropriate tests
3. **Documentation**: Public APIs are documented
4. **Contract Alignment**: API calls match provider contracts (NEW)

## How It Works

### Validation Flow

```
Git Commit
    ↓
Pre-Commit Hook
    ↓
SpecSync Validation Orchestrator
    ├─→ Drift Detection (spec-code alignment)
    ├─→ Test Coverage Analysis
    ├─→ Documentation Validation
    └─→ Bridge Contract Validation (NEW)
         ├─→ Load bridge configuration
         ├─→ Check each dependency
         ├─→ Find API calls in code
         ├─→ Validate against contracts
         └─→ Report drift issues
    ↓
Unified Validation Report
    ↓
Allow/Block Commit
```

### Bridge Validation Steps

1. **Configuration Check**: Verify `.kiro/settings/bridge.json` exists
2. **Dependency Discovery**: Load all configured dependencies
3. **Contract Loading**: Load cached contracts for each dependency
4. **API Call Extraction**: Find all API calls in consumer code using AST parsing
5. **Validation**: Check each API call against provider contracts
6. **Reporting**: Generate drift issues with suggestions

## Configuration

### Enabling Bridge Validation

Bridge validation is automatically enabled when:

```bash
# 1. Initialize bridge
specsync bridge init --role consumer

# 2. Add dependencies
specsync bridge add-dependency backend --git-url https://github.com/org/backend.git

# 3. Sync contracts
specsync bridge sync
```

Once configured, bridge validation runs automatically on every commit.

### Bridge Configuration File

`.kiro/settings/bridge.json`:

```json
{
  "bridge": {
    "enabled": true,
    "role": "consumer",
    "repo_id": "frontend",
    "dependencies": {
      "backend": {
        "type": "http-api",
        "sync_method": "git",
        "git_url": "https://github.com/org/backend.git",
        "contract_path": ".kiro/contracts/provided-api.yaml",
        "local_cache": ".kiro/contracts/backend-api.yaml",
        "sync_on_commit": true
      }
    }
  }
}
```

## Validation Output

### Success Case

When all API calls align with contracts:

```
Running SpecSync validation...

[*] Validating 5 staged file(s)...

======================================================================
  VALIDATION RESULTS
======================================================================

[OK] SUCCESS: All validations passed

   Message: All validations passed - commit can proceed

🌉 Bridge Contract Status:
   ✓ All API calls align with contracts (2 dependencies checked)

======================================================================
```

### Drift Detected

When contract drift is found:

```
Running SpecSync validation...

[*] Validating 5 staged file(s)...

======================================================================
  VALIDATION RESULTS
======================================================================

[FAIL] FAILURE: Validation issues detected

   Message: Validation failed: 3 contract drift issue(s) detected

🌉 Bridge Contract Drift:
   Total: 3
   Dependencies: backend, auth-service
   • [backend] GET /users/profile
     API call to GET /users/profile does not match any endpoint in contract
   • [backend] POST /users
     Endpoint path exists but method is PUT, not POST
   • [auth-service] GET /auth/verify
     API call to GET /auth/verify does not match any endpoint in contract

💡 Suggestions:
   1. [BRIDGE] [backend] API call to GET /users/profile does not match any endpoint in contract
      → Did you mean one of these endpoints? GET /users/{id}, GET /users/me
   2. [BRIDGE] [backend] Endpoint path exists but method is PUT, not POST
      → Update your API call to use PUT instead of POST
   3. [BRIDGE] [auth-service] API call to GET /auth/verify does not match any endpoint in contract
      → Either sync the latest contract or remove this API call

======================================================================
```

## Validation Reports

### Bridge Report Structure

The bridge validation report includes:

```python
{
    'enabled': True,              # Whether bridge is configured
    'has_issues': True,           # Whether drift was detected
    'total_issues': 3,            # Total number of drift issues
    'errors': 2,                  # Number of error-level issues
    'warnings': 1,                # Number of warning-level issues
    'issues': [                   # List of drift issues
        {
            'dependency': 'backend',
            'type': 'missing_endpoint',
            'severity': 'error',
            'endpoint': '/users/profile',
            'method': 'GET',
            'location': 'src/api/users.py:42',
            'message': 'API call to GET /users/profile does not match any endpoint in contract',
            'suggestion': 'Did you mean one of these endpoints? GET /users/{id}, GET /users/me'
        }
    ],
    'dependencies_checked': ['backend', 'auth-service'],
    'message': 'Found 3 contract drift issue(s)'
}
```

### Integration with Auto-Remediation

When auto-remediation is enabled, bridge issues are included in the generated task list:

```markdown
# Remediation Tasks

## Bridge Contract Drift

- [ ] Fix API call in src/api/users.py:42
  - Dependency: backend
  - Issue: API call to GET /users/profile does not match any endpoint in contract
  - Suggestion: Did you mean one of these endpoints? GET /users/{id}, GET /users/me
  - Priority: Medium

- [ ] Update API call method in src/api/users.py:58
  - Dependency: backend
  - Issue: Endpoint path exists but method is PUT, not POST
  - Suggestion: Update your API call to use PUT instead of POST
  - Priority: Medium
```

## Performance

Bridge validation is designed to be fast and non-intrusive:

- **Typical Runtime**: < 1 second for most projects
- **Caching**: Uses cached contracts (no network calls during validation)
- **Parallel Processing**: Checks multiple dependencies concurrently
- **AST Parsing**: Efficient code analysis using Python's AST module

### Performance Metrics

Example timing breakdown:

```
Validation Performance Summary:
----------------------------------------
  Drift Detection: 0.234s
  Test Coverage: 0.156s
  Documentation: 0.089s
  Bridge Validation: 0.421s
----------------------------------------
  Total: 0.900s
```

## API Call Detection

Bridge detects API calls from common Python HTTP libraries:

### Supported Libraries

- **requests**: `requests.get()`, `requests.post()`, etc.
- **httpx**: `httpx.get()`, `httpx.post()`, `client.get()`, etc.
- **aiohttp**: `session.get()`, `session.post()`, etc.

### Detection Examples

```python
# Detected
response = requests.get("http://api.example.com/users")
response = httpx.post("/users", json=data)
response = await session.get(f"/users/{user_id}")

# Not detected (not HTTP library calls)
result = get_user(user_id)
data = fetch_data()
```

## Troubleshooting

### Bridge Validation Not Running

**Symptom**: No bridge validation output in commit validation

**Solutions**:
1. Check if bridge is initialized: `ls .kiro/settings/bridge.json`
2. Verify dependencies are configured: `specsync bridge status`
3. Ensure contracts are synced: `specsync bridge sync`

### False Positives

**Symptom**: Valid API calls reported as drift

**Solutions**:
1. Sync latest contracts: `specsync bridge sync`
2. Check API call syntax (method, path)
3. Verify contract extraction on provider side
4. Check for path parameter mismatches

### Validation Too Slow

**Symptom**: Bridge validation takes > 2 seconds

**Solutions**:
1. Check network connectivity (affects git operations)
2. Reduce number of dependencies
3. Use cached contracts for offline work
4. Check for large codebases (many files to scan)

### Contract Not Found

**Symptom**: "Contract file not found" error

**Solutions**:
1. Run sync: `specsync bridge sync <dependency>`
2. Check contract path in configuration
3. Verify provider has published contract
4. Check git URL is accessible

## Best Practices

### For Consumers

1. **Sync Regularly**: Run `specsync bridge sync` daily or before major work
2. **Validate Before Committing**: Run `specsync bridge validate` to catch issues early
3. **Monitor Status**: Use `specsync bridge status` to track dependency health
4. **Fix Drift Promptly**: Address drift issues as they arise

### For Providers

1. **Extract Contracts**: Run contract extraction after API changes
2. **Commit Contracts**: Include contract files in version control
3. **Document Changes**: Use clear commit messages for contract changes
4. **Notify Consumers**: Alert consumers of breaking changes

### For Teams

1. **Establish Sync Schedule**: Agree on how often to sync contracts
2. **Review Drift Together**: Discuss drift issues in code reviews
3. **Coordinate Changes**: Plan breaking changes across teams
4. **Share Contract Updates**: Notify teams when contracts change

## Advanced Usage

### Manual Validation

Run bridge validation without committing:

```bash
# Validate all dependencies
specsync bridge validate

# Check specific dependency
specsync bridge sync backend
specsync bridge validate
```

### Programmatic Access

Use bridge validation in scripts:

```python
from backend.validator import ValidationOrchestrator

orchestrator = ValidationOrchestrator()
git_context = {
    'branch': 'main',
    'stagedFiles': ['src/api/users.py'],
    'diff': '...'
}

result = orchestrator.validate(git_context)

if result['bridge_report'] and result['bridge_report']['has_issues']:
    print(f"Found {result['bridge_report']['total_issues']} drift issues")
    for issue in result['bridge_report']['issues']:
        print(f"  - {issue['dependency']}: {issue['message']}")
```

### Custom Validation Rules

Extend bridge validation with custom rules:

```python
from backend.bridge_drift_detector import BridgeDriftDetector

class CustomDriftDetector(BridgeDriftDetector):
    def _check_endpoint_exists(self, api_call, contract):
        # Add custom validation logic
        issue = super()._check_endpoint_exists(api_call, contract)
        
        # Add custom checks
        if api_call.path.startswith('/internal/'):
            # Custom rule: internal endpoints should not be called
            return DriftIssue(
                type='internal_endpoint_call',
                severity='warning',
                endpoint=api_call.path,
                method=api_call.method,
                location=f"{api_call.file_path}:{api_call.line_number}",
                message='Calling internal endpoint',
                suggestion='Use public API instead'
            )
        
        return issue
```

## Future Enhancements

Planned improvements to bridge validation:

1. **Language Support**: TypeScript, Go, Java, Rust
2. **Protocol Support**: GraphQL, gRPC, WebSocket
3. **Smart Suggestions**: ML-based endpoint matching
4. **Performance Optimization**: Incremental validation
5. **Visual Reports**: HTML/PDF validation reports

## Related Documentation

- [Bridge CLI Documentation](BRIDGE_CLI.md)
- [Bridge Design Document](../.kiro/specs/bridge/design.md)
- [SpecSync Validation Workflow](workflow_diagram.md)
- [Auto-Remediation Guide](../backend/auto_remediation.py)

