#!/usr/bin/env python3
"""
Quick test script to verify SpecSync is working correctly.
Runs all major components and reports status.
"""

import subprocess
import sys
import os
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_status(test_name, passed, details=""):
    """Print test status."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if details:
        print(f"       {details}")


def run_command(cmd, cwd=None):
    """Run a command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def main():
    """Run all quick tests."""
    print_header("SpecSync Quick Test Suite")
    
    results = []
    
    # Test 1: Python environment
    print_header("Test 1: Python Environment")
    success, stdout, stderr = run_command("python --version")
    print_status("Python installed", success, stdout.strip() if success else stderr)
    results.append(("Python Environment", success))
    
    # Test 2: Dependencies installed
    print_header("Test 2: Python Dependencies")
    success, stdout, stderr = run_command("python -c \"import fastapi, pytest, hypothesis\"")
    print_status("Python dependencies", success, "FastAPI, pytest, Hypothesis available" if success else "Missing dependencies")
    results.append(("Python Dependencies", success))
    
    # Test 3: Node.js environment
    print_header("Test 3: Node.js Environment")
    success, stdout, stderr = run_command("node --version")
    print_status("Node.js installed", success, stdout.strip() if success else stderr)
    results.append(("Node.js Environment", success))
    
    # Test 4: MCP tool build
    print_header("Test 4: MCP Tool Build")
    success, stdout, stderr = run_command("npm run build", cwd="mcp")
    print_status("MCP tool builds", success, "TypeScript compiled successfully" if success else "Build failed")
    results.append(("MCP Tool Build", success))
    
    # Test 5: MCP tool manual test
    print_header("Test 5: MCP Tool Functionality")
    success, stdout, stderr = run_command("node test-manual.js", cwd="mcp")
    print_status("MCP tool runs", success, "Git context extraction works" if success else "MCP tool failed")
    results.append(("MCP Tool Functionality", success))
    
    # Test 6: Python test suite
    print_header("Test 6: Python Test Suite")
    success, stdout, stderr = run_command("pytest tests/ -q")
    if success:
        # Extract test count from output
        lines = stdout.split('\n')
        summary_line = [l for l in lines if 'passed' in l.lower()]
        details = summary_line[0] if summary_line else "All tests passed"
    else:
        details = "Some tests failed"
    print_status("Test suite", success, details)
    results.append(("Python Test Suite", success))
    
    # Test 7: Demo scripts
    print_header("Test 7: Demo Scripts")
    
    demos = [
        ("Validation Flow", "demo_validation_flow.py"),
        ("Steering Rules", "demo_steering_rules.py"),
        ("Performance", "demo_performance_monitoring.py"),
        ("Staging Preservation", "demo_staging_preservation.py"),
        ("E2E Validation", "demo_e2e_validation.py"),
    ]
    
    demo_results = []
    for name, script in demos:
        success, stdout, stderr = run_command(f"python {script}")
        print_status(f"Demo: {name}", success)
        demo_results.append(success)
        results.append((f"Demo: {name}", success))
    
    # Test 8: Example service
    print_header("Test 8: Example Service")
    # Just check if the files exist and can be imported
    success, stdout, stderr = run_command(
        "python -c \"from backend.main import app; from backend.handlers import health, user; from backend.models import User\""
    )
    print_status("Example service imports", success, "All modules importable" if success else "Import errors")
    results.append(("Example Service", success))
    
    # Test 9: Documentation exists
    print_header("Test 9: Documentation")
    docs_exist = all([
        Path("README.md").exists(),
        Path("docs/index.md").exists(),
        Path("docs/architecture.md").exists(),
        Path("docs/api/health.md").exists(),
        Path("docs/api/users.md").exists(),
    ])
    print_status("Documentation files", docs_exist, "All docs present" if docs_exist else "Missing docs")
    results.append(("Documentation", docs_exist))
    
    # Test 10: Spec files
    print_header("Test 10: Specification Files")
    specs_exist = all([
        Path(".kiro/specs/app.yaml").exists(),
        Path(".kiro/specs/specsync-core/requirements.md").exists(),
        Path(".kiro/specs/specsync-core/design.md").exists(),
        Path(".kiro/specs/specsync-core/tasks.md").exists(),
        Path(".kiro/steering/rules.md").exists(),
    ])
    print_status("Spec files", specs_exist, "All specs present" if specs_exist else "Missing specs")
    results.append(("Specification Files", specs_exist))
    
    # Summary
    print_header("Test Summary")
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed}")
    print()
    
    if failed > 0:
        print("Failed Tests:")
        for name, success in results:
            if not success:
                print(f"  ❌ {name}")
        print()
    
    if passed == total:
        print("🎉 All tests passed! SpecSync is ready to use.")
        print()
        print("Next steps:")
        print("  1. Configure MCP server in Kiro: See README.md")
        print("  2. Install pre-commit hook: python install_hook.py")
        print("  3. Start using SpecSync: git add <files> && git commit")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        print()
        print("Troubleshooting:")
        print("  - Ensure virtual environment is activated: .venv\\Scripts\\activate")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Build MCP tool: cd mcp && npm install && npm run build")
        print("  - See TEST_SCENARIOS.md for detailed testing instructions")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
