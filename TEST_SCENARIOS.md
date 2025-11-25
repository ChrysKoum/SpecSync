# SpecSync Testing Scenarios

This guide provides step-by-step scenarios to test SpecSync functionality.

---

## Scenario 1: Test with Demo Scripts (No Git Required)

**Purpose:** Verify all components work without making actual commits

**Steps:**
```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Run each demo script
python demo_e2e_validation.py
python demo_validation_flow.py
python demo_steering_rules.py
python demo_performance_monitoring.py
python demo_staging_preservation.py
```

**Expected Results:**
- All demos complete successfully
- No errors in output
- Validation results show drift detection working
- Performance metrics displayed

---

## Scenario 2: Test Drift Detection (Simulated)

**Purpose:** See how SpecSync detects misalignment

**Steps:**
```bash
# Run the validation flow demo
python demo_validation_flow.py
```

**What to Look For:**
- ✗ Validation failures for files without tests
- ✗ Drift detected for code not in spec
- ✗ Documentation issues flagged
- 💡 Suggestions provided for each issue

---

## Scenario 3: Test with Real Git Changes

**Purpose:** Test actual commit-time validation

### 3a. Test Drift Detection (Commit Should Fail)

```bash
# 1. Create a new endpoint (without updating spec/tests/docs)
# Edit backend/handlers/user.py and add:

@router.get("/users/{id}/posts")
async def get_user_posts(id: int):
    """Get posts for a specific user."""
    return {"user_id": id, "posts": []}

# 2. Stage the change
git add backend/handlers/user.py

# 3. Try to commit
git commit -m "Add user posts endpoint"

# 4. Expected: Commit blocked with drift warnings
```

**Expected Output:**
```
❌ Drift Detected - Commit Blocked

Issues:
1. [SPEC] New endpoint GET /users/{id}/posts not defined in spec
2. [TEST] Missing tests for new endpoint
3. [DOCS] No documentation for new endpoint

Suggestions:
1. Add endpoint to .kiro/specs/app.yaml
2. Add tests to tests/unit/test_user.py
3. Document in docs/api/users.md
```

### 3b. Test Aligned Changes (Commit Should Succeed)

```bash
# 1. Update the spec first
# Edit .kiro/specs/app.yaml and add:

  - path: "/users/{id}/posts"
    method: "GET"
    description: "Get posts for a specific user"
    parameters:
      - name: "id"
        type: "integer"
    response:
      type: "array"
    tests_required: true

# 2. Add tests
# Edit tests/unit/test_user.py and add:

def test_get_user_posts():
    # Test implementation
    pass

# 3. Update documentation
# Edit docs/api/users.md and add endpoint description

# 4. Stage all changes
git add .kiro/specs/app.yaml
git add backend/handlers/user.py
git add tests/unit/test_user.py
git add docs/api/users.md

# 5. Try to commit
git commit -m "Add user posts endpoint with spec, tests, and docs"

# 6. Expected: Commit succeeds ✅
```

---

## Scenario 4: Test MCP Tool

**Purpose:** Verify git context extraction works

**Steps:**
```bash
# 1. Build the MCP tool
cd mcp
npm run build

# 2. Test manually
node test-manual.js

# 3. Stage some files to see it detect them
cd ..
git add README.md
cd mcp
node test-manual.js
```

**Expected Output:**
```
✅ Successfully retrieved git context
Branch: main
Staged Files: ['README.md']
Diff Length: XXX characters
```

---

## Scenario 5: Test Example Service

**Purpose:** Verify the FastAPI service works

**Steps:**
```bash
# 1. Start the service
cd backend
uvicorn main:app --reload

# 2. In another terminal, test endpoints:
curl http://localhost:8000/health
# Expected: {"status":"healthy","timestamp":"..."}

curl http://localhost:8000/users
# Expected: [{"id":1,"username":"alice",...}, ...]

curl http://localhost:8000/users/1
# Expected: {"id":1,"username":"alice",...}

curl http://localhost:8000/users/999
# Expected: {"detail":"User not found"}

# 3. Visit interactive docs
# Open browser: http://localhost:8000/docs
```

---

## Scenario 6: Test Steering Rules

**Purpose:** Verify steering rules filter files correctly

**Steps:**
```bash
# 1. Stage a mix of files (some should be ignored)
git add backend/models.py
git add __pycache__/test.pyc
git add node_modules/package.json

# 2. Run validation
python demo_steering_rules.py

# 3. Check output - ignored files should be filtered
```

**Expected:**
- `backend/models.py` - validated ✓
- `__pycache__/test.pyc` - ignored (in ignore patterns)
- `node_modules/package.json` - ignored (in ignore patterns)

---

## Scenario 7: Test Performance

**Purpose:** Verify validation completes quickly

**Steps:**
```bash
# Run performance demo
python demo_performance_monitoring.py
```

**Expected:**
- Total validation time < 1 second for typical files
- Detailed timing breakdown shown
- All validations complete within 30-second target

---

## Scenario 8: Test Staging Preservation

**Purpose:** Verify validation doesn't modify staged changes

**Steps:**
```bash
# 1. Stage some files
git add backend/models.py

# 2. Run staging preservation demo
python demo_staging_preservation.py

# 3. Verify staging area unchanged
git status
```

**Expected:**
- Staging area identical before and after validation
- Demo reports: "✓ Staging area unchanged"

---

## Scenario 9: Test Complete Integration

**Purpose:** Full end-to-end test with Kiro

**Prerequisites:**
- Kiro IDE installed
- MCP server configured in Kiro

**Steps:**

### 9a. Configure MCP Server

1. Open Kiro settings
2. Edit `.kiro/settings/mcp.json` (or `~/.kiro/settings/mcp.json`)
3. Add:
```json
{
  "mcpServers": {
    "specsync-git": {
      "command": "node",
      "args": ["D:/path/to/specsync/mcp/dist/server.js"],
      "disabled": false,
      "autoApprove": ["get_staged_diff"]
    }
  }
}
```
4. Restart Kiro or reconnect MCP server

### 9b. Install Pre-Commit Hook

```bash
python install_hook.py
```

### 9c. Test Commit Flow

1. Make a change to `backend/handlers/user.py`
2. Stage it: `git add backend/handlers/user.py`
3. Commit: `git commit -m "Test change"`
4. Kiro should trigger validation automatically
5. Check Kiro output for validation results

---

## Scenario 10: Test Error Handling

**Purpose:** Verify graceful error handling

### 10a. Test Non-Git Directory

```bash
# 1. Go to a non-git directory
cd C:\temp

# 2. Try to run MCP tool
node D:/path/to/specsync/mcp/dist/server.js
```

**Expected:** Error message indicating not a git repository

### 10b. Test Empty Staging Area

```bash
# 1. Ensure nothing is staged
git reset

# 2. Run validation
python demo_validation_flow.py
```

**Expected:** Validation completes with "No files to validate"

### 10c. Test Invalid Spec File

```bash
# 1. Temporarily break the spec
# Edit .kiro/specs/app.yaml and add invalid YAML

# 2. Run validation
python demo_validation_flow.py

# 3. Fix the spec file
```

**Expected:** Error message about invalid YAML

---

## Quick Verification Checklist

Use this checklist to verify everything works:

- [ ] All demo scripts run without errors
- [ ] Test suite passes (107/107 tests)
- [ ] MCP tool builds successfully
- [ ] MCP tool extracts git context
- [ ] Example service starts and responds
- [ ] Drift detection works (blocks bad commits)
- [ ] Aligned changes pass validation
- [ ] Steering rules filter ignored files
- [ ] Performance is under 30 seconds
- [ ] Staging area preserved after validation
- [ ] Documentation is accurate

---

## Troubleshooting

### Issue: "Module not found" errors

**Solution:**
```bash
# Ensure virtual environment is activated
.venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: MCP tool not found

**Solution:**
```bash
cd mcp
npm install
npm run build
```

### Issue: Git commands fail

**Solution:**
```bash
# Verify you're in a git repository
git status

# Check git is installed
git --version
```

### Issue: Port 8000 already in use

**Solution:**
```bash
# Use a different port
uvicorn backend.main:app --reload --port 8001
```

---

## Next Steps

After testing:

1. **Customize for your project:**
   - Update `.kiro/specs/app.yaml` with your service spec
   - Modify `.kiro/steering/rules.md` for your conventions
   - Add your own endpoints to the example service

2. **Integrate with your workflow:**
   - Install the pre-commit hook: `python install_hook.py`
   - Configure MCP server in Kiro
   - Start committing with SpecSync validation!

3. **Monitor and improve:**
   - Review validation results
   - Adjust steering rules as needed
   - Add more tests for your specific use cases

---

**Happy Testing! 🚀**
