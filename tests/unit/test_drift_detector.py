"""Unit tests for drift detection functionality."""
import pytest
from pathlib import Path
from backend.drift_detector import (
    SpecParser, CodeParser, DriftDetector, 
    AlignmentDetector, MultiFileValidator
)


class TestSpecParser:
    """Tests for SpecParser class."""
    
    def test_parse_spec_file(self):
        """Test parsing a valid spec file."""
        spec_path = ".kiro/specs/app.yaml"
        parser = SpecParser(spec_path)
        spec_data = parser.parse()
        
        assert spec_data is not None
        assert 'service' in spec_data
        assert 'endpoints' in spec_data
        assert 'models' in spec_data
    
    def test_get_endpoints(self):
        """Test extracting endpoints from spec."""
        spec_path = ".kiro/specs/app.yaml"
        parser = SpecParser(spec_path)
        endpoints = parser.get_endpoints()
        
        assert len(endpoints) > 0
        assert any(ep['path'] == '/users' for ep in endpoints)
    
    def test_get_models(self):
        """Test extracting models from spec."""
        spec_path = ".kiro/specs/app.yaml"
        parser = SpecParser(spec_path)
        models = parser.get_models()
        
        assert 'User' in models
        assert 'fields' in models['User']
    
    def test_get_endpoint_by_path_method(self):
        """Test finding specific endpoint."""
        spec_path = ".kiro/specs/app.yaml"
        parser = SpecParser(spec_path)
        endpoint = parser.get_endpoint_by_path_method('/users', 'GET')
        
        assert endpoint is not None
        assert endpoint['path'] == '/users'
        assert endpoint['method'] == 'GET'


class TestCodeParser:
    """Tests for CodeParser class."""
    
    def test_parse_code_file(self):
        """Test parsing a valid Python file."""
        code_path = "backend/handlers/user.py"
        parser = CodeParser(code_path)
        tree = parser.parse()
        
        assert tree is not None
    
    def test_extract_endpoints(self):
        """Test extracting endpoints from code."""
        code_path = "backend/handlers/user.py"
        parser = CodeParser(code_path)
        endpoints = parser.extract_endpoints()
        
        assert len(endpoints) > 0
        assert any(ep['path'] == '/users' and ep['method'] == 'GET' for ep in endpoints)
    
    def test_extract_functions(self):
        """Test extracting function names."""
        code_path = "backend/handlers/user.py"
        parser = CodeParser(code_path)
        functions = parser.extract_functions()
        
        assert 'list_users' in functions
        assert 'get_user' in functions
    
    def test_extract_models(self):
        """Test extracting Pydantic models."""
        code_path = "backend/models.py"
        parser = CodeParser(code_path)
        models = parser.extract_models()
        
        assert len(models) > 0
        assert any(m['name'] == 'User' for m in models)
        
        user_model = next(m for m in models if m['name'] == 'User')
        field_names = [f['name'] for f in user_model['fields']]
        assert 'id' in field_names
        assert 'username' in field_names
        assert 'email' in field_names


class TestDriftDetector:
    """Tests for DriftDetector class."""
    
    def test_compare_aligned_code(self):
        """Test comparing code that aligns with spec."""
        spec_path = ".kiro/specs/app.yaml"
        detector = DriftDetector(spec_path)
        
        # Test with user handler which should be aligned
        result = detector.compare_code_to_spec("backend/handlers/user.py")
        
        assert 'aligned' in result
        assert 'endpoint_drift' in result
        assert 'model_drift' in result
    
    def test_compare_models(self):
        """Test comparing models between spec and code."""
        spec_path = ".kiro/specs/app.yaml"
        detector = DriftDetector(spec_path)
        
        result = detector.compare_code_to_spec("backend/models.py")
        
        # User model should be aligned
        assert result['model_drift']['new_in_code'] == []
        assert result['model_drift']['removed_from_code'] == []


class TestAlignmentDetector:
    """Tests for AlignmentDetector class."""
    
    def test_generate_drift_report(self):
        """Test generating a complete drift report."""
        spec_path = ".kiro/specs/app.yaml"
        detector = AlignmentDetector(spec_path)
        
        report = detector.generate_drift_report("backend/handlers/user.py")
        
        assert report is not None
        assert hasattr(report, 'issues')
        assert hasattr(report, 'suggestions')
    
    def test_detect_new_functionality(self):
        """Test detecting new functionality not in spec."""
        spec_path = ".kiro/specs/app.yaml"
        detector = AlignmentDetector(spec_path)
        
        issues = detector.detect_new_functionality("backend/handlers/user.py")
        
        # Should return a list (may be empty if aligned)
        assert isinstance(issues, list)
    
    def test_detect_removed_functionality(self):
        """Test detecting removed functionality."""
        spec_path = ".kiro/specs/app.yaml"
        detector = AlignmentDetector(spec_path)
        
        issues = detector.detect_removed_functionality("backend/handlers/user.py")
        
        # Should return a list (may be empty if aligned)
        assert isinstance(issues, list)


class TestMultiFileValidator:
    """Tests for MultiFileValidator class."""
    
    def test_map_file_to_spec_section(self):
        """Test mapping files to spec sections."""
        spec_path = ".kiro/specs/app.yaml"
        validator = MultiFileValidator(spec_path)
        
        assert validator.map_file_to_spec_section("backend/handlers/user.py") == "endpoints"
        assert validator.map_file_to_spec_section("backend/models.py") == "models"
        assert validator.map_file_to_spec_section("backend/main.py") == "general"
        assert validator.map_file_to_spec_section("tests/test_user.py") is None
    
    def test_validate_multiple_files(self):
        """Test validating multiple files."""
        spec_path = ".kiro/specs/app.yaml"
        validator = MultiFileValidator(spec_path)
        
        files = ["backend/handlers/user.py", "backend/models.py"]
        result = validator.validate_multiple_files(files)
        
        assert 'aligned' in result
        assert 'files_validated' in result
        assert 'files_skipped' in result
        assert 'total_issues' in result
        assert 'issues_by_file' in result
    
    def test_validate_staged_changes(self):
        """Test validating staged changes."""
        spec_path = ".kiro/specs/app.yaml"
        validator = MultiFileValidator(spec_path)
        
        staged_files = [
            "backend/handlers/user.py",
            "backend/models.py",
            "README.md"  # Should be skipped
        ]
        
        result = validator.validate_staged_changes(staged_files)
        
        assert 'aligned' in result
        assert 'message' in result
        assert 'files_validated' in result
        assert len(result['files_validated']) == 2  # Only Python files
