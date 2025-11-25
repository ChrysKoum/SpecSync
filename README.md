# SpecSync

**Keep your specs, code, tests, and docs in perfect sync**

SpecSync is a commit-driven reliability layer that ensures specifications, code, tests, and documentation remain synchronized throughout the development lifecycle. The system acts as a quality gate at commit-time, preventing drift between these critical artifacts before changes enter the codebase.

## Project Structure

```
specsync/
├── backend/              # Python FastAPI backend
│   └── handlers/         # API endpoint handlers
├── mcp/                  # Model Context Protocol tool
│   └── src/              # TypeScript source files
├── docs/                 # Documentation
│   └── api/              # API documentation
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   ├── property/         # Property-based tests
│   ├── integration/      # Integration tests
│   └── fixtures/         # Test fixtures
├── .kiro/                # Kiro configuration
│   ├── specs/            # Feature specifications
│   └── steering/         # Steering rules
├── requirements.txt      # Python dependencies
└── mcp/package.json      # Node.js dependencies
```

## Installation

### Python Backend

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix/MacOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### MCP Tool

```bash
cd mcp
npm install
npm run build
```

## Development

### Running Tests

**Python tests:**
```bash
pytest
```

**MCP tool tests:**
```bash
cd mcp
npm test
```

### Running the Example Service

```bash
cd backend
uvicorn main:app --reload
```

## How It Works

1. **Git commit triggers** the pre-commit hook
2. **MCP tool extracts** git context (branch, staged diff)
3. **Kiro agent analyzes** changes against specs, tests, and docs
4. **System validates** alignment and suggests fixes if needed
5. **Commit proceeds** only when alignment is confirmed

## Features

- ✅ Automatic validation on commit
- ✅ Drift detection between specs and code
- ✅ Test coverage validation
- ✅ Documentation sync checking
- ✅ Actionable suggestions for fixes
- ✅ Customizable steering rules
- ✅ Fast validation (< 30 seconds)

## License

MIT
