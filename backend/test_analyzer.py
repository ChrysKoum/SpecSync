"""
Test coverage analysis module for SpecSync.

This module provides functionality to analyze test coverage by mapping
code files to their corresponding test files and extracting tested functions.
"""
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


class TestFileMapper:
    """Maps code files to their corresponding test files using naming conventions."""
    
    def __init__(self, project_root: str = "."):
        """
        Initialize the test file mapper.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
    
    def map_code_to_test_file(self, code_file: str) -> List[str]:
        """
        Map a code file to its corresponding test file(s).
        
        Uses naming conventions to find test files:
        - backend/handlers/user.py -> tests/unit/test_user.py
        - backend/module.py -> tests/unit/test_module.py
        
        Args:
            code_file: Path to the code file
            
        Returns:
            List of potential test file paths (may be empty if no tests exist)
        """
        code_path = Path(code_file)
        
        # Extract the module name from the code file
        module_name = code_path.stem  # e.g., "user" from "user.py"
        
        # Generate potential test file names
        test_file_patterns = [
            f"test_{module_name}.py",
            f"{module_name}_test.py"
        ]
        
        # Search in test directories
        test_locations = [
            self.test_dir / "unit",
            self.test_dir / "integration",
            self.test_dir / "property"
        ]
        
        found_test_files = []
        
        for test_dir in test_locations:
            if not test_dir.exists():
                continue
            
            for pattern in test_file_patterns:
                test_file = test_dir / pattern
                if test_file.exists():
                    found_test_files.append(str(test_file))
        
        return found_test_files
    
    def find_all_test_files(self) -> List[str]:
        """
        Find all test files in the project.
        
        Returns:
            List of all test file paths
        """
        test_files = []
        
        if not self.test_dir.exists():
            return test_files
        
        # Search recursively for test files
        for test_file in self.test_dir.rglob("test_*.py"):
            test_files.append(str(test_file))
        
        for test_file in self.test_dir.rglob("*_test.py"):
            test_files.append(str(test_file))
        
        return test_files
    
    def get_code_files_for_test(self, test_file: str) -> List[str]:
        """
        Reverse mapping: find code files that a test file should cover.
        
        Args:
            test_file: Path to the test file
            
        Returns:
            List of code file paths that should be tested
        """
        test_path = Path(test_file)
        test_name = test_path.stem
        
        # Extract module name from test file name
        # test_user.py -> user
        # user_test.py -> user
        if test_name.startswith("test_"):
            module_name = test_name[5:]  # Remove "test_" prefix
        elif test_name.endswith("_test"):
            module_name = test_name[:-5]  # Remove "_test" suffix
        else:
            module_name = test_name
        
        # Search for corresponding code files
        code_locations = [
            self.project_root / "backend" / "handlers" / f"{module_name}.py",
            self.project_root / "backend" / f"{module_name}.py"
        ]
        
        found_code_files = []
        for code_file in code_locations:
            if code_file.exists():
                found_code_files.append(str(code_file))
        
        return found_code_files


class TestParser:
    """Parser for test files to extract tested functions and coverage information."""
    
    def __init__(self, test_file: str):
        """
        Initialize the test parser.
        
        Args:
            test_file: Path to the test file
        """
        self.test_file = Path(test_file)
        self.tree: Optional[ast.AST] = None
    
    def parse(self) -> ast.AST:
        """
        Parse the test file into an AST.
        
        Returns:
            AST representation of the test file
            
        Raises:
            FileNotFoundError: If test file doesn't exist
            SyntaxError: If test file has invalid Python syntax
        """
        if not self.test_file.exists():
            raise FileNotFoundError(f"Test file not found: {self.test_file}")
        
        with open(self.test_file, 'r') as f:
            code = f.read()
        
        self.tree = ast.parse(code, filename=str(self.test_file))
        return self.tree
    
    def extract_tested_functions(self) -> Set[str]:
        """
        Extract names of functions that are tested in this test file.
        
        This analyzes:
        - Function calls within test functions
        - Imported functions from the module being tested
        
        Returns:
            Set of function names that are tested
        """
        if self.tree is None:
            self.parse()
        
        tested_functions = set()
        imported_functions = self._extract_imports()
        
        # Find all test functions
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if it's a test function
                if node.name.startswith('test_'):
                    # Extract function calls within this test
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            func_name = self._get_function_name(child)
                            if func_name and func_name in imported_functions:
                                tested_functions.add(func_name)
        
        return tested_functions
    
    def _extract_imports(self) -> Set[str]:
        """
        Extract all imported function names from the test file.
        
        Returns:
            Set of imported function names
        """
        if self.tree is None:
            self.parse()
        
        imports = set()
        
        for node in ast.walk(self.tree):
            # Handle: from module import function
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.add(alias.name)
            
            # Handle: import module (we'll track the module name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
        
        return imports
    
    def _get_function_name(self, call_node: ast.Call) -> Optional[str]:
        """
        Extract the function name from a Call node.
        
        Args:
            call_node: AST Call node
            
        Returns:
            Function name if extractable, None otherwise
        """
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        return None
    
    def extract_test_functions(self) -> List[str]:
        """
        Extract all test function names from the test file.
        
        Returns:
            List of test function names
        """
        if self.tree is None:
            self.parse()
        
        test_functions = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('test_'):
                    test_functions.append(node.name)
        
        return test_functions
    
    def extract_tested_classes(self) -> Set[str]:
        """
        Extract names of classes that are tested in this test file.
        
        Returns:
            Set of class names that are tested
        """
        if self.tree is None:
            self.parse()
        
        tested_classes = set()
        imported_classes = self._extract_imported_classes()
        
        # Find instantiations and method calls on imported classes
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in imported_classes:
                    tested_classes.add(node.func.id)
        
        return tested_classes
    
    def _extract_imported_classes(self) -> Set[str]:
        """
        Extract all imported class names from the test file.
        
        Returns:
            Set of imported class names
        """
        if self.tree is None:
            self.parse()
        
        classes = set()
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    # Heuristic: class names typically start with uppercase
                    if alias.name and alias.name[0].isupper():
                        classes.add(alias.name)
        
        return classes


class TestCoverageAnalyzer:
    """Main analyzer that combines mapping and parsing to assess test coverage."""
    
    def __init__(self, project_root: str = "."):
        """
        Initialize the test coverage analyzer.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.mapper = TestFileMapper(project_root)
    
    def analyze_code_file(self, code_file: str) -> Dict[str, Any]:
        """
        Analyze test coverage for a specific code file.
        
        Args:
            code_file: Path to the code file
            
        Returns:
            Dictionary containing coverage analysis results
        """
        # Find corresponding test files
        test_files = self.mapper.map_code_to_test_file(code_file)
        
        if not test_files:
            return {
                'code_file': code_file,
                'has_tests': False,
                'test_files': [],
                'tested_functions': set(),
                'test_count': 0
            }
        
        # Analyze each test file
        all_tested_functions = set()
        all_tested_classes = set()
        total_test_count = 0
        
        for test_file in test_files:
            try:
                parser = TestParser(test_file)
                tested_functions = parser.extract_tested_functions()
                tested_classes = parser.extract_tested_classes()
                test_functions = parser.extract_test_functions()
                
                all_tested_functions.update(tested_functions)
                all_tested_classes.update(tested_classes)
                total_test_count += len(test_functions)
            except Exception as e:
                # Skip test files that can't be parsed
                continue
        
        return {
            'code_file': code_file,
            'has_tests': True,
            'test_files': test_files,
            'tested_functions': all_tested_functions,
            'tested_classes': all_tested_classes,
            'test_count': total_test_count
        }
    
    def get_coverage_summary(self, code_files: List[str]) -> Dict[str, Any]:
        """
        Get a summary of test coverage across multiple code files.
        
        Args:
            code_files: List of code file paths
            
        Returns:
            Summary of test coverage
        """
        summary = {
            'total_files': len(code_files),
            'files_with_tests': 0,
            'files_without_tests': 0,
            'coverage_by_file': {}
        }
        
        for code_file in code_files:
            analysis = self.analyze_code_file(code_file)
            summary['coverage_by_file'][code_file] = analysis
            
            if analysis['has_tests']:
                summary['files_with_tests'] += 1
            else:
                summary['files_without_tests'] += 1
        
        return summary



class TestCoverageIssue:
    """Represents a test coverage issue detected during validation."""
    
    def __init__(self, issue_type: str, severity: str, file: str, 
                 description: str, suggestion: str):
        """
        Initialize a test coverage issue.
        
        Args:
            issue_type: Type of issue ('missing_tests', 'insufficient_coverage', 'misalignment')
            severity: Severity level ('error', 'warning')
            file: File where issue was detected
            description: Human-readable description of the issue
            suggestion: Suggested fix for the issue
        """
        self.type = issue_type
        self.severity = severity
        self.file = file
        self.description = description
        self.suggestion = suggestion
    
    def to_dict(self) -> Dict[str, str]:
        """Convert the issue to a dictionary."""
        return {
            'type': self.type,
            'severity': self.severity,
            'file': self.file,
            'description': self.description,
            'suggestion': self.suggestion
        }


class TestCoverageReport:
    """Structured report of test coverage issues."""
    
    def __init__(self):
        """Initialize an empty test coverage report."""
        self.issues: List[TestCoverageIssue] = []
        self.coverage_summary: Dict[str, Any] = {}
    
    def add_issue(self, issue: TestCoverageIssue):
        """Add a test coverage issue to the report."""
        self.issues.append(issue)
    
    def has_issues(self) -> bool:
        """Check if there are any coverage issues."""
        return len(self.issues) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the report to a dictionary."""
        return {
            'has_issues': self.has_issues(),
            'issues': [issue.to_dict() for issue in self.issues],
            'coverage_summary': self.coverage_summary
        }


class TestCoverageDetector:
    """Detects test coverage issues for code changes."""
    
    def __init__(self, project_root: str = ".", spec_path: Optional[str] = None):
        """
        Initialize the test coverage detector.
        
        Args:
            project_root: Root directory of the project
            spec_path: Optional path to spec file for spec alignment checks
        """
        self.project_root = Path(project_root)
        self.analyzer = TestCoverageAnalyzer(project_root)
        self.spec_path = spec_path
        
        # Import spec parser if spec path provided
        if spec_path:
            from backend.drift_detector import SpecParser
            self.spec_parser = SpecParser(spec_path)
            self.spec_parser.parse()
        else:
            self.spec_parser = None
    
    def detect_missing_test_files(self, code_file: str) -> List[TestCoverageIssue]:
        """
        Detect if a code file is missing corresponding test files.
        
        Args:
            code_file: Path to the code file
            
        Returns:
            List of test coverage issues for missing test files
        """
        issues = []
        
        # Analyze the code file
        analysis = self.analyzer.analyze_code_file(code_file)
        
        if not analysis['has_tests']:
            issue = TestCoverageIssue(
                issue_type='missing_tests',
                severity='error',
                file=code_file,
                description=f"No test file found for {code_file}",
                suggestion=f"Create a test file for {code_file} following naming conventions (e.g., tests/unit/test_{{module}}.py)"
            )
            issues.append(issue)
        
        return issues
    
    def detect_insufficient_coverage(self, code_file: str) -> List[TestCoverageIssue]:
        """
        Detect if test coverage is insufficient for new functionality.
        
        This checks if:
        - Functions in the code file are tested
        - Classes in the code file are tested
        - The number of tests seems reasonable for the code complexity
        
        Args:
            code_file: Path to the code file
            
        Returns:
            List of test coverage issues for insufficient coverage
        """
        issues = []
        
        # Analyze test coverage
        analysis = self.analyzer.analyze_code_file(code_file)
        
        if not analysis['has_tests']:
            # Already handled by detect_missing_test_files
            return issues
        
        # Parse the code file to get functions and classes
        from backend.drift_detector import CodeParser
        code_parser = CodeParser(code_file)
        code_parser.parse()
        
        code_functions = set(code_parser.extract_functions())
        tested_functions = analysis['tested_functions']
        
        # Find untested functions (excluding private functions and __init__)
        public_functions = {f for f in code_functions if not f.startswith('_') or f == '__init__'}
        untested_functions = public_functions - tested_functions
        
        if untested_functions:
            issue = TestCoverageIssue(
                issue_type='insufficient_coverage',
                severity='warning',
                file=code_file,
                description=f"Functions in {code_file} lack test coverage: {', '.join(sorted(untested_functions))}",
                suggestion=f"Add tests for untested functions in {', '.join(analysis['test_files'])}"
            )
            issues.append(issue)
        
        # Check if test count is very low
        if analysis['test_count'] == 0:
            issue = TestCoverageIssue(
                issue_type='insufficient_coverage',
                severity='error',
                file=code_file,
                description=f"Test file exists but contains no test functions for {code_file}",
                suggestion=f"Add test functions to {', '.join(analysis['test_files'])}"
            )
            issues.append(issue)
        
        return issues
    
    def validate_test_code_spec_alignment(self, test_file: str) -> List[TestCoverageIssue]:
        """
        Validate that tests align with both code implementation and spec requirements.
        
        This checks:
        - Tests exist for functionality defined in spec
        - Tests cover the actual code implementation
        - Tests don't test non-existent functionality
        
        Args:
            test_file: Path to the test file
            
        Returns:
            List of test coverage issues for alignment problems
        """
        issues = []
        
        # Find the corresponding code file
        code_files = self.analyzer.mapper.get_code_files_for_test(test_file)
        
        if not code_files:
            issue = TestCoverageIssue(
                issue_type='misalignment',
                severity='warning',
                file=test_file,
                description=f"Test file {test_file} has no corresponding code file",
                suggestion="Ensure test file naming matches code file naming conventions"
            )
            issues.append(issue)
            return issues
        
        # Parse the test file
        test_parser = TestParser(test_file)
        test_parser.parse()
        tested_functions = test_parser.extract_tested_functions()
        
        # Parse the code file
        from backend.drift_detector import CodeParser
        for code_file in code_files:
            code_parser = CodeParser(code_file)
            code_parser.parse()
            code_functions = set(code_parser.extract_functions())
            
            # Check if tests reference non-existent functions
            non_existent = tested_functions - code_functions
            if non_existent:
                issue = TestCoverageIssue(
                    issue_type='misalignment',
                    severity='warning',
                    file=test_file,
                    description=f"Tests reference functions that don't exist in {code_file}: {', '.join(sorted(non_existent))}",
                    suggestion=f"Update tests to match current code implementation or implement missing functions"
                )
                issues.append(issue)
            
            # If spec is available, check spec alignment
            if self.spec_parser:
                spec_endpoints = self.spec_parser.get_endpoints()
                code_endpoints = code_parser.extract_endpoints()
                
                # Check if all spec endpoints have tests
                for spec_endpoint in spec_endpoints:
                    if spec_endpoint.get('tests_required', False):
                        # Check if this endpoint is in the code
                        endpoint_in_code = any(
                            ce['path'] == spec_endpoint['path'] and 
                            ce['method'] == spec_endpoint['method']
                            for ce in code_endpoints
                        )
                        
                        if endpoint_in_code:
                            # Endpoint exists in code, should have tests
                            # This is a simplified check - in practice, we'd need more sophisticated analysis
                            test_functions = test_parser.extract_test_functions()
                            
                            # Heuristic: look for test function names that might test this endpoint
                            endpoint_path_parts = spec_endpoint['path'].strip('/').split('/')
                            endpoint_keywords = [part for part in endpoint_path_parts if not part.startswith('{')]
                            
                            has_test = any(
                                any(keyword in test_func.lower() for keyword in endpoint_keywords)
                                for test_func in test_functions
                            )
                            
                            if not has_test and endpoint_keywords:
                                issue = TestCoverageIssue(
                                    issue_type='misalignment',
                                    severity='warning',
                                    file=test_file,
                                    description=f"Spec requires tests for {spec_endpoint['method']} {spec_endpoint['path']}, but no matching test found",
                                    suggestion=f"Add test for {spec_endpoint['method']} {spec_endpoint['path']} endpoint"
                                )
                                issues.append(issue)
        
        return issues
    
    def generate_coverage_report(self, code_files: List[str], test_files: Optional[List[str]] = None) -> TestCoverageReport:
        """
        Generate a comprehensive test coverage report.
        
        Args:
            code_files: List of code files to check
            test_files: Optional list of test files to validate alignment
            
        Returns:
            TestCoverageReport with all detected issues
        """
        report = TestCoverageReport()
        
        # Get coverage summary
        report.coverage_summary = self.analyzer.get_coverage_summary(code_files)
        
        # Detect issues for each code file
        for code_file in code_files:
            # Check for missing test files
            missing_issues = self.detect_missing_test_files(code_file)
            for issue in missing_issues:
                report.add_issue(issue)
            
            # Check for insufficient coverage
            coverage_issues = self.detect_insufficient_coverage(code_file)
            for issue in coverage_issues:
                report.add_issue(issue)
        
        # Validate test-code-spec alignment for test files
        if test_files:
            for test_file in test_files:
                alignment_issues = self.validate_test_code_spec_alignment(test_file)
                for issue in alignment_issues:
                    report.add_issue(issue)
        
        return report
    
    def validate_staged_changes(self, staged_files: List[str]) -> TestCoverageReport:
        """
        Validate test coverage for staged changes.
        
        This is the main entry point for commit-time test coverage validation.
        
        Args:
            staged_files: List of staged file paths
            
        Returns:
            TestCoverageReport with coverage validation results
        """
        # Separate code files and test files
        code_files = [f for f in staged_files if f.endswith('.py') and f.startswith('backend/') and not 'test' in f]
        test_files = [f for f in staged_files if f.endswith('.py') and 'test' in f]
        
        # Generate comprehensive report
        return self.generate_coverage_report(code_files, test_files)
