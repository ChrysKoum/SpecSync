# Bridge Validation - Quick Start Guide

## What is Bridge Validation?

Bridge validation automatically checks that your API calls match provider contracts during commits. It's integrated with SpecSync's pre-commit validation workflow.

## Setup (One-Time)

### 1. Initialize Bridge

```bash
specsync bridge init --role consumer
```

This creates `.kiro/settings/bridge.json` and `.kiro/contracts/` directory.

### 2. Add Dependencies

```bash
specsync bridge add-dependency backend --git-url https://github.com/org/backend.git
specsync bridge add-dependency auth --git-url https://github.com/org/auth-service.git
```

### 3. Sync Contracts

```bash
specsync bridge sync
```

This fetches and caches contracts from your dependencies.

## Daily Usage

### Before Committing

```bash
# Sync latest contracts (recommended daily)
specsync bridge sync

# Validate your code
specsync bridge validate
```

### During Commit

Bridge validation runs automatically:

```bash
git add .
git commit -m "Add user profile feature"
```

You'll see:

```
Running SpecSync validation...

🌉 Bridge Contract Status:
   ✓ All API calls align with contracts (2 dependencies checked)

[OK] SUCCESS: All validations passed
```

### If Drift is Detected

```
🌉 Bridge Contract Drift:
   Total: 1
   • [backend] GET /users/profile
     API call does not match any endpoint in contract

💡 Suggestion:
   Did you mean: GET /users/{id} or GET /users/me?
   Or sync latest contract: specsync bridge sync backend
```

**Fix it:**

1. Update your API call to match the contract
2. Or sync the latest contract if it's been updated
3. Or coordinate with the provider team

## Common Commands

```bash
# Check status of all dependencies
specsync bridge status

# Sync specific dependency
specsync bridge sync backend

# Sync all dependencies
specsync bridge sync

# Validate without committing
specsync bridge validate

# View bridge configuration
cat .kiro/settings/bridge.json
```

## Understanding Output

### ✓ Success

```
🌉 Bridge Contract Status:
   ✓ All API calls align with contracts (2 dependencies checked)
```

All your API calls match provider contracts. Commit can proceed.

### ✗ Drift Detected

```
🌉 Bridge Contract Drift:
   Total: 3
   Dependencies: backend, auth-service
   • [backend] GET /users/profile - endpoint not found
   • [backend] POST /users - wrong method (should be PUT)
   • [auth] GET /verify - endpoint not found
```

Some API calls don't match contracts. Fix before committing.

## Troubleshooting

### "Contract file not found"

**Solution**: Run `specsync bridge sync <dependency>`

### "Bridge not configured"

**Solution**: Run `specsync bridge init`

### Too many false positives

**Solution**: Sync latest contracts with `specsync bridge sync`

### Validation too slow

**Solution**: Check network connectivity or use cached contracts offline

## Best Practices

1. **Sync Daily**: Run `specsync bridge sync` at the start of each day
2. **Validate Before Committing**: Run `specsync bridge validate` before `git commit`
3. **Monitor Status**: Use `specsync bridge status` to track dependency health
4. **Fix Drift Promptly**: Address drift issues as they arise

## Integration with SpecSync

Bridge validation is part of SpecSync's comprehensive validation:

1. **Spec Alignment** - Code matches specifications
2. **Test Coverage** - Code has appropriate tests
3. **Bridge Contracts** - API calls match provider contracts ← NEW
4. **Documentation** - Public APIs are documented

All checks run automatically on commit.

## Disabling Bridge Validation

To temporarily disable:

```bash
# Option 1: Remove configuration
rm .kiro/settings/bridge.json

# Option 2: Remove contracts
rm .kiro/contracts/*-api.yaml
```

Bridge validation will skip if no configuration is found.

## Getting Help

- Full documentation: [docs/BRIDGE_INTEGRATION.md](BRIDGE_INTEGRATION.md)
- CLI reference: [docs/BRIDGE_CLI.md](BRIDGE_CLI.md)
- Design document: [.kiro/specs/bridge/design.md](../.kiro/specs/bridge/design.md)

## Example Workflow

```bash
# Morning: Sync contracts
specsync bridge sync

# Work on feature
vim src/api/users.py

# Before committing: Validate
specsync bridge validate

# If validation passes: Commit
git add .
git commit -m "Add user profile endpoint"

# Bridge validation runs automatically
# ✓ All validations passed
```

## What Gets Validated?

Bridge detects API calls from:

- **requests**: `requests.get()`, `requests.post()`, etc.
- **httpx**: `httpx.get()`, `client.post()`, etc.
- **aiohttp**: `session.get()`, `session.post()`, etc.

Example:

```python
# These are validated
response = requests.get("/users")
response = httpx.post("/users", json=data)
response = await session.get(f"/users/{id}")

# These are not (not HTTP library calls)
result = get_user(id)
data = fetch_data()
```

## Next Steps

1. Set up bridge: `specsync bridge init`
2. Add your dependencies
3. Sync contracts
4. Start committing with automatic validation!

For more details, see [BRIDGE_INTEGRATION.md](BRIDGE_INTEGRATION.md).

