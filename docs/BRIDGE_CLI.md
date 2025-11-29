# SpecSync Bridge CLI

Command-line interface for managing cross-repository API contract synchronization.

## Overview

SpecSync Bridge enables automatic detection of contract changes and keeps all services aligned without requiring a shared parent folder. It operates on a provider-consumer model where:

- **Providers** extract and publish API contracts from their codebase
- **Consumers** sync and cache contracts from their dependencies
- **Validation** detects drift between what consumers expect and what providers offer

## Installation

The Bridge CLI is included with SpecSync. No additional installation required.

## Quick Start

### For Consumers

1. **Initialize Bridge**
   ```bash
   python bridge.py init --role consumer
   ```

2. **Add Dependencies**
   ```bash
   python bridge.py add-dependency backend \
     --git-url https://github.com/org/backend.git
   ```

3. **Sync Contracts**
   ```bash
   python bridge.py sync
   ```

4. **Validate Your Code**
   ```bash
   python bridge.py validate
   ```

### For Providers

1. **Initialize Bridge**
   ```bash
   python bridge.py init --role provider
   ```

2. **Extract Your Contract**
   ```bash
   python -m backend.bridge_contract_extractor
   ```

3. **Commit the Contract**
   ```bash
   git add .kiro/contracts/provided-api.yaml
   git commit -m "Add API contract"
   git push
   ```

## Commands

### `init`

Initialize bridge configuration in your repository.

**Usage:**
```bash
python bridge.py init [--role ROLE]
```

**Options:**
- `--role`: Role of this repository (choices: `consumer`, `provider`, `both`; default: `consumer`)

**What it does:**
- Creates `.kiro/settings/bridge.json` configuration file
- Creates `.kiro/contracts/` directory for contract storage
- Generates default configuration based on role

**Example:**
```bash
# Initialize as a consumer
python bridge.py init --role consumer

# Initialize as a provider
python bridge.py init --role provider

# Initialize as both (microservice that provides and consumes APIs)
python bridge.py init --role both
```

---

### `add-dependency`

Add a new dependency to your configuration.

**Usage:**
```bash
python bridge.py add-dependency NAME --git-url URL [--contract-path PATH]
```

**Arguments:**
- `NAME`: Name of the dependency (e.g., `backend`, `auth-service`)

**Options:**
- `--git-url`: Git repository URL (required)
- `--contract-path`: Path to contract file in dependency repo (default: `.kiro/contracts/provided-api.yaml`)

**What it does:**
- Adds dependency to `.kiro/settings/bridge.json`
- Validates configuration
- Prepares local cache path

**Example:**
```bash
# Add backend dependency
python bridge.py add-dependency backend \
  --git-url https://github.com/org/backend.git

# Add dependency with custom contract path
python bridge.py add-dependency auth \
  --git-url https://github.com/org/auth-service.git \
  --contract-path contracts/api.yaml
```

---

### `sync`

Sync contracts from dependencies.

**Usage:**
```bash
python bridge.py sync [DEPENDENCY]
```

**Arguments:**
- `DEPENDENCY`: Name of specific dependency to sync (optional; omit to sync all)

**What it does:**
- Clones/pulls dependency repositories
- Copies contract files to local cache
- Detects changes since last sync
- Records consumer expectations
- Displays sync results

**Features:**
- **Parallel Sync**: Syncs multiple dependencies concurrently (up to 5 at once)
- **Offline Fallback**: Uses cached contracts if sync fails
- **Change Detection**: Shows what changed since last sync

**Example:**
```bash
# Sync all dependencies
python bridge.py sync

# Sync specific dependency
python bridge.py sync backend

# Output example:
# Syncing all dependencies...
#
#   → Syncing backend...
#   ✓ Completed backend
#   → Syncing auth...
#   ✓ Completed auth
#
# Sync Results:
#
# ✓ backend
#   Endpoints: 15
#   Cached: .kiro/contracts/backend-api.yaml
#   Changes:
#     - Added: POST /users
#     - Modified: GET /users/{id}
#
# ✓ auth
#   Endpoints: 8
#   Cached: .kiro/contracts/auth-api.yaml
#
# Summary:
#   Success: 2
#   Failed: 0
```

---

### `validate`

Validate API calls against cached contracts.

**Usage:**
```bash
python bridge.py validate
```

**What it does:**
- Scans your code for API calls
- Validates calls against cached contracts
- Detects drift (missing endpoints, parameter mismatches, etc.)
- Displays detailed drift reports with suggestions

**Drift Types Detected:**
- **Missing Endpoint**: API call to endpoint not in contract
- **Parameter Mismatch**: Wrong parameters passed to endpoint
- **Method Mismatch**: Wrong HTTP method used
- **Response Mismatch**: Expected response doesn't match contract

**Example:**
```bash
python bridge.py validate

# Output example (with drift):
# Validating API calls against contracts...
#
# Dependency: backend
#   ✗ Found 2 drift issue(s)
#     Errors: 2, Warnings: 0
#
#   1. [ERROR] missing_endpoint
#      Endpoint: GET /users/{id}/posts
#      Location: src/api/users.py:42
#      Message: API call to GET /users/{id}/posts does not match any endpoint in contract
#      Suggestion: Either sync the latest contract or remove this API call
#
#   2. [ERROR] parameter_mismatch
#      Endpoint: POST /auth/login
#      Location: src/api/auth.py:18
#      Message: Parameter 'remember_me' not in contract
#      Suggestion: Check if parameter name is correct or update contract
#
# ============================================================
# Validation Summary
# ============================================================
# ✗ DRIFT DETECTED
#   Total Issues: 2
#   Errors: 2
#   Warnings: 0
#
# Recommendation:
#   1. Sync contracts: python bridge.py sync
#   2. Fix API calls to match contracts
#   3. Or update provider contracts if changes are intentional

# Output example (no drift):
# Validating API calls against contracts...
#
# Dependency: backend
#   ✓ All API calls align with contract
#
# Dependency: auth
#   ✓ All API calls align with contract
#
# ============================================================
# Validation Summary
# ============================================================
# ✓ SUCCESS - All API calls align with contracts
```

---

### `status`

Display status of all dependencies.

**Usage:**
```bash
python bridge.py status
```

**What it does:**
- Shows configuration details
- Lists all dependencies
- Displays sync status for each dependency
- Shows endpoint counts
- Checks drift status

**Example:**
```bash
python bridge.py status

# Output example:
# SpecSync Bridge Status
#
# Configuration:
#   Role: consumer
#   Config: .kiro/settings/bridge.json
#
# Dependencies (2):
#
# backend
#   Git URL: https://github.com/org/backend.git
#   Contract Path: .kiro/contracts/provided-api.yaml
#   Local Cache: .kiro/contracts/backend-api.yaml
#   ✓ Synced
#   Endpoints: 15
#   Last Updated: 2 hours ago
#   Drift: ✓ No drift
#
# auth
#   Git URL: https://github.com/org/auth-service.git
#   Contract Path: .kiro/contracts/provided-api.yaml
#   Local Cache: .kiro/contracts/auth-api.yaml
#   ⚠  Not synced
#   Run: python bridge.py sync auth
#
# Overall Status:
#   ⚠  1 dependencies need syncing
```

## Configuration

Bridge configuration is stored in `.kiro/settings/bridge.json`:

```json
{
  "bridge": {
    "enabled": true,
    "role": "consumer",
    "repo_id": "",
    "provides": {},
    "dependencies": {
      "backend": {
        "name": "backend",
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

## Contract Format

Contracts are stored as YAML files in `.kiro/contracts/`:

```yaml
version: "1.0"
repo_id: "backend"
role: "provider"
last_updated: "2024-11-27T15:00:00Z"

endpoints:
  - id: "get-user"
    path: "/users/{id}"
    method: "GET"
    status: "implemented"
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

## Workflows

### Consumer Workflow

1. **Initial Setup**
   ```bash
   python bridge.py init --role consumer
   python bridge.py add-dependency backend --git-url <url>
   python bridge.py sync
   ```

2. **Daily Development**
   ```bash
   # Before starting work
   python bridge.py sync
   
   # Write code that calls APIs
   
   # Before committing
   python bridge.py validate
   ```

3. **When Validation Fails**
   ```bash
   # Option 1: Sync latest contracts
   python bridge.py sync
   python bridge.py validate
   
   # Option 2: Fix your code to match contracts
   # Edit your code
   python bridge.py validate
   ```

### Provider Workflow

1. **Initial Setup**
   ```bash
   python bridge.py init --role provider
   python -m backend.bridge_contract_extractor
   git add .kiro/contracts/provided-api.yaml
   git commit -m "Add API contract"
   ```

2. **After API Changes**
   ```bash
   # Extract updated contract
   python -m backend.bridge_contract_extractor
   
   # Check for breaking changes
   git diff .kiro/contracts/provided-api.yaml
   
   # Commit changes
   git add .kiro/contracts/provided-api.yaml
   git commit -m "Update API contract"
   git push
   ```

### Microservice Workflow (Both Provider and Consumer)

1. **Initial Setup**
   ```bash
   python bridge.py init --role both
   
   # Add dependencies you consume
   python bridge.py add-dependency auth --git-url <url>
   
   # Extract contract you provide
   python -m backend.bridge_contract_extractor
   ```

2. **Daily Development**
   ```bash
   # Sync dependencies
   python bridge.py sync
   
   # Validate your API calls
   python bridge.py validate
   
   # After making API changes
   python -m backend.bridge_contract_extractor
   git add .kiro/contracts/provided-api.yaml
   git commit -m "Update API contract"
   ```

## CI/CD Integration

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash

# Sync contracts
python bridge.py sync

# Validate API calls
if ! python bridge.py validate; then
    echo "❌ API validation failed. Fix drift before committing."
    exit 1
fi

echo "✅ API validation passed"
```

### GitHub Actions

Add to `.github/workflows/bridge.yml`:

```yaml
name: Bridge Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Sync contracts
        run: python bridge.py sync
      
      - name: Validate API calls
        run: python bridge.py validate
```

## Troubleshooting

### "Bridge not initialized"

**Problem:** Running commands before initialization.

**Solution:**
```bash
python bridge.py init --role consumer
```

---

### "Dependency not found in configuration"

**Problem:** Trying to sync a dependency that hasn't been added.

**Solution:**
```bash
python bridge.py add-dependency <name> --git-url <url>
```

---

### "Contract file not found"

**Problem:** Contract hasn't been synced yet.

**Solution:**
```bash
python bridge.py sync
```

---

### "Git operation failed"

**Problem:** Network issues or invalid git URL.

**Solutions:**
- Check network connection
- Verify git URL is correct
- Check git credentials
- Use cached contract (Bridge will automatically fall back)

---

### Drift detected but code is correct

**Problem:** Contract is outdated.

**Solution:**
```bash
# Sync latest contract
python bridge.py sync

# Validate again
python bridge.py validate
```

---

### False positive drift detection

**Problem:** Bridge detects drift for valid API calls.

**Possible causes:**
- Dynamic URL construction not recognized
- API call pattern not supported
- Contract format issue

**Solution:**
- Check if API call uses supported patterns (requests, httpx, aiohttp)
- Verify contract format is correct
- Report issue if pattern should be supported

## Advanced Usage

### Custom Contract Paths

If your dependency stores contracts in a non-standard location:

```bash
python bridge.py add-dependency backend \
  --git-url https://github.com/org/backend.git \
  --contract-path docs/api/contract.yaml
```

### Multiple Environments

Use different configurations for different environments:

```bash
# Development
python bridge.py init --role consumer
python bridge.py add-dependency backend-dev --git-url <dev-url>

# Production
python bridge.py add-dependency backend-prod --git-url <prod-url>

# Sync specific environment
python bridge.py sync backend-dev
```

### Offline Development

Bridge supports offline development using cached contracts:

```bash
# Sync when online
python bridge.py sync

# Work offline - validation uses cached contracts
python bridge.py validate

# Bridge will warn if contracts are stale
```

## Best Practices

1. **Sync Regularly**: Run `python bridge.py sync` at the start of each day
2. **Validate Before Committing**: Always run `python bridge.py validate` before committing
3. **Keep Contracts in Git**: Commit contract files so team members have them
4. **Use CI/CD**: Automate validation in your CI/CD pipeline
5. **Document Breaking Changes**: When making breaking changes, communicate with consumers
6. **Version Your APIs**: Use versioned endpoints for major changes
7. **Monitor Drift**: Check `python bridge.py status` regularly

## Support

For issues or questions:
- Check the [main documentation](../README.md)
- Review [design document](BRIDGE_DESIGN.md)
- Open an issue on GitHub

## Related Documentation

- [Bridge Design](BRIDGE_DESIGN.md) - Architecture and design decisions
- [Parallel Sync](PARALLEL_SYNC.md) - Details on parallel synchronization
- [Usage Tracking](USAGE_TRACKING.md) - Consumer expectation tracking
- [Main README](../README.md) - SpecSync overview
