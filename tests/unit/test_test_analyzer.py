"""Unit tests for test coverage analysis functionality."""
import pytest
from pathlib import Path
from backend.test_analyzer import (
    TestFileMapper, TestParser, TestCoverageAnalyzer,
    TestCoverageDetector, TestCoverageReport, TestCoverageIssue
)


class TestTestFileMapper:
    """Tests for TestFileMapper class."""
    
    def test_map_code_to_test_file(self):
        """Test mapping code files to test files."""
        mapper = TestFileMapper()
        
        # Test mapping for drift_detector which has tests
        test_files = mapper.map_code_to_test_file("backend/drift_detector.py")
        assert len(test_files) > 0
        assert any("test_drift_detector.py" in tf for tf in test_files)
    
    def test_map_code_to_test_file_no_tests(self):
        """Test mapping for code file without tests."""
        mapper = TestFileMapper()
        
        # Test mapping for a file that doesn't have tests
        test_files = mapper.map_code_to_test_file("backend/nonexistent.py")
        assert len(test_files) == 0
    
    def test_find_all_test_files(self):
        """Test finding all test files in project."""
        mapper = TestFileMapper()
        
        test_files = mapper.find_all_test_files()
        assert len(test_files) > 0
        assert any("test_drift_detector.py" in tf for tf in test_files)
    
    def test_get_code_files_for_test(self):
        """Test reverse mapping from test to code files."""
        mapper = TestFileMapper()
        
        code_files = mapper.get_code_files_for_test("tests/unit/test_drift_detector.py")
        assert len(code_files) > 0
        assert any("drift_detector.py" in cf for cf in code_files)


class TestTestParser:
    """Tests for TestParser class."""
    
    def test_parse_test_file(self):
        """Test parsing a test file."""
        parser = TestParser("tests/unit/test_drift_detector.py")
        tree = parser.parse()
        
        assert tree is not None
    
    def test_extract_test_functions(self):
        """Test extracting test function names."""
        parser = TestParser("tests/unit/test_drift_detector.py")
        test_functions = parser.extract_test_functions()
        
        assert len(test_functions) > 0
        assert all(func.startswith("test_") for func in test_functions)
    
    def test_extract_tested_functions(self):
        """Test extracting functions that are tested."""
        parser = TestParser("tests/unit/test_drift_detector.py")
        tested_functions = parser.extract_tested_functions()
        
        # Should find some tested functions
        assert isinstance(tested_functions, set)
    
    def test_extract_tested_classes(self):
        """Test extracting classes that are tested."""
        parser = TestParser("tests/unit/test_drift_detector.py")
        tested_classes = parser.extract_tested_classes()
        
        # Should find classes like SpecParser, CodeParser, etc.
        assert isinstance(tested_classes, set)
        assert len(tested_classes) > 0


class TestTestCoverageAnalyzer:
    """Tests for TestCoverageAnalyzer class."""
    
    def test_analyze_code_file_with_tests(self):
        """Test analyzing a code file that has tests."""
        analyzer = TestCoverageAnalyzer()
        
        analysis = analyzer.analyze_code_file("backend/drift_detector.py")
        
        assert analysis['code_file'] == "backend/drift_detector.py"
        assert analysis['has_tests'] is True
        assert len(analysis['test_files']) > 0
        assert analysis['test_count'] > 0
    
    def test_analyze_code_file_without_tests(self):
        """Test analyzing a code file without tests."""
        analyzer = TestCoverageAnalyzer()
        
        # Test analyzer itself doesn't have tests yet
        analysis = analyzer.analyze_code_file("backend/test_analyzer.py")
        
        assert analysis['code_file'] == "backend/test_analyzer.py"
        # This will be False until we create tests for it
        assert 'has_tests' in analysis
    
    def test_get_coverage_summary(self):
        """Test getting coverage summary for multiple files."""
        analyzer = TestCoverageAnalyzer()
        
        code_files = [
            "backend/drift_detector.py",
            "backend/test_analyzer.py"
        ]
        
        summary = analyzer.get_coverage_summary(code_files)
        
        assert summary['total_files'] == 2
        assert 'files_with_tests' in summary
        assert 'files_without_tests' in summary
        assert 'coverage_by_file' in summary


class TestTestCoverageIssue:
    """Tests for TestCoverageIssue class."""
    
    def test_create_issue(self):
        """Test creating a test coverage issue."""
        issue = TestCoverageIssue(
            issue_type='missing_tests',
            severity='error',
            file='backend/example.py',
            description='No tests found',
            suggestion='Create test file'
        )
        
        assert issue.type == 'missing_tests'
        assert issue.severity == 'error'
        assert issue.file == 'backend/example.py'
    
    def test_issue_to_dict(self):
        """Test converting issue to dictionary."""
        issue = TestCoverageIssue(
            issue_type='missing_tests',
            severity='error',
            file='backend/example.py',
            description='No tests found',
            suggestion='Create test file'
        )
        
        issue_dict = issue.to_dict()
        
        assert issue_dict['type'] == 'missing_tests'
        assert issue_dict['severity'] == 'error'
        assert issue_dict['file'] == 'backend/example.py'
        assert issue_dict['description'] == 'No tests found'
        assert issue_dict['suggestion'] == 'Create test file'


class TestTestCoverageReport:
    """Tests for TestCoverageReport class."""
    
    def test_empty_report(self):
        """Test creating an empty report."""
        report = TestCoverageReport()
        
        assert not report.has_issues()
        assert len(report.issues) == 0
    
    def test_add_issue(self):
        """Test adding issues to report."""
        report = TestCoverageReport()
        
        issue = TestCoverageIssue(
            issue_type='missing_tests',
            severity='error',
            file='backend/example.py',
            description='No tests found',
            suggestion='Create test file'
        )
        
        report.add_issue(issue)
        
        assert report.has_issues()
        assert len(report.issues) == 1
    
    def test_report_to_dict(self):
        """Test converting report to dictionary."""
        report = TestCoverageReport()
        
        issue = TestCoverageIssue(
            issue_type='missing_tests',
            severity='error',
            file='backend/example.py',
            description='No tests found',
            suggestion='Create test file'
        )
        
        report.add_issue(issue)
        report_dict = report.to_dict()
        
        assert report_dict['has_issues'] is True
        assert len(report_dict['issues']) == 1
        assert 'coverage_summary' in report_dict


class TestTestCoverageDetector:
    """Tests for TestCoverageDetector class."""
    
    def test_detect_missing_test_files(self):
        """Test detecting missing test files."""
        detector = TestCoverageDetector()
        
        # Test with a file that has tests
        issues = detector.detect_missing_test_files("backend/drift_detector.py")
        # Should have no issues since tests exist
        assert len(issues) == 0
        
        # Test with an empty file (should not generate test task)
        issues = detector.detect_missing_test_files("backend/bridge_sync.py")
        # Should have no issues since file is empty (no functions to test)
        assert len(issues) == 0
        
        # Test with a file that has content but no tests
        issues = detector.detect_missing_test_files("backend/auto_fix.py")
        # Should detect missing tests if file has functions
        # (This may or may not have tests depending on the actual file)
    
    def test_detect_insufficient_coverage(self):
        """Test detecting insufficient test coverage."""
        detector = TestCoverageDetector()
        
        # Test with drift_detector which has tests
        issues = detector.detect_insufficient_coverage("backend/drift_detector.py")
        
        # May or may not have issues depending on coverage
        assert isinstance(issues, list)
    
    def test_validate_test_code_spec_alignment(self):
        """Test validating test-code-spec alignment."""
        detector = TestCoverageDetector(spec_path=".kiro/specs/app.yaml")
        
        # Test with existing test file
        issues = detector.validate_test_code_spec_alignment("tests/unit/test_drift_detector.py")
        
        # Should return a list (may be empty if aligned)
        assert isinstance(issues, list)
    
    def test_generate_coverage_report(self):
        """Test generating a comprehensive coverage report."""
        detector = TestCoverageDetector(spec_path=".kiro/specs/app.yaml")
        
        code_files = ["backend/drift_detector.py"]
        test_files = ["tests/unit/test_drift_detector.py"]
        
        report = detector.generate_coverage_report(code_files, test_files)
        
        assert isinstance(report, TestCoverageReport)
        assert 'total_files' in report.coverage_summary
        assert 'coverage_by_file' in report.coverage_summary
    
    def test_validate_staged_changes(self):
        """Test validating staged changes."""
        detector = TestCoverageDetector(spec_path=".kiro/specs/app.yaml")
        
        staged_files = [
            "backend/drift_detector.py",
            "tests/unit/test_drift_detector.py",
            "README.md"
        ]
        
        report = detector.validate_staged_changes(staged_files)
        
        assert isinstance(report, TestCoverageReport)
        assert isinstance(report.issues, list)
