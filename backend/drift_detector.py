"""
Drift detection module for SpecSync.

This module provides functionality to detect drift between specifications,
code implementations, and other artifacts.
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


class SpecParser:
    """Parser for YAML specification files."""
    
    def __init__(self, spec_path: str):
        """
        Initialize the spec parser.
        
        Args:
            spec_path: Path to the YAML spec file
        """
        self.spec_path = Path(spec_path)
        self.spec_data: Optional[Dict[str, Any]] = None
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the spec file and return structured data.
        
        Returns:
            Dictionary containing parsed spec data
            
        Raises:
            FileNotFoundError: If spec file doesn't exist
            yaml.YAMLError: If spec file has invalid YAML syntax
        """
        if not self.spec_path.exists():
            raise FileNotFoundError(f"Spec file not found: {self.spec_path}")
        
        with open(self.spec_path, 'r') as f:
            self.spec_data = yaml.safe_load(f)
        
        return self.spec_data
    
    def get_endpoints(self) -> List[Dict[str, Any]]:
        """
        Extract endpoint definitions from the spec.
        
        Returns:
            List of endpoint definitions
        """
        if self.spec_data is None:
            self.parse()
        
        return self.spec_data.get('endpoints', [])
    
    def get_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract model definitions from the spec.
        
        Returns:
            Dictionary of model definitions keyed by model name
        """
        if self.spec_data is None:
            self.parse()
        
        return self.spec_data.get('models', {})
    
    def get_endpoint_by_path_method(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Find an endpoint definition by path and method.
        
        Args:
            path: Endpoint path (e.g., "/users")
            method: HTTP method (e.g., "GET")
            
        Returns:
            Endpoint definition if found, None otherwise
        """
        endpoints = self.get_endpoints()
        for endpoint in endpoints:
            if endpoint.get('path') == path and endpoint.get('method') == method.upper():
                return endpoint
        return None


class CodeParser:
    """Parser for Python code files to extract endpoints and functions."""
    
    def __init__(self, code_path: str):
        """
        Initialize the code parser.
        
        Args:
            code_path: Path to the Python code file
        """
        self.code_path = Path(code_path)
        self.tree: Optional[ast.AST] = None
    
    def parse(self) -> ast.AST:
        """
        Parse the Python code file into an AST.
        
        Returns:
            AST representation of the code
            
        Raises:
            FileNotFoundError: If code file doesn't exist
            SyntaxError: If code has invalid Python syntax
        """
        if not self.code_path.exists():
            raise FileNotFoundError(f"Code file not found: {self.code_path}")
        
        with open(self.code_path, 'r') as f:
            code = f.read()
        
        self.tree = ast.parse(code, filename=str(self.code_path))
        return self.tree
    
    def extract_endpoints(self) -> List[Dict[str, Any]]:
        """
        Extract FastAPI endpoint definitions from the code.
        
        Returns:
            List of endpoint definitions with path, method, and function name
        """
        if self.tree is None:
            self.parse()
        
        endpoints = []
        
        for node in ast.walk(self.tree):
            # Check both FunctionDef and AsyncFunctionDef
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Look for FastAPI route decorators
                for decorator in node.decorator_list:
                    endpoint_info = self._extract_endpoint_from_decorator(decorator, node.name)
                    if endpoint_info:
                        endpoints.append(endpoint_info)
        
        return endpoints
    
    def _extract_endpoint_from_decorator(self, decorator: ast.expr, func_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract endpoint information from a decorator node.
        
        Args:
            decorator: AST decorator node
            func_name: Name of the decorated function
            
        Returns:
            Endpoint information if decorator is a route decorator, None otherwise
        """
        # Handle router.get("/path"), router.post("/path"), etc.
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                method = decorator.func.attr.upper()
                if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    # Extract path from first argument
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
                        return {
                            'path': path,
                            'method': method,
                            'function': func_name
                        }
        
        return None
    
    def extract_functions(self) -> List[str]:
        """
        Extract all function names from the code.
        
        Returns:
            List of function names
        """
        if self.tree is None:
            self.parse()
        
        functions = []
        for node in ast.walk(self.tree):
            # Check both FunctionDef and AsyncFunctionDef
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
        
        return functions
    
    def extract_models(self) -> List[Dict[str, Any]]:
        """
        Extract Pydantic model definitions from the code.
        
        Returns:
            List of model definitions with name and fields
        """
        if self.tree is None:
            self.parse()
        
        models = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Pydantic model (inherits from BaseModel)
                is_pydantic = any(
                    isinstance(base, ast.Name) and base.id == 'BaseModel'
                    for base in node.bases
                )
                
                if is_pydantic:
                    fields = self._extract_model_fields(node)
                    models.append({
                        'name': node.name,
                        'fields': fields
                    })
        
        return models
    
    def _extract_model_fields(self, class_node: ast.ClassDef) -> List[Dict[str, str]]:
        """
        Extract field definitions from a Pydantic model class.
        
        Args:
            class_node: AST class definition node
            
        Returns:
            List of field definitions with name and type
        """
        fields = []
        
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                field_name = node.target.id
                field_type = ast.unparse(node.annotation) if node.annotation else 'Any'
                fields.append({
                    'name': field_name,
                    'type': field_type
                })
        
        return fields


class DriftDetector:
    """Main drift detection class that compares code against specs."""
    
    def __init__(self, spec_path: str):
        """
        Initialize the drift detector.
        
        Args:
            spec_path: Path to the YAML spec file
        """
        self.spec_parser = SpecParser(spec_path)
        self.spec_parser.parse()
    
    def compare_code_to_spec(self, code_path: str) -> Dict[str, Any]:
        """
        Compare a code file against the spec and detect drift.
        
        Args:
            code_path: Path to the Python code file
            
        Returns:
            Dictionary containing drift analysis results
        """
        code_parser = CodeParser(code_path)
        code_parser.parse()
        
        # Extract endpoints from both spec and code
        spec_endpoints = self.spec_parser.get_endpoints()
        code_endpoints = code_parser.extract_endpoints()
        
        # Compare endpoints
        endpoint_drift = self._compare_endpoints(spec_endpoints, code_endpoints)
        
        # Extract models from both spec and code
        spec_models = self.spec_parser.get_models()
        code_models = code_parser.extract_models()
        
        # Compare models
        model_drift = self._compare_models(spec_models, code_models)
        
        # Aggregate results
        has_drift = bool(endpoint_drift['new_in_code'] or 
                        endpoint_drift['removed_from_code'] or
                        model_drift['new_in_code'] or
                        model_drift['removed_from_code'] or
                        model_drift['field_mismatches'])
        
        return {
            'aligned': not has_drift,
            'file': code_path,
            'endpoint_drift': endpoint_drift,
            'model_drift': model_drift
        }
    
    def _compare_endpoints(self, spec_endpoints: List[Dict[str, Any]], 
                          code_endpoints: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Compare endpoints between spec and code.
        
        Args:
            spec_endpoints: Endpoints defined in spec
            code_endpoints: Endpoints found in code
            
        Returns:
            Dictionary with new, removed, and modified endpoints
        """
        # Create sets for comparison
        spec_routes = {(ep['path'], ep['method']) for ep in spec_endpoints}
        code_routes = {(ep['path'], ep['method']) for ep in code_endpoints}
        
        # Find differences
        new_in_code = code_routes - spec_routes
        removed_from_code = spec_routes - code_routes
        
        return {
            'new_in_code': [{'path': path, 'method': method} for path, method in new_in_code],
            'removed_from_code': [{'path': path, 'method': method} for path, method in removed_from_code],
            'modified': []  # TODO: Detect behavior modifications
        }
    
    def _compare_models(self, spec_models: Dict[str, Dict[str, Any]], 
                       code_models: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare models between spec and code.
        
        Args:
            spec_models: Models defined in spec
            code_models: Models found in code
            
        Returns:
            Dictionary with new, removed, and field mismatches
        """
        spec_model_names = set(spec_models.keys())
        code_model_names = {model['name'] for model in code_models}
        
        new_in_code = code_model_names - spec_model_names
        removed_from_code = spec_model_names - code_model_names
        
        # Check field mismatches for models that exist in both
        field_mismatches = []
        for model_name in spec_model_names & code_model_names:
            spec_fields = {field['name'] for field in spec_models[model_name].get('fields', [])}
            code_model = next(m for m in code_models if m['name'] == model_name)
            code_fields = {field['name'] for field in code_model['fields']}
            
            if spec_fields != code_fields:
                field_mismatches.append({
                    'model': model_name,
                    'spec_fields': list(spec_fields),
                    'code_fields': list(code_fields),
                    'missing_in_code': list(spec_fields - code_fields),
                    'extra_in_code': list(code_fields - spec_fields)
                })
        
        return {
            'new_in_code': list(new_in_code),
            'removed_from_code': list(removed_from_code),
            'field_mismatches': field_mismatches
        }



class DriftIssue:
    """Represents a specific drift issue detected during validation."""
    
    def __init__(self, issue_type: str, severity: str, file: str, 
                 description: str, expected_behavior: str, actual_behavior: str):
        """
        Initialize a drift issue.
        
        Args:
            issue_type: Type of drift ('spec', 'test', 'doc')
            severity: Severity level ('error', 'warning')
            file: File where drift was detected
            description: Human-readable description of the issue
            expected_behavior: What was expected based on spec
            actual_behavior: What was found in the code
        """
        self.type = issue_type
        self.severity = severity
        self.file = file
        self.description = description
        self.expected_behavior = expected_behavior
        self.actual_behavior = actual_behavior
    
    def to_dict(self) -> Dict[str, str]:
        """Convert the issue to a dictionary."""
        return {
            'type': self.type,
            'severity': self.severity,
            'file': self.file,
            'description': self.description,
            'expected_behavior': self.expected_behavior,
            'actual_behavior': self.actual_behavior
        }


class DriftReport:
    """Structured report of all drift issues detected."""
    
    def __init__(self):
        """Initialize an empty drift report."""
        self.issues: List[DriftIssue] = []
        self.suggestions: List[str] = []
    
    def add_issue(self, issue: DriftIssue):
        """Add a drift issue to the report."""
        self.issues.append(issue)
    
    def add_suggestion(self, suggestion: str):
        """Add a suggestion for fixing drift."""
        self.suggestions.append(suggestion)
    
    def is_aligned(self) -> bool:
        """Check if there are any drift issues."""
        return len(self.issues) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a dictionary."""
        return {
            'aligned': self.is_aligned(),
            'issues': [issue.to_dict() for issue in self.issues],
            'suggestions': self.suggestions
        }


class AlignmentDetector:
    """Detects specific types of spec-code alignment issues."""
    
    def __init__(self, spec_path: str):
        """
        Initialize the alignment detector.
        
        Args:
            spec_path: Path to the YAML spec file
        """
        self.drift_detector = DriftDetector(spec_path)
    
    def detect_new_functionality(self, code_path: str) -> List[DriftIssue]:
        """
        Detect new functions/endpoints in code that are not in the spec.
        
        Args:
            code_path: Path to the Python code file
            
        Returns:
            List of drift issues for new functionality
        """
        comparison = self.drift_detector.compare_code_to_spec(code_path)
        issues = []
        
        # Check for new endpoints
        for endpoint in comparison['endpoint_drift']['new_in_code']:
            issue = DriftIssue(
                issue_type='spec',
                severity='error',
                file=code_path,
                description=f"New endpoint {endpoint['method']} {endpoint['path']} found in code but not defined in spec",
                expected_behavior="All endpoints should be defined in the spec before implementation",
                actual_behavior=f"Endpoint {endpoint['method']} {endpoint['path']} exists in code without spec definition"
            )
            issues.append(issue)
        
        # Check for new models
        for model_name in comparison['model_drift']['new_in_code']:
            issue = DriftIssue(
                issue_type='spec',
                severity='error',
                file=code_path,
                description=f"New model '{model_name}' found in code but not defined in spec",
                expected_behavior="All models should be defined in the spec before implementation",
                actual_behavior=f"Model '{model_name}' exists in code without spec definition"
            )
            issues.append(issue)
        
        return issues
    
    def detect_removed_functionality(self, code_path: str) -> List[DriftIssue]:
        """
        Detect functionality defined in spec but removed from code.
        
        Args:
            code_path: Path to the Python code file
            
        Returns:
            List of drift issues for removed functionality
        """
        comparison = self.drift_detector.compare_code_to_spec(code_path)
        issues = []
        
        # Check for removed endpoints
        for endpoint in comparison['endpoint_drift']['removed_from_code']:
            issue = DriftIssue(
                issue_type='spec',
                severity='error',
                file=code_path,
                description=f"Endpoint {endpoint['method']} {endpoint['path']} defined in spec but not found in code",
                expected_behavior=f"Endpoint {endpoint['method']} {endpoint['path']} should be implemented",
                actual_behavior="Endpoint is missing from code implementation"
            )
            issues.append(issue)
        
        # Check for removed models
        for model_name in comparison['model_drift']['removed_from_code']:
            issue = DriftIssue(
                issue_type='spec',
                severity='error',
                file=code_path,
                description=f"Model '{model_name}' defined in spec but not found in code",
                expected_behavior=f"Model '{model_name}' should be implemented",
                actual_behavior="Model is missing from code implementation"
            )
            issues.append(issue)
        
        return issues
    
    def detect_modified_behavior(self, code_path: str) -> List[DriftIssue]:
        """
        Detect modified behavior that differs from spec.
        
        Args:
            code_path: Path to the Python code file
            
        Returns:
            List of drift issues for modified behavior
        """
        comparison = self.drift_detector.compare_code_to_spec(code_path)
        issues = []
        
        # Check for field mismatches in models
        for mismatch in comparison['model_drift']['field_mismatches']:
            model_name = mismatch['model']
            
            if mismatch['missing_in_code']:
                issue = DriftIssue(
                    issue_type='spec',
                    severity='error',
                    file=code_path,
                    description=f"Model '{model_name}' is missing fields defined in spec: {', '.join(mismatch['missing_in_code'])}",
                    expected_behavior=f"Model should have fields: {', '.join(mismatch['spec_fields'])}",
                    actual_behavior=f"Model has fields: {', '.join(mismatch['code_fields'])}"
                )
                issues.append(issue)
            
            if mismatch['extra_in_code']:
                issue = DriftIssue(
                    issue_type='spec',
                    severity='error',
                    file=code_path,
                    description=f"Model '{model_name}' has extra fields not in spec: {', '.join(mismatch['extra_in_code'])}",
                    expected_behavior=f"Model should have fields: {', '.join(mismatch['spec_fields'])}",
                    actual_behavior=f"Model has fields: {', '.join(mismatch['code_fields'])}"
                )
                issues.append(issue)
        
        return issues
    
    def generate_drift_report(self, code_path: str) -> DriftReport:
        """
        Generate a complete drift report for a code file.
        
        Args:
            code_path: Path to the Python code file
            
        Returns:
            DriftReport containing all detected issues and suggestions
        """
        report = DriftReport()
        
        # Detect all types of drift
        new_functionality_issues = self.detect_new_functionality(code_path)
        removed_functionality_issues = self.detect_removed_functionality(code_path)
        modified_behavior_issues = self.detect_modified_behavior(code_path)
        
        # Add all issues to report
        for issue in new_functionality_issues + removed_functionality_issues + modified_behavior_issues:
            report.add_issue(issue)
        
        # Generate suggestions based on issues
        for issue in report.issues:
            if "not defined in spec" in issue.description:
                if "endpoint" in issue.description.lower():
                    report.add_suggestion(f"Add the endpoint definition to .kiro/specs/app.yaml")
                elif "model" in issue.description.lower():
                    report.add_suggestion(f"Add the model definition to .kiro/specs/app.yaml")
            elif "not found in code" in issue.description:
                if "endpoint" in issue.description.lower():
                    report.add_suggestion(f"Implement the endpoint in the code or remove it from the spec")
                elif "model" in issue.description.lower():
                    report.add_suggestion(f"Implement the model in the code or remove it from the spec")
            elif "missing fields" in issue.description:
                report.add_suggestion(f"Add the missing fields to the model implementation or update the spec")
            elif "extra fields" in issue.description:
                report.add_suggestion(f"Remove the extra fields from the model or add them to the spec")
        
        return report



class MultiFileValidator:
    """Validates multiple files against specs and aggregates drift reports."""
    
    def __init__(self, spec_path: str):
        """
        Initialize the multi-file validator.
        
        Args:
            spec_path: Path to the YAML spec file
        """
        self.spec_path = spec_path
        self.alignment_detector = AlignmentDetector(spec_path)
    
    def map_file_to_spec_section(self, file_path: str) -> Optional[str]:
        """
        Map a staged file to its corresponding spec section.
        
        Args:
            file_path: Path to the staged file
            
        Returns:
            Spec section identifier or None if no mapping exists
        """
        file_path = Path(file_path)
        
        # Map based on file location and type
        if file_path.match('backend/handlers/*.py'):
            return 'endpoints'
        elif file_path.match('backend/models.py'):
            return 'models'
        elif file_path.match('backend/*.py'):
            return 'general'
        
        # No spec mapping for this file
        return None
    
    def validate_multiple_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Validate multiple files and aggregate drift reports.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            Aggregated validation result with per-file reports
        """
        aggregated_report = {
            'aligned': True,
            'files_validated': [],
            'files_skipped': [],
            'total_issues': 0,
            'issues_by_file': {},
            'all_suggestions': []
        }
        
        for file_path in file_paths:
            # Check if file should be validated
            spec_section = self.map_file_to_spec_section(file_path)
            
            if spec_section is None:
                aggregated_report['files_skipped'].append({
                    'file': file_path,
                    'reason': 'No spec mapping for this file type'
                })
                continue
            
            # Skip non-Python files
            if not file_path.endswith('.py'):
                aggregated_report['files_skipped'].append({
                    'file': file_path,
                    'reason': 'Not a Python file'
                })
                continue
            
            # Validate the file
            try:
                file_report = self.validate_single_file(file_path)
                aggregated_report['files_validated'].append(file_path)
                
                # Add to aggregated results
                if not file_report.is_aligned():
                    aggregated_report['aligned'] = False
                    aggregated_report['issues_by_file'][file_path] = [
                        issue.to_dict() for issue in file_report.issues
                    ]
                    aggregated_report['total_issues'] += len(file_report.issues)
                    
                    # Add suggestions (deduplicate)
                    for suggestion in file_report.suggestions:
                        if suggestion not in aggregated_report['all_suggestions']:
                            aggregated_report['all_suggestions'].append(suggestion)
                else:
                    aggregated_report['issues_by_file'][file_path] = []
                    
            except Exception as e:
                aggregated_report['files_skipped'].append({
                    'file': file_path,
                    'reason': f'Validation error: {str(e)}'
                })
        
        return aggregated_report
    
    def validate_single_file(self, file_path: str) -> DriftReport:
        """
        Validate a single file against the spec.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            DriftReport for the file
        """
        return self.alignment_detector.generate_drift_report(file_path)
    
    def validate_staged_changes(self, staged_files: List[str]) -> Dict[str, Any]:
        """
        Validate all staged changes for a commit.
        
        This is the main entry point for commit-time validation.
        
        Args:
            staged_files: List of staged file paths
            
        Returns:
            Complete validation result with recommendations
        """
        # Filter to only Python files in backend
        python_files = [
            f for f in staged_files 
            if f.endswith('.py') and f.startswith('backend/')
        ]
        
        if not python_files:
            return {
                'aligned': True,
                'message': 'No backend Python files to validate',
                'files_validated': [],
                'files_skipped': staged_files,
                'total_issues': 0,
                'issues_by_file': {},
                'all_suggestions': []
            }
        
        # Validate all Python files
        result = self.validate_multiple_files(python_files)
        
        # Add summary message
        if result['aligned']:
            result['message'] = f"All {len(result['files_validated'])} files are aligned with spec"
        else:
            result['message'] = f"Drift detected in {len([f for f in result['issues_by_file'] if result['issues_by_file'][f]])} of {len(result['files_validated'])} files"
        
        return result
