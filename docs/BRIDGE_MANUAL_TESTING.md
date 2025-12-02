# Bridge Manual Testing Checklist

## Prerequisites

Before testing, ensure you have:
- [ ] Python 3.9+ installed
- [ ] Git installed
- [ ] Two separate folders for test repos
- [ ] specsync-bridge package installed: `pip install -e /path/to/specsync`

---

## Test Setup

### Create Test Repos

```bash
# Create provider repo (backend)
mkdir test-backend
cd test-backend
git init

# Create consumer repo (frontend)
mkdir ../test-frontend
cd ../test-frontend
git init
```

---

## Part 1: Provider Repo Setup

### 1.1 Initialize Bridge as Provider
```bash
cd test-backend
specsync-bridge init --role provider
```

**Expected:**
- [ ] `.kiro/settings/bridge.json` created
- [ ] `.kiro/contracts/` directory created
- [ ] Config shows `role: provider`

**Verify:**
```bash
specsync-bridge status
```

### 1.2 Create Sample API Code

Create `app.py`:
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def list_users():
    return [{"id": 1, "name": "Alice"}]

@app.get("/users/{id}")
def get_user(id: int):
    return {"id": id, "name": "Alice"}

@app.post("/users")
def create_user(name: str):
    return {"id": 2, "name": name}
```

### 1.3 Extract Contract
```bash
specsync-bridge extract
```

**Expected:**
- [ ] `.kiro/contracts/provided-api.yaml` created
- [ ] Contract contains 3 endpoints (GET /users, GET /users/{id}, POST /users)

**Verify:**
```bash
cat .kiro/contracts/provided-api.yaml
```

### 1.4 Commit and Push
```bash
git add .
git commit -m "Add API contract"
# Push to GitHub/GitLab (create remote repo first)
git remote add origin https://github.com/YOUR_USER/test-backend.git
git push -u origin main
```

**Checkpoint 1:** Provider repo is set up with contract ✓

---

## Part 2: Consumer Repo Setup

### 2.1 Initialize Bridge as Consumer
```bash
cd ../test-frontend
specsync-bridge init --role consumer
```

**Expected:**
- [ ] `.kiro/settings/bridge.json` created
- [ ] Config shows `role: consumer`

### 2.2 Add Backend as Dependency
```bash
specsync-bridge add-dependency backend --git-url https://github.com/YOUR_USER/test-backend.git
```

**Expected:**
- [ ] Dependency added to `bridge.json`
- [ ] Shows next step to sync

**Verify:**
```bash
specsync-bridge status
```
- [ ] Shows `backend` dependency as "Not synced"

### 2.3 Sync Contract
```bash
specsync-bridge sync
```

**Expected:**
- [ ] Contract fetched from backend repo
- [ ] `.kiro/contracts/backend-api.yaml` created
- [ ] Shows endpoint count

**Verify:**
```bash
specsync-bridge status
```
- [ ] Shows `backend` dependency as "Synced"
- [ ] Shows endpoint count

**Checkpoint 2:** Consumer repo synced with provider contract ✓

---

## Part 3: Validation Tests

### 3.1 Create Valid API Calls

Create `api_client.py`:
```python
import requests

def get_users():
    return requests.get("http://api.example.com/users")

def get_user(id):
    return requests.get(f"http://api.example.com/users/{id}")
```

### 3.2 Validate (Should Pass)
```bash
specsync-bridge validate
```

**Expected:**
- [ ] Shows "All API calls align with contracts"
- [ ] Exit code 0

### 3.3 Create Invalid API Call

Add to `api_client.py`:
```python
def get_user_posts(id):
    # This endpoint doesn't exist in the contract!
    return requests.get(f"http://api.example.com/users/{id}/posts")
```

### 3.4 Validate (Should Fail)
```bash
specsync-bridge validate
```

**Expected:**
- [ ] Shows drift detected
- [ ] Shows `GET /users/{id}/posts` as missing endpoint
- [ ] Shows file and line number
- [ ] Exit code 1

**Checkpoint 3:** Drift detection working ✓

---

## Part 4: Contract Update Flow

### 4.1 Provider Adds New Endpoint

In `test-backend/app.py`, add:
```python
@app.get("/users/{id}/posts")
def get_user_posts(id: int):
    return []
```

### 4.2 Re-extract Contract
```bash
cd ../test-backend
specsync-bridge extract
git add .
git commit -m "Add posts endpoint"
git push
```

### 4.3 Consumer Re-syncs
```bash
cd ../test-frontend
specsync-bridge sync
```

**Expected:**
- [ ] Shows "Added: GET /users/{id}/posts" in changes

### 4.4 Validate Again (Should Pass Now)
```bash
specsync-bridge validate
```

**Expected:**
- [ ] Shows "All API calls align with contracts"
- [ ] Exit code 0

**Checkpoint 4:** Contract update flow working ✓

---

## Part 5: Offline Fallback Test

### 5.1 Disconnect Network (or use invalid URL)

Edit `.kiro/settings/bridge.json` and change git_url to invalid:
```json
"git_url": "https://github.com/invalid/nonexistent.git"
```

### 5.2 Try to Sync
```bash
specsync-bridge sync
```

**Expected:**
- [ ] Shows warning about using cached contract
- [ ] Still shows endpoint count from cache
- [ ] Validation still works with cached contract

**Checkpoint 5:** Offline fallback working ✓

---

## Part 6: Multiple Dependencies Test

### 6.1 Create Second Provider Repo
```bash
mkdir ../test-auth
cd ../test-auth
git init
specsync-bridge init --role provider
```

Create `auth.py`:
```python
from fastapi import FastAPI
app = FastAPI()

@app.post("/auth/login")
def login(username: str, password: str):
    return {"token": "abc123"}

@app.post("/auth/logout")
def logout():
    return {"success": True}
```

```bash
specsync-bridge extract
git add .
git commit -m "Add auth contract"
# Push to remote
```

### 6.2 Add Second Dependency to Consumer
```bash
cd ../test-frontend
specsync-bridge add-dependency auth --git-url https://github.com/YOUR_USER/test-auth.git
```

### 6.3 Sync All
```bash
specsync-bridge sync
```

**Expected:**
- [ ] Both dependencies synced in parallel
- [ ] Shows progress for each
- [ ] Both contracts cached

### 6.4 Status Shows Both
```bash
specsync-bridge status
```

**Expected:**
- [ ] Shows 2 dependencies
- [ ] Both marked as synced

**Checkpoint 6:** Multiple dependencies working ✓

---

## Summary Checklist

| Test | Status |
|------|--------|
| Provider init | ☐ |
| Contract extraction | ☐ |
| Consumer init | ☐ |
| Add dependency | ☐ |
| Sync contract | ☐ |
| Validate (pass) | ☐ |
| Validate (fail with drift) | ☐ |
| Contract update flow | ☐ |
| Offline fallback | ☐ |
| Multiple dependencies | ☐ |

---

## Troubleshooting

### "Bridge not initialized"
Run `specsync-bridge init --role consumer` or `--role provider`

### "Dependency not found"
Run `specsync-bridge add-dependency <name> --git-url <url>`

### "Contract not found"
Run `specsync-bridge sync` to fetch contracts

### Git clone fails
- Check git URL is correct
- Check you have access to the repo
- Check network connection

### No endpoints extracted
- Ensure code uses FastAPI decorators (`@app.get`, `@router.post`, etc.)
- Check file patterns in config

---

## Quick Test Script

Save as `test_bridge.sh`:
```bash
#!/bin/bash
set -e

echo "=== Testing SpecSync Bridge ==="

# Cleanup
rm -rf /tmp/test-backend /tmp/test-frontend

# Provider setup
echo "1. Setting up provider..."
mkdir -p /tmp/test-backend
cd /tmp/test-backend
git init
specsync-bridge init --role provider

cat > app.py << 'EOF'
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    return []

@app.get("/users/{id}")
def get_user(id: int):
    return {"id": id}
EOF

specsync-bridge extract
git add .
git commit -m "Initial"

echo "✓ Provider setup complete"

# Consumer setup (local test - no remote needed)
echo "2. Setting up consumer..."
mkdir -p /tmp/test-frontend
cd /tmp/test-frontend
git init
specsync-bridge init --role consumer

# For local testing, manually copy contract
mkdir -p .kiro/contracts
cp /tmp/test-backend/.kiro/contracts/provided-api.yaml .kiro/contracts/backend-api.yaml

# Add to config manually for local test
cat > .kiro/settings/bridge.json << 'EOF'
{
  "bridge": {
    "enabled": true,
    "role": "consumer",
    "dependencies": {
      "backend": {
        "name": "backend",
        "type": "http-api",
        "sync_method": "git",
        "git_url": "file:///tmp/test-backend",
        "contract_path": ".kiro/contracts/provided-api.yaml",
        "local_cache": ".kiro/contracts/backend-api.yaml"
      }
    }
  }
}
EOF

echo "✓ Consumer setup complete"

# Validation test
echo "3. Testing validation..."
cat > api.py << 'EOF'
import requests
def get_users():
    return requests.get("/users")
EOF

specsync-bridge validate && echo "✓ Validation passed"

echo ""
echo "=== All tests passed! ==="
```

Run with: `bash test_bridge.sh`
