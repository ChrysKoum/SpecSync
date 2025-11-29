"""
Validation orchestrator module for SpecSync.

This module orchestrates all validation steps including drift detection,
test coverage analysis, documentation validation, and suggestion generation.
"""
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import signal
import subprocess
import hashlib
from contextlib import contextmanager

from backend.steering_parser import SteeringRulesParser
from backend.rule_application import RuleApplicationEngine



class TimeoutException(Exception):
    """Exception raised when validation exceeds timeout limit."""
    pass


class StagingAreaModifiedException(Exception):
    """Exception raised when staging area is modified during validation."""
    pass


def get_staging_area_state() -> str:
    """
    Capture the current state of the git staging area.
    
    Returns a hash representing the current staged changes.
    This allows us to verify that validation doesn't modify the staging area.
    
    Returns:
        Hash string representing the staging area state
        
    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    try:
        # Get the staged diff content
        result = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        staged_diff = result.stdout
        
        # Get the list of staged files
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        staged_files = result.stdout
        
        # Combine both to create a comprehensive state representation
        state_content = f"{staged_files}\n---\n{staged_diff}"
        
        # Return hash of the state
        return hashlib.sha256(state_content.encode('utf-8')).hexdigest()
        
    except subprocess.CalledProcessError as e:
        # If git command fails, return empty state
        # This handles non-git directories gracefully
        return ""
    except FileNotFoundError:
        # Git not installed or not in PATH
        return ""


def verify_staging_area_unchanged(before_state: str, after_state: str) -> None:
    """
    Verify that the staging area hasn't changed during validation.
    
    Args:
        before_state: Hash of staging area before validation
        after_state: Hash of staging area after validation
        
    Raises:
        StagingAreaModifiedException: If staging area was modified
    """
    if before_state != after_state:
        raise StagingAreaModifiedException(
            "Staging area was modified during validation. "
            "Validation must run in read-only mode and never modify staged changes."
        )


@contextmanager
def timeout_handler(seconds: int):
    """
    Context manager for handling timeouts.
    
    Args:
        seconds: Timeout duration in seconds
        
    Raises:
        TimeoutException: If operation exceeds timeout
    """
    def timeout_signal_handler(signum, frame):
        raise TimeoutException(f"Operation exceeded {seconds} second timeout")
    
    # Set up signal handler (Unix-like systems)
    try:
        old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    except AttributeError:
        # Windows doesn't support SIGALRM, use simple time-based check
        yield


class ValidationOrchestrator:
    """Main orchestrator for SpecSync validation."""
    
    def __init__(self, steering_rules_path: str = ".kiro/steering/rules.md", 
                 timeout_seconds: int = 30):
        """
        Initialize the validation orchestrator.
        
        Args:
            steering_rules_path: Path to steering rules document
            timeout_seconds: Maximum time allowed for validation (default: 30)
        """
        self.steering_parser = SteeringRulesParser(steering_rules_path)
        self.steering_rules: Optional[Dict[str, Any]] = None
        self.rule_engine: Optional[RuleApplicationEngine] = None
        self.timeout_seconds = timeout_seconds
        self.timing_data: Dict[str, float] = {}
    
    def load_steering_rules(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load and parse steering rules.
        
        Args:
            force_reload: If True, bypass cache and reload from file
        
        Returns:
            Parsed steering rules dictionary
        """
        self.steering_rules = self.steering_parser.parse(force_reload=force_reload)
        self.rule_engine = RuleApplicationEngine(self.steering_rules)
        return self.steering_rules
    
    def check_and_reload_steering_rules(self) -> bool:
        """
        Check if steering rules file has been modified and reload if needed.
        
        Returns:
            True if rules were reloaded, False otherwise
        """
        if not self.steering_parser:
            return False
        
        current_mtime = self.steering_parser._get_file_mtime()
        if current_mtime != self.steering_parser._last_modified:
            # File has changed, reload rules
            self.load_steering_rules(force_reload=True)
            return True
        
        return False
    
    def apply_steering_rules(self, validation_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply steering rules to validation context.
        
        Args:
            validation_context: Context containing files to validate
            
        Returns:
            Modified validation context with rules applied
        """
        if not self.steering_rules or not self.rule_engine:
            self.load_steering_rules()
        
        # Store original files for conflict detection
        validation_context['all_staged_files'] = validation_context.get('staged_files', [])
        
        # Apply correlation patterns to map files
        if 'staged_files' in validation_context:
            validation_context['file_mappings'] = self.rule_engine.apply_correlation_patterns(
                validation_context['staged_files']
            )
        
        # Filter out ignored files
        if 'staged_files' in validation_context:
            validation_context['filtered_files'] = self.rule_engine.filter_ignored_files(
                validation_context['staged_files']
            )
        
        # Add validation priorities
        validation_context['priorities'] = self.steering_rules.get('validation_priorities', {})
        
        # Add minimal change policy
        validation_context['minimal_change_policy'] = self.steering_rules.get('minimal_change_policy', {})
        
        return validation_context

    
    def validate(self, git_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main validation function that orchestrates all validation steps.
        
        This is the primary entry point for commit-time validation.
        Includes performance monitoring and timeout handling.
        
        Args:
            git_context: Git context from MCP tool containing:
                - branch: Current branch name
                - stagedFiles: List of staged file paths
                - diff: Full diff content
                
        Returns:
            ValidationResult dictionary with success/failure and suggestions
        """
        # Capture staging area state BEFORE validation
        # This ensures validation runs in read-only mode
        staging_state_before = get_staging_area_state()
        
        # Start overall timing
        start_time = time.time()
        self.timing_data = {}
        
        # Track if we hit timeout
        timed_out = False
        partial_results = False
        
        try:
            # Use timeout handler for the entire validation
            with timeout_handler(self.timeout_seconds):
                # Initialize validation context
                step_start = time.time()
                validation_context = {
                    'branch': git_context.get('branch', 'unknown'),
                    'staged_files': git_context.get('stagedFiles', []),
                    'diff': git_context.get('diff', ''),
                    'timestamp': start_time
                }
                self.timing_data['context_initialization'] = time.time() - step_start
                
                # Load and apply steering rules (with hot-reload check)
                step_start = time.time()
                # Check if steering rules file has been modified and reload if needed
                if self.steering_parser:
                    current_mtime = self.steering_parser._get_file_mtime()
                    if current_mtime != self.steering_parser._last_modified:
                        # File has changed, reload rules
                        self.load_steering_rules(force_reload=True)
                validation_context = self.apply_steering_rules(validation_context)
                self.timing_data['steering_rules'] = time.time() - step_start
                
                # Get filtered files (excluding ignored patterns)
                files_to_validate = validation_context.get('filtered_files', [])
                
                if not files_to_validate:
                    total_time = time.time() - start_time
                    self.timing_data['total'] = total_time
                    
                    # Verify staging area is unchanged even for early return
                    staging_state_after = get_staging_area_state()
                    staging_preserved = (staging_state_before == staging_state_after)
                    
                    return {
                        'success': True,
                        'message': 'No files to validate (all files ignored by steering rules)',
                        'allowCommit': True,
                        'drift_report': None,
                        'test_report': None,
                        'doc_report': None,
                        'suggestions': None,
                        'timing': self.timing_data,
                        'timed_out': False,
                        'staging_area_preserved': staging_preserved
                    }
                
                # Run all validation steps with individual timing
                drift_report = None
                test_report = None
                doc_report = None
                bridge_report = None
                
                try:
                    step_start = time.time()
                    drift_report = self._run_drift_detection(files_to_validate)
                    self.timing_data['drift_detection'] = time.time() - step_start
                except TimeoutException:
                    self.timing_data['drift_detection'] = time.time() - step_start
                    raise
                
                try:
                    step_start = time.time()
                    test_report = self._run_test_coverage_validation(files_to_validate)
                    self.timing_data['test_coverage'] = time.time() - step_start
                except TimeoutException:
                    self.timing_data['test_coverage'] = time.time() - step_start
                    raise
                
                try:
                    step_start = time.time()
                    doc_report = self._run_documentation_validation(files_to_validate)
                    self.timing_data['documentation'] = time.time() - step_start
                except TimeoutException:
                    self.timing_data['documentation'] = time.time() - step_start
                    raise
                
                try:
                    step_start = time.time()
                    bridge_report = self._run_bridge_validation()
                    self.timing_data['bridge_validation'] = time.time() - step_start
                except TimeoutException:
                    self.timing_data['bridge_validation'] = time.time() - step_start
                    raise
                
                # Aggregate results
                step_start = time.time()
                aggregated_result = self._aggregate_validation_results(
                    drift_report, test_report, doc_report, bridge_report, validation_context
                )
                self.timing_data['aggregation'] = time.time() - step_start
                
                # Generate suggestions if there are issues
                if not aggregated_result['success']:
                    step_start = time.time()
                    suggestions = self._generate_suggestions(
                        drift_report, test_report, doc_report, bridge_report
                    )
                    self.timing_data['suggestion_generation'] = time.time() - step_start
                    aggregated_result['suggestions'] = suggestions
                else:
                    aggregated_result['suggestions'] = None
                
                # Add reports to result
                aggregated_result['drift_report'] = drift_report
                aggregated_result['test_report'] = test_report
                aggregated_result['doc_report'] = doc_report
                aggregated_result['bridge_report'] = bridge_report
                
        except TimeoutException as e:
            # Timeout occurred - return partial results
            timed_out = True
            partial_results = True
            
            # Build partial result with whatever we have
            aggregated_result = {
                'success': False,
                'message': f'Validation timed out after {self.timeout_seconds} seconds. Partial results returned.',
                'allowCommit': False,  # Block commit on timeout for safety
                'drift_report': drift_report if 'drift_report' in locals() else None,
                'test_report': test_report if 'test_report' in locals() else None,
                'doc_report': doc_report if 'doc_report' in locals() else None,
                'bridge_report': bridge_report if 'bridge_report' in locals() else None,
                'suggestions': None,
                'timeout_error': str(e)
            }
        
        # Add timing information to result
        total_time = time.time() - start_time
        self.timing_data['total'] = total_time
        aggregated_result['timing'] = self.timing_data
        aggregated_result['timed_out'] = timed_out
        aggregated_result['partial_results'] = partial_results
        
        # Verify staging area is unchanged AFTER validation
        # This is a critical safety check to ensure validation is read-only
        staging_state_after = get_staging_area_state()
        try:
            verify_staging_area_unchanged(staging_state_before, staging_state_after)
            aggregated_result['staging_area_preserved'] = True
        except StagingAreaModifiedException as e:
            # This is a critical error - validation modified the staging area
            aggregated_result['staging_area_preserved'] = False
            aggregated_result['staging_area_error'] = str(e)
            aggregated_result['success'] = False
            aggregated_result['allowCommit'] = False
            aggregated_result['message'] = f"CRITICAL ERROR: {str(e)}"
        
        return aggregated_result

    
    def _run_drift_detection(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run drift detection on staged files.
        
        Args:
            files: List of file paths to validate
            
        Returns:
            Drift detection report or None if no spec file
        """
        # Check if spec file exists
        spec_path = Path('.kiro/specs/app.yaml')
        if not spec_path.exists():
            return {
                'aligned': True,
                'message': 'No spec file found, skipping drift detection',
                'files_validated': [],
                'files_skipped': files,
                'total_issues': 0,
                'issues_by_file': {},
                'all_suggestions': []
            }
        
        # Import and run drift detector
        from backend.drift_detector import MultiFileValidator
        
        validator = MultiFileValidator(str(spec_path))
        result = validator.validate_staged_changes(files)
        
        return result
    
    def _run_test_coverage_validation(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run test coverage validation on staged files.
        
        Args:
            files: List of file paths to validate
            
        Returns:
            Test coverage report
        """
        # Import and run test coverage detector
        from backend.test_analyzer import TestCoverageDetector
        
        spec_path = Path('.kiro/specs/app.yaml')
        spec_path_str = str(spec_path) if spec_path.exists() else None
        
        detector = TestCoverageDetector(project_root=".", spec_path=spec_path_str)
        report = detector.validate_staged_changes(files)
        
        return report.to_dict()
    
    def _run_documentation_validation(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run documentation validation on staged files.
        
        Args:
            files: List of file paths to validate
            
        Returns:
            Documentation validation report
        """
        # Import and run documentation alignment detector
        from backend.doc_analyzer import DocumentationAlignmentDetector
        
        spec_path = Path('.kiro/specs/app.yaml')
        spec_path_str = str(spec_path) if spec_path.exists() else None
        
        detector = DocumentationAlignmentDetector(project_root=".", spec_path=spec_path_str)
        report = detector.validate_staged_changes(files)
        
        return report.to_dict()
    
    def _run_bridge_validation(self) -> Optional[Dict[str, Any]]:
        """
        Run bridge validation to check API contract drift.
        
        Returns:
            Bridge validation report or None if bridge not configured
        """
        # Check if bridge is configured
        bridge_config_path = Path('.kiro/settings/bridge.json')
        if not bridge_config_path.exists():
            return {
                'enabled': False,
                'message': 'Bridge not configured',
                'has_issues': False,
                'issues': []
            }
        
        # Import bridge drift detector
        from backend.bridge_drift_detector import BridgeDriftDetector, generate_drift_report
        
        try:
            # Create detector and check all dependencies
            detector = BridgeDriftDetector(repo_root=".")
            drift_results = detector.detect_all_drift()
            
            # Aggregate results
            all_issues = []
            total_errors = 0
            total_warnings = 0
            
            for dep_name, issues in drift_results.items():
                for issue in issues:
                    all_issues.append({
                        'dependency': dep_name,
                        'type': issue.type,
                        'severity': issue.severity,
                        'endpoint': issue.endpoint,
                        'method': issue.method,
                        'location': issue.location,
                        'message': issue.message,
                        'suggestion': issue.suggestion
                    })
                    
                    if issue.severity == 'error':
                        total_errors += 1
                    elif issue.severity == 'warning':
                        total_warnings += 1
            
            has_issues = len(all_issues) > 0
            
            return {
                'enabled': True,
                'has_issues': has_issues,
                'total_issues': len(all_issues),
                'errors': total_errors,
                'warnings': total_warnings,
                'issues': all_issues,
                'dependencies_checked': list(drift_results.keys()),
                'message': f"Checked {len(drift_results)} dependencies" if not has_issues else f"Found {len(all_issues)} contract drift issue(s)"
            }
            
        except Exception as e:
            # If bridge validation fails, don't block the commit
            return {
                'enabled': True,
                'has_issues': False,
                'error': str(e),
                'message': f'Bridge validation error: {str(e)}'
            }

    
    def _aggregate_validation_results(self, 
                                     drift_report: Optional[Dict[str, Any]],
                                     test_report: Optional[Dict[str, Any]],
                                     doc_report: Optional[Dict[str, Any]],
                                     bridge_report: Optional[Dict[str, Any]] = None,
                                     validation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Aggregate results from all validation steps.
        
        Args:
            drift_report: Drift detection report
            test_report: Test coverage report
            doc_report: Documentation validation report
            bridge_report: Bridge contract validation report
            validation_context: Optional validation context with file information
            
        Returns:
            Aggregated validation result
        """
        # Check if any validation failed
        has_drift = drift_report and not drift_report.get('aligned', True)
        has_test_issues = test_report and test_report.get('has_issues', False)
        has_doc_issues = doc_report and doc_report.get('has_issues', False)
        has_bridge_issues = bridge_report and bridge_report.get('has_issues', False)
        
        success = not (has_drift or has_test_issues or has_doc_issues or has_bridge_issues)
        
        # Count total issues
        total_issues = 0
        all_issues = []
        
        if drift_report:
            total_issues += drift_report.get('total_issues', 0)
            # Collect drift issues
            for file, issues in drift_report.get('issues_by_file', {}).items():
                all_issues.extend(issues)
        if test_report:
            total_issues += len(test_report.get('issues', []))
            all_issues.extend(test_report.get('issues', []))
        if doc_report:
            total_issues += len(doc_report.get('issues', []))
            all_issues.extend(doc_report.get('issues', []))
        if bridge_report:
            total_issues += bridge_report.get('total_issues', 0)
            all_issues.extend(bridge_report.get('issues', []))
        
        # Generate message
        if success:
            message = "All validations passed - commit can proceed"
        else:
            issue_parts = []
            if has_drift:
                issue_parts.append(f"{drift_report.get('total_issues', 0)} drift issue(s)")
            if has_test_issues:
                issue_parts.append(f"{len(test_report.get('issues', []))} test coverage issue(s)")
            if has_doc_issues:
                issue_parts.append(f"{len(doc_report.get('issues', []))} documentation issue(s)")
            if has_bridge_issues:
                issue_parts.append(f"{bridge_report.get('total_issues', 0)} contract drift issue(s)")
            
            message = f"Validation failed: {', '.join(issue_parts)} detected"
        
        result = {
            'success': success,
            'message': message,
            'allowCommit': success,
            'total_issues': total_issues,
            'has_drift': has_drift,
            'has_test_issues': has_test_issues,
            'has_doc_issues': has_doc_issues,
            'has_bridge_issues': has_bridge_issues
        }
        
        # Detect rule-drift conflicts if rule engine is available
        if self.rule_engine and validation_context:
            filtered_files = validation_context.get('filtered_files', [])
            all_files = validation_context.get('all_staged_files', [])
            
            conflicts = self.rule_engine.detect_rule_drift_conflicts(
                all_issues, filtered_files, all_files
            )
            
            # Apply alignment priority over rules
            if conflicts:
                result = self.rule_engine.prioritize_alignment_over_rules(conflicts, result)
        
        return result
    
    def _generate_suggestions(self,
                            drift_report: Optional[Dict[str, Any]],
                            test_report: Optional[Dict[str, Any]],
                            doc_report: Optional[Dict[str, Any]],
                            bridge_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate suggestions for fixing validation issues.
        
        Args:
            drift_report: Drift detection report
            test_report: Test coverage report
            doc_report: Documentation validation report
            bridge_report: Bridge contract validation report
            
        Returns:
            Prioritized suggestions report
        """
        # Import suggestion generator
        from backend.suggestion_generator import ComprehensiveSuggestionGenerator
        
        spec_path = Path('.kiro/specs/app.yaml')
        spec_path_str = str(spec_path) if spec_path.exists() else None
        
        generator = ComprehensiveSuggestionGenerator(spec_path=spec_path_str)
        
        # Generate suggestions from reports
        suggestions = generator.generate_suggestions_from_reports(
            drift_report=drift_report,
            test_report=test_report,
            doc_report=doc_report
        )
        
        # Add bridge-specific suggestions if there are bridge issues
        if bridge_report and bridge_report.get('has_issues', False):
            bridge_suggestions = self._generate_bridge_suggestions(bridge_report)
            if 'ordered_suggestions' in suggestions:
                suggestions['ordered_suggestions'].extend(bridge_suggestions)
            else:
                suggestions['ordered_suggestions'] = bridge_suggestions
            
            # Update summary
            if 'summary' in suggestions:
                suggestions['summary']['total_suggestions'] = len(suggestions['ordered_suggestions'])
        
        # Apply minimal change policy if rule engine is available
        if self.rule_engine and 'ordered_suggestions' in suggestions:
            suggestions['ordered_suggestions'] = self.rule_engine.apply_minimal_change_policy(
                suggestions['ordered_suggestions']
            )
        
        return suggestions
    
    def _generate_bridge_suggestions(self, bridge_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate suggestions for bridge contract drift issues.
        
        Args:
            bridge_report: Bridge validation report
            
        Returns:
            List of suggestion dictionaries
        """
        suggestions = []
        
        for issue in bridge_report.get('issues', []):
            suggestion = {
                'type': 'bridge',
                'priority': 2,  # Medium priority
                'description': f"[{issue['dependency']}] {issue['message']}",
                'file': issue.get('location', '').split(':')[0] if ':' in issue.get('location', '') else '',
                'suggestion': issue.get('suggestion', ''),
                'details': {
                    'dependency': issue['dependency'],
                    'endpoint': issue['endpoint'],
                    'method': issue['method'],
                    'severity': issue['severity']
                }
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    def get_timing_summary(self) -> str:
        """
        Get a human-readable summary of timing data.
        
        Returns:
            Formatted timing summary string
        """
        if not self.timing_data:
            return "No timing data available"
        
        lines = ["Validation Performance Summary:"]
        lines.append("-" * 40)
        
        # Sort by time (longest first)
        sorted_steps = sorted(
            [(k, v) for k, v in self.timing_data.items() if k != 'total'],
            key=lambda x: x[1],
            reverse=True
        )
        
        for step, duration in sorted_steps:
            step_name = step.replace('_', ' ').title()
            lines.append(f"  {step_name}: {duration:.3f}s")
        
        lines.append("-" * 40)
        total = self.timing_data.get('total', 0)
        lines.append(f"  Total: {total:.3f}s")
        
        # Add warning if close to timeout
        if total > self.timeout_seconds * 0.8:
            lines.append(f"  ⚠ Warning: Approaching timeout limit ({self.timeout_seconds}s)")
        
        return "\n".join(lines)



class ValidationResult:
    """Structured validation result."""
    
    def __init__(self, success: bool, message: str, allow_commit: bool,
                 drift_report: Optional[Dict[str, Any]] = None,
                 test_report: Optional[Dict[str, Any]] = None,
                 doc_report: Optional[Dict[str, Any]] = None,
                 bridge_report: Optional[Dict[str, Any]] = None,
                 suggestions: Optional[Dict[str, Any]] = None,
                 timing: Optional[Dict[str, float]] = None,
                 timed_out: bool = False,
                 partial_results: bool = False,
                 staging_area_preserved: bool = True,
                 staging_area_error: Optional[str] = None):
        """
        Initialize a validation result.
        
        Args:
            success: Whether validation passed
            message: Human-readable message
            allow_commit: Whether to allow the commit
            drift_report: Optional drift detection report
            test_report: Optional test coverage report
            doc_report: Optional documentation report
            bridge_report: Optional bridge contract validation report
            suggestions: Optional suggestions for fixing issues
            timing: Optional timing data for performance monitoring
            timed_out: Whether validation exceeded timeout
            partial_results: Whether results are partial due to timeout
            staging_area_preserved: Whether staging area remained unchanged
            staging_area_error: Error message if staging area was modified
        """
        self.success = success
        self.message = message
        self.allow_commit = allow_commit
        self.drift_report = drift_report
        self.test_report = test_report
        self.doc_report = doc_report
        self.bridge_report = bridge_report
        self.suggestions = suggestions
        self.timing = timing or {}
        self.timed_out = timed_out
        self.partial_results = partial_results
        self.staging_area_preserved = staging_area_preserved
        self.staging_area_error = staging_area_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        result = {
            'success': self.success,
            'message': self.message,
            'allowCommit': self.allow_commit,
            'drift_report': self.drift_report,
            'test_report': self.test_report,
            'doc_report': self.doc_report,
            'bridge_report': self.bridge_report,
            'suggestions': self.suggestions,
            'timing': self.timing,
            'timed_out': self.timed_out,
            'partial_results': self.partial_results,
            'staging_area_preserved': self.staging_area_preserved
        }
        
        if self.staging_area_error:
            result['staging_area_error'] = self.staging_area_error
        
        return result
    
    def format_for_display(self) -> str:
        """Format the result as human-readable text."""
        lines = []
        
        # Add header
        if self.success:
            lines.append("✓ VALIDATION PASSED")
        else:
            lines.append("✗ VALIDATION FAILED")
        
        # Add timeout warning if applicable
        if self.timed_out:
            lines.append("⚠ TIMEOUT - Partial results returned")
        
        # Add staging area error if applicable
        if not self.staging_area_preserved:
            lines.append("⚠ CRITICAL: Staging area was modified during validation")
            if self.staging_area_error:
                lines.append(f"   {self.staging_area_error}")
        
        lines.append("")
        lines.append(self.message)
        lines.append("")
        
        # Add timing information
        if self.timing:
            lines.append("--- Performance ---")
            total_time = self.timing.get('total', 0)
            lines.append(f"Total validation time: {total_time:.3f}s")
            
            # Show breakdown of major steps
            if 'drift_detection' in self.timing:
                lines.append(f"  Drift detection: {self.timing['drift_detection']:.3f}s")
            if 'test_coverage' in self.timing:
                lines.append(f"  Test coverage: {self.timing['test_coverage']:.3f}s")
            if 'documentation' in self.timing:
                lines.append(f"  Documentation: {self.timing['documentation']:.3f}s")
            lines.append("")
        
        # Add drift report summary
        if self.drift_report and not self.drift_report.get('aligned', True):
            lines.append("--- Drift Issues ---")
            lines.append(f"Total drift issues: {self.drift_report.get('total_issues', 0)}")
            for file, issues in self.drift_report.get('issues_by_file', {}).items():
                if issues:
                    lines.append(f"  {file}: {len(issues)} issue(s)")
            lines.append("")
        
        # Add test report summary
        if self.test_report and self.test_report.get('has_issues', False):
            lines.append("--- Test Coverage Issues ---")
            lines.append(f"Total test issues: {len(self.test_report.get('issues', []))}")
            lines.append("")
        
        # Add doc report summary
        if self.doc_report and self.doc_report.get('has_issues', False):
            lines.append("--- Documentation Issues ---")
            lines.append(f"Total documentation issues: {len(self.doc_report.get('issues', []))}")
            lines.append("")
        
        # Add bridge report summary
        if self.bridge_report and self.bridge_report.get('enabled', False):
            if self.bridge_report.get('has_issues', False):
                lines.append("--- Bridge Contract Drift ---")
                lines.append(f"Total contract drift issues: {self.bridge_report.get('total_issues', 0)}")
                deps = self.bridge_report.get('dependencies_checked', [])
                if deps:
                    lines.append(f"Dependencies checked: {', '.join(deps)}")
                lines.append("")
            else:
                deps = self.bridge_report.get('dependencies_checked', [])
                if deps:
                    lines.append("--- Bridge Contract Status ---")
                    lines.append(f"✓ All API calls align with contracts ({len(deps)} dependencies)")
                    lines.append("")
        
        # Add suggestions (only if not timed out)
        if not self.timed_out and self.suggestions and self.suggestions.get('summary', {}).get('total_suggestions', 0) > 0:
            lines.append("--- Suggestions ---")
            
            from backend.suggestion_generator import ComprehensiveSuggestionGenerator
            generator = ComprehensiveSuggestionGenerator()
            formatted_suggestions = generator.format_suggestions_for_display(self.suggestions)
            lines.append(formatted_suggestions)
        
        return "\n".join(lines)
