"""
Bridge Drift Detector for API call validation.

This module detects drift between consumer API calls and provider contracts.
It extracts API calls from Python code and validates them against cached contracts.
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from backend.bridge_models import Contract, DriftIssue, BridgeConfig, load_contract_from_yaml


@dataclass
class APICall:
    """Represents an API call found in consumer code."""
    method: str  # HTTP method (GET, POST, etc.)
    path: str  # Endpoint path
    file_path: str  # Source file
    line_number: int  # Line number in source file
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.method} {self.path} at {self.file_path}:{self.line_number}"


class BridgeDriftDetector:
    """
    Detects drift between consumer API calls and provider contracts.
    
    This class:
    - Extracts API calls from Python code (requests, httpx, aiohttp)
    - Validates calls against cached contracts
    - Generates drift reports with suggestions
    - Tracks usage locations
    """
    
    def __init__(self, repo_root: str = "."):
        """
        Initialize drift detector.
        
        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = Path(repo_root)
        self.config = BridgeConfig(config_path=str(self.repo_root / ".kiro/settings/bridge.json"))
        self.config.load()

    def detect_drift(self, dependency_name: str) -> List[DriftIssue]:
        """
        Detect drift for a specific dependency.
        
        Args:
            dependency_name: Name of the dependency to check
            
        Returns:
            List of drift issues
        """
        # Load the cached contract for this dependency
        dependency = self.config.get_dependency(dependency_name)
        if not dependency:
            return [DriftIssue(
                type="configuration_error",
                severity="error",
                endpoint="",
                method="",
                location="",
                message=f"Dependency '{dependency_name}' not found in configuration",
                suggestion="Add the dependency using 'specsync bridge add-dependency'"
            )]
        
        cache_path = self.repo_root / dependency.local_cache
        if not cache_path.exists():
            return [DriftIssue(
                type="missing_contract",
                severity="error",
                endpoint="",
                method="",
                location="",
                message=f"Contract file not found: {dependency.local_cache}",
                suggestion="Run 'specsync bridge sync' to fetch the contract"
            )]
        
        try:
            contract = load_contract_from_yaml(str(cache_path))
        except Exception as e:
            return [DriftIssue(
                type="invalid_contract",
                severity="error",
                endpoint="",
                method="",
                location="",
                message=f"Failed to load contract: {str(e)}",
                suggestion="Check contract file format or re-sync"
            )]
        
        # Find all API calls in consumer code
        api_calls = self._find_api_calls_in_code()
        
        # Check each API call against the contract
        issues = []
        for api_call in api_calls:
            issue = self._check_endpoint_exists(api_call, contract)
            if issue:
                issues.append(issue)
        
        return issues
    
    def detect_all_drift(self) -> Dict[str, List[DriftIssue]]:
        """
        Detect drift for all configured dependencies.
        
        Returns:
            Dictionary mapping dependency names to their drift issues
        """
        results = {}
        
        for dep_name in self.config.list_dependencies():
            issues = self.detect_drift(dep_name)
            results[dep_name] = issues
        
        return results
    
    def validate_all(self) -> List['DriftReport']:
        """
        Validate against all contracts and generate reports.
        
        Returns:
            List of drift reports for all dependencies
        """
        drift_results = self.detect_all_drift()
        reports = []
        
        for dep_name, issues in drift_results.items():
            report = generate_drift_report(dep_name, issues)
            reports.append(report)
        
        return reports
    
    def _find_api_calls_in_code(self, file_patterns: Optional[List[str]] = None) -> List[APICall]:
        """
        Find API calls in Python code.
        
        Supports:
        - requests library (requests.get, requests.post, etc.)
        - httpx library (httpx.get, httpx.post, client.get, etc.)
        - aiohttp library (session.get, session.post, etc.)
        
        Args:
            file_patterns: List of glob patterns for files to search (default: all .py files)
            
        Returns:
            List of API calls found
        """
        if file_patterns is None:
            file_patterns = ["**/*.py"]
        
        api_calls = []
        
        # Find all Python files matching patterns
        python_files = []
        for pattern in file_patterns:
            python_files.extend(self.repo_root.glob(pattern))
        
        # Extract API calls from each file
        for file_path in python_files:
            # Skip test files and virtual environments
            if 'test' in str(file_path) or '.venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
            
            try:
                calls = self._extract_api_calls_from_file(file_path)
                api_calls.extend(calls)
            except Exception:
                # Skip files that can't be parsed
                continue
        
        return api_calls
    
    def _extract_api_calls_from_file(self, file_path: Path) -> List[APICall]:
        """
        Extract API calls from a single Python file using AST.
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of API calls found in the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        
        api_calls = []
        
        # Visit all function calls in the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = self._parse_api_call(node, file_path)
                if call:
                    api_calls.append(call)
        
        return api_calls
    
    def _parse_api_call(self, node: ast.Call, file_path: Path) -> Optional[APICall]:
        """
        Parse an AST Call node to extract API call information.
        
        Handles patterns like:
        - requests.get(url)
        - httpx.post(url)
        - client.get(url)
        - session.post(url)
        
        Args:
            node: AST Call node
            file_path: Source file path
            
        Returns:
            APICall if this is an HTTP API call, None otherwise
        """
        # Check if this is an attribute call (e.g., requests.get)
        if not isinstance(node.func, ast.Attribute):
            return None
        
        method_name = node.func.attr.upper()
        
        # Check if method is an HTTP method
        http_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if method_name not in http_methods:
            return None
        
        # Check if the object is a known HTTP library
        if isinstance(node.func.value, ast.Name):
            lib_name = node.func.value.id
            if lib_name not in ['requests', 'httpx', 'client', 'session']:
                return None
        elif isinstance(node.func.value, ast.Attribute):
            # Handle cases like httpx.AsyncClient().get
            return None
        else:
            return None
        
        # Extract URL from first argument
        if not node.args:
            return None
        
        url_arg = node.args[0]
        url = self._extract_url_from_node(url_arg)
        
        if not url:
            return None
        
        # Extract path from URL (remove base URL if present)
        path = self._extract_path_from_url(url)
        
        return APICall(
            method=method_name,
            path=path,
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=node.lineno
        )
    
    def _extract_url_from_node(self, node: ast.AST) -> Optional[str]:
        """
        Extract URL string from an AST node.
        
        Handles:
        - String literals: "http://api.example.com/users"
        - f-strings: f"http://api.example.com/users/{id}"
        - String concatenation: base_url + "/users"
        
        Args:
            node: AST node
            
        Returns:
            URL string if extractable, None otherwise
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        
        if isinstance(node, ast.JoinedStr):
            # f-string - try to extract the static parts
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                else:
                    parts.append("{}")
            return "".join(parts)
        
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # String concatenation
            left = self._extract_url_from_node(node.left)
            right = self._extract_url_from_node(node.right)
            if left and right:
                return left + right
        
        return None
    
    def _extract_path_from_url(self, url: str) -> str:
        """
        Extract path from URL.
        
        Examples:
        - "http://api.example.com/users" -> "/users"
        - "/users" -> "/users"
        - "users" -> "/users"
        - "/users/{id}" -> "/users/{id}"
        
        Args:
            url: Full or partial URL
            
        Returns:
            Path component
        """
        # Remove protocol and domain if present
        if '://' in url:
            url = url.split('://', 1)[1]
            if '/' in url:
                url = '/' + url.split('/', 1)[1]
            else:
                url = '/'
        
        # Ensure path starts with /
        if not url.startswith('/'):
            url = '/' + url
        
        # Remove query parameters and fragments
        url = url.split('?')[0].split('#')[0]
        
        return url
    
    def _check_endpoint_exists(self, api_call: APICall, contract: Contract) -> Optional[DriftIssue]:
        """
        Check if an API call matches an endpoint in the contract.
        
        Args:
            api_call: API call to validate
            contract: Contract to validate against
            
        Returns:
            DriftIssue if endpoint doesn't exist, None if it matches
        """
        # Normalize the path for comparison
        call_path = self._normalize_path(api_call.path)
        
        # Check each endpoint in the contract
        for endpoint in contract.endpoints:
            endpoint_path = self._normalize_path(endpoint.path)
            
            # Check if path and method match
            if self._paths_match(call_path, endpoint_path) and api_call.method == endpoint.method:
                # Match found - no drift
                return None
        
        # No match found - create drift issue
        return DriftIssue(
            type="missing_endpoint",
            severity="error",
            endpoint=api_call.path,
            method=api_call.method,
            location=f"{api_call.file_path}:{api_call.line_number}",
            message=f"API call to {api_call.method} {api_call.path} does not match any endpoint in contract",
            suggestion=self._generate_suggestion(api_call, contract)
        )
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize a path for comparison.
        
        Converts path parameters to a standard format:
        - /users/{id} -> /users/{param}
        - /users/{user_id} -> /users/{param}
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized path
        """
        # Replace all path parameters with {param}
        normalized = re.sub(r'\{[^}]+\}', '{param}', path)
        return normalized
    
    def _paths_match(self, path1: str, path2: str) -> bool:
        """
        Check if two paths match (considering path parameters).
        
        Args:
            path1: First path
            path2: Second path
            
        Returns:
            True if paths match, False otherwise
        """
        return path1 == path2
    
    def _generate_suggestion(self, api_call: APICall, contract: Contract) -> str:
        """
        Generate a helpful suggestion for fixing drift.
        
        Args:
            api_call: API call that caused drift
            contract: Contract being validated against
            
        Returns:
            Suggestion string
        """
        # Find similar endpoints
        similar = []
        call_path_parts = api_call.path.strip('/').split('/')
        
        for endpoint in contract.endpoints:
            endpoint_path_parts = endpoint.path.strip('/').split('/')
            
            # Check if paths have similar structure
            if len(call_path_parts) == len(endpoint_path_parts):
                matches = sum(1 for a, b in zip(call_path_parts, endpoint_path_parts) 
                             if a == b or '{' in b)
                if matches >= len(call_path_parts) - 1:
                    similar.append(f"{endpoint.method} {endpoint.path}")
        
        if similar:
            return f"Did you mean one of these endpoints? {', '.join(similar)}"
        
        # Check if method is wrong
        for endpoint in contract.endpoints:
            if self._paths_match(
                self._normalize_path(api_call.path),
                self._normalize_path(endpoint.path)
            ):
                return f"Endpoint path exists but method is {endpoint.method}, not {api_call.method}"
        
        return "Either sync the latest contract or remove this API call"


def detect_drift(dependency_name: str, repo_root: str = ".") -> List[DriftIssue]:
    """
    Convenience function to detect drift for a dependency.
    
    Args:
        dependency_name: Name of dependency to check
        repo_root: Repository root directory
        
    Returns:
        List of drift issues
    """
    detector = BridgeDriftDetector(repo_root)
    return detector.detect_drift(dependency_name)


def detect_all_drift(repo_root: str = ".") -> Dict[str, List[DriftIssue]]:
    """
    Convenience function to detect drift for all dependencies.
    
    Args:
        repo_root: Repository root directory
        
    Returns:
        Dictionary mapping dependency names to drift issues
    """
    detector = BridgeDriftDetector(repo_root)
    return detector.detect_all_drift()


@dataclass
class DriftReport:
    """Formatted drift report with statistics."""
    dependency_name: str
    total_issues: int
    errors: int
    warnings: int
    issues: List[DriftIssue]
    success: bool
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'dependency_name': self.dependency_name,
            'total_issues': self.total_issues,
            'errors': self.errors,
            'warnings': self.warnings,
            'issues': [issue.to_dict() for issue in self.issues],
            'success': self.success,
            'message': self.message
        }


def generate_drift_report(dependency_name: str, issues: List[DriftIssue]) -> DriftReport:
    """
    Generate a formatted drift report.
    
    Args:
        dependency_name: Name of the dependency
        issues: List of drift issues
        
    Returns:
        Formatted drift report
    """
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    
    if not issues:
        return DriftReport(
            dependency_name=dependency_name,
            total_issues=0,
            errors=0,
            warnings=0,
            issues=[],
            success=True,
            message=f"✓ All API calls align with {dependency_name} contract"
        )
    
    return DriftReport(
        dependency_name=dependency_name,
        total_issues=len(issues),
        errors=errors,
        warnings=warnings,
        issues=issues,
        success=False,
        message=f"✗ Found {len(issues)} drift issue(s) with {dependency_name} contract"
    )


def format_drift_report(report: DriftReport) -> str:
    """
    Format a drift report as a human-readable string.
    
    Args:
        report: Drift report to format
        
    Returns:
        Formatted string
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"Drift Report: {report.dependency_name}")
    lines.append(f"{'='*60}")
    lines.append(f"Status: {'✓ SUCCESS' if report.success else '✗ DRIFT DETECTED'}")
    lines.append(f"Total Issues: {report.total_issues}")
    
    if report.total_issues > 0:
        lines.append(f"  - Errors: {report.errors}")
        lines.append(f"  - Warnings: {report.warnings}")
        lines.append("")
        
        for i, issue in enumerate(report.issues, 1):
            lines.append(f"{i}. [{issue.severity.upper()}] {issue.type}")
            lines.append(f"   Endpoint: {issue.method} {issue.endpoint}")
            lines.append(f"   Location: {issue.location}")
            lines.append(f"   Message: {issue.message}")
            lines.append(f"   Suggestion: {issue.suggestion}")
            lines.append("")
    else:
        lines.append(f"\n{report.message}")
    
    lines.append(f"{'='*60}\n")
    return "\n".join(lines)
