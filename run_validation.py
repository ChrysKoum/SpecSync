#!/usr/bin/env python3
"""
Standalone validation runner for SpecSync pre-commit hook.
This script runs validation on staged changes and returns appropriate exit codes.
"""

import sys
import subprocess
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.validator import ValidationOrchestrator
from backend.drift_detector import DriftDetector
from backend.test_analyzer import TestCoverageDetector
from backend.doc_analyzer import DocumentationAlignmentDetector
from backend.suggestion_generator import SuggestionGenerator
from backend.auto_remediation import enable_auto_remediation
from backend.auto_fix import enable_auto_fix, get_auto_fix_instructions


def get_git_context():
    """Get git context (staged files and diff)."""
    try:
        # Get current branch
        branch_result = subprocess.run(
            "git rev-parse --abbrev-ref HEAD",
            capture_output=True,
            text=True,
            check=True,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        branch = branch_result.stdout.strip()
        
        # Get staged files
        files_result = subprocess.run(
            "git diff --cached --name-only",
            capture_output=True,
            text=True,
            check=True,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        staged_files = [f.strip() for f in files_result.stdout.split('\n') if f.strip()]
        
        # Get diff (with error handling for unicode)
        diff_result = subprocess.run(
            "git diff --cached",
            capture_output=True,
            text=True,
            check=True,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        diff = diff_result.stdout
        
        return {
            "branch": branch,
            "stagedFiles": staged_files,
            "diff": diff
        }
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Error getting git context: {e}")
        return None


def load_config():
    """Load SpecSync configuration."""
    config_path = Path(".kiro/settings/specsync.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {
        "auto_remediation": {"enabled": False, "mode": "tasks"},
        "semi_auto_fix": {"enabled": False},
        "validation": {"block_on_drift": True}
    }


def get_commit_message():
    """Get the commit message from git."""
    try:
        # Try to get the message from COMMIT_EDITMSG
        commit_msg_file = Path(".git/COMMIT_EDITMSG")
        if commit_msg_file.exists():
            with open(commit_msg_file, 'r') as f:
                return f.readline().strip()
    except:
        pass
    return "Current commit"


def main():
    """Run validation on staged changes."""
    print("Initializing SpecSync validation...")
    
    # Load configuration
    config = load_config()
    auto_remediation_enabled = config.get("auto_remediation", {}).get("enabled", False)
    remediation_mode = config.get("auto_remediation", {}).get("mode", "tasks")
    semi_auto_enabled = config.get("semi_auto_fix", {}).get("enabled", False)
    allow_commit_with_tasks = config.get("validation", {}).get("allow_commit_with_tasks", True)
    
    if auto_remediation_enabled:
        if remediation_mode == "semi-auto" and semi_auto_enabled:
            print("🤖 Semi-automatic fix mode: ENABLED")
            print("   You will need to manually ask Kiro to fix drift after commit")
        else:
            print("[*] Auto-remediation mode: ENABLED")
            print("   Tasks will be generated for any detected drift")
        print()
    
    # Get git context
    git_context = get_git_context()
    if not git_context:
        print("[ERROR] Failed to get git context")
        return 1
    
    staged_files = git_context["stagedFiles"]
    
    if not staged_files:
        print("ℹ️  No files staged for commit")
        return 0
    
    print(f"[*] Validating {len(staged_files)} staged file(s)...")
    print()
    
    # Initialize orchestrator
    orchestrator = ValidationOrchestrator()
    
    # Run validation
    result = orchestrator.validate(git_context)
    
    # Display results
    print()
    print("=" * 70)
    print("  VALIDATION RESULTS")
    print("=" * 70)
    print()
    
    # Handle both dict and object results
    if isinstance(result, dict):
        success = result.get('success', False)
        message = result.get('message', 'Unknown')
        drift_report = result.get('drift_report')
        test_report = result.get('test_report')
        doc_report = result.get('doc_report')
        bridge_report = result.get('bridge_report')
        suggestions = result.get('suggestions', [])
    else:
        success = result.success
        message = result.message
        drift_report = result.drift_report
        test_report = result.test_report
        doc_report = result.doc_report
        bridge_report = getattr(result, 'bridge_report', None)
        suggestions = result.suggestions
    
    if success:
        print("[OK] SUCCESS: All validations passed")
        print()
        print(f"   Message: {message}")
        return 0
    
    # Validation failed - check if we should allow commit anyway
    print("[WARN] WARNING: Validation issues detected")
    print()
    print(f"   Message: {message}")
    print()
    
    # Check if we should allow commit with warnings
    block_on_drift = config.get("validation", {}).get("block_on_drift", True)
    
    # Auto-remediation mode
    if auto_remediation_enabled:
        print()
        print("=" * 70)
        
        # Convert result to dict if needed
        if isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {
                'success': success,
                'message': message,
                'drift_report': drift_report,
                'test_report': test_report,
                'doc_report': doc_report,
                'suggestions': suggestions
            }
        
        # Check mode
        if remediation_mode == "semi-auto" and semi_auto_enabled:
            print("  SEMI-AUTOMATIC FIX MODE")
            print("=" * 70)
            print()
            
            # Get commit message
            commit_msg = get_commit_message()
            
            # Execute auto-fix
            auto_fix_result = enable_auto_fix(result_dict, config, commit_msg)
            
            if auto_fix_result.get('requires_kiro_agent', False):
                print("🤖 Semi-Automatic Fix Available")
                print()
                print(f"   Estimated effort: {auto_fix_result.get('estimated_credits', 'Unknown')} issues to fix")
                print()
                print("📋 What needs fixing:")
                for fix in auto_fix_result.get('fixes_applied', []):
                    print(f"   • {fix}")
                print()
                print("🔄 Next Steps:")
                print("   1. Your commit will proceed")
                print("   2. Open Kiro chat")
                print("   3. Say: 'Fix the drift from my last commit'")
                print("   4. Kiro will make all fixes")
                print("   5. Kiro will create a follow-up commit")
                print()
                print("=" * 70)
                print()
                print("[OK] Commit ALLOWED - Manual Kiro invocation required")
                print()
                print("[TIP] After commit, open Kiro and say:")
                print("   'Fix the drift from my last commit'")
                print()
                return 0  # Allow commit
            else:
                print(f"[FAIL] Semi-auto fix failed: {auto_fix_result.get('message')}")
                print()
                return 1
        
        else:
            # Task generation mode
            print("  AUTO-REMEDIATION MODE")
            print("=" * 70)
            print()
            
            # Generate remediation tasks
            remediation_message = enable_auto_remediation(result_dict, feature_name="app")
            print(remediation_message)
            print()
            print("=" * 70)
            print()
            
            if allow_commit_with_tasks:
                print("[OK] Commit ALLOWED with remediation tasks generated")
                print("   Please complete the tasks in the generated file")
                print()
                return 0  # Allow commit
            else:
                print("[BLOCKED] Commit BLOCKED - Fix issues before committing")
                print("   (Set 'allow_commit_with_tasks: true' to allow commits with tasks)")
                print()
                return 1  # Block commit
    
    # Standard mode (no auto-remediation)
    print()
    
    # Show drift issues
    if drift_report:
        aligned = drift_report.get('aligned', True) if isinstance(drift_report, dict) else drift_report.aligned
        if not aligned:
            issues = drift_report.get('issues', []) if isinstance(drift_report, dict) else drift_report.issues
            print("[INFO] Drift Issues:")
            print(f"   Total: {len(issues)}")
            for issue in issues[:5]:  # Show first 5
                if isinstance(issue, dict):
                    print(f"   • [{issue.get('type')}] {issue.get('file')}: {issue.get('description')}")
                else:
                    print(f"   • [{issue.type}] {issue.file}: {issue.description}")
            if len(issues) > 5:
                print(f"   ... and {len(issues) - 5} more")
            print()
    
    # Show test coverage issues
    if test_report:
        has_issues = test_report.get('has_issues', False) if isinstance(test_report, dict) else test_report.has_issues
        if has_issues:
            issues = test_report.get('issues', []) if isinstance(test_report, dict) else test_report.issues
            print("🧪 Test Coverage Issues:")
            print(f"   Total: {len(issues)}")
            for issue in issues[:3]:  # Show first 3
                if isinstance(issue, dict):
                    print(f"   • [{issue.get('type')}] {issue.get('description')}")
                else:
                    print(f"   • [{issue.type}] {issue.description}")
            if len(issues) > 3:
                print(f"   ... and {len(issues) - 3} more")
            print()
    
    # Show documentation issues
    if doc_report:
        has_issues = doc_report.get('has_issues', False) if isinstance(doc_report, dict) else doc_report.has_issues
        if has_issues:
            issues = doc_report.get('issues', []) if isinstance(doc_report, dict) else doc_report.issues
            print("📚 Documentation Issues:")
            print(f"   Total: {len(issues)}")
            for issue in issues[:3]:  # Show first 3
                if isinstance(issue, dict):
                    print(f"   • [{issue.get('type')}] {issue.get('description')}")
                else:
                    print(f"   • [{issue.type}] {issue.description}")
            if len(issues) > 3:
                print(f"   ... and {len(issues) - 3} more")
            print()
    
    # Show bridge contract drift issues
    if bridge_report and bridge_report.get('enabled', False):
        has_issues = bridge_report.get('has_issues', False)
        if has_issues:
            issues = bridge_report.get('issues', [])
            print("🌉 Bridge Contract Drift:")
            print(f"   Total: {len(issues)}")
            print(f"   Dependencies: {', '.join(bridge_report.get('dependencies_checked', []))}")
            for issue in issues[:3]:  # Show first 3
                print(f"   • [{issue['dependency']}] {issue['method']} {issue['endpoint']}")
                print(f"     {issue['message']}")
            if len(issues) > 3:
                print(f"   ... and {len(issues) - 3} more")
            print()
        else:
            # Show success message for bridge
            deps = bridge_report.get('dependencies_checked', [])
            if deps:
                print("🌉 Bridge Contract Status:")
                print(f"   ✓ All API calls align with contracts ({len(deps)} dependencies checked)")
                print()
    
    # Show suggestions
    if suggestions:
        # Handle both list and dict formats
        if isinstance(suggestions, dict):
            suggestions_list = suggestions.get('suggestions', [])
        elif isinstance(suggestions, list):
            suggestions_list = suggestions
        else:
            suggestions_list = []
        
        if suggestions_list:
            print("💡 Suggestions:")
            for i, suggestion in enumerate(suggestions_list[:5], 1):
                if isinstance(suggestion, dict):
                    print(f"   {i}. [{suggestion.get('type', '').upper()}] {suggestion.get('description')}")
                else:
                    print(f"   {i}. [{suggestion.type.upper()}] {suggestion.description}")
            if len(suggestions_list) > 5:
                print(f"   ... and {len(suggestions_list) - 5} more suggestions")
            print()
    
    print("=" * 70)
    print()
    
    # Final decision: block or allow based on configuration
    if not block_on_drift:
        print("[OK] Commit ALLOWED (block_on_drift is disabled)")
        print("   Validation issues detected but commit is allowed per configuration")
        print()
        return 0
    
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error during validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
