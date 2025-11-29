# SpecSync Bridge Contracts Directory

This directory stores API contracts for the SpecSync Bridge system.

## Purpose

The `.kiro/contracts/` directory serves as the local cache for API contracts:

- **Provider repositories** store their own contract in `provided-api.yaml`
- **Consumer repositories** cache contracts from dependencies (e.g., `backend-api.yaml`, `auth-api.yaml`)

## Contract Format

Contracts are stored in YAML format with the following structure:

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

## File Naming Convention

- `provided-api.yaml` - Contract this repository provides (if acting as provider)
- `{dependency-name}-api.yaml` - Cached contract from a dependency

## Workflow

### For Providers

1. Code changes are made to API endpoints
2. Contract extractor runs (manually or via git hook)
3. Updated contract is saved to `provided-api.yaml`
4. Contract is committed to git with code changes

### For Consumers

1. Run `specsync bridge sync` to fetch latest contracts
2. Contracts are cached in this directory
3. Run `specsync bridge validate` to check for drift
4. Fix any drift issues before deployment

## Git Tracking

Contract files should be committed to git to:
- Enable offline validation
- Track contract changes over time
- Allow code review of API changes
- Support CI/CD pipelines

## Cache Management

- Contracts are updated when running `specsync bridge sync`
- Old contracts are overwritten with new versions
- Removing a dependency deletes its cached contract
- Manual deletion is safe - contracts will be re-synced on next sync operation
