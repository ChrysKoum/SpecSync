"""
Unit tests for Bridge Drift Detector.
"""
import pytest
from pathlib import Path
import tempfile
import shutil
import json

from backend.bridge_drift_detector import (
    BridgeDriftDetector,
    APICall,
    detect_drift,
    detect_all_drift,
    generate_drift_report,
    format_drift_report
)
from backend.bridge_models import (
    Contract,
    Endpoint,
    BridgeConfig,
    Dependency,
    DriftIssue
)


class TestAPICall:
    """Test APICall data class."""
    
    def test_api_call_creation(self):
        """Test creating an APICall."""
        call = APICall(
            method="GET",
            path="/users",
            file_path="backend/client.py",
            line_number=42
        )
        
        assert call.method == "GET"
        assert call.path == "/users"
        assert call.file_path == "backend/client.py"
        assert call.line_number == 42
    
    def test_api_call_str(self):
        """Test APICall string representation."""
        call = APICall(
            method="POST",
            path="/users",
            file_path="backend/client.py",
            line_number=10
        )
        
        assert str(call) == "POST /users at backend/client.py:10"


class TestBridgeDriftDetector:
    """Test BridgeDriftDetector class."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)
        
        # Create directory structure
        (repo_path / ".kiro/settings").mkdir(parents=True, exist_ok=True)
        (repo_path / ".kiro/contracts").mkdir(parents=True, exist_ok=True)
        (repo_path / "backend").mkdir(parents=True, exist_ok=True)
        
        yield repo_path
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_config(self, temp_repo):
        """Create a sample bridge configuration."""
        config_path = temp_repo / ".kiro/settings/bridge.json"
        config_data = {
            "bridge": {
                "enabled": True,
                "role": "consumer",
                "repo_id": "test-repo",
                "provides": {},
                "dependencies": {
                    "backend": {
                        "name": "backend",
                        "type": "http-api",
                        "sync_method": "git",
                        "git_url": "https://github.com/test/backend.git",
                        "contract_path": ".kiro/contracts/provided-api.yaml",
                        "local_cache": ".kiro/contracts/backend-api.yaml",
                        "sync_on_commit": True
                    }
                }
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        return config_path
    
    @pytest.fixture
    def sample_contract(self, temp_repo):
        """Create a sample contract."""
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(
                    id="get-users",
                    path="/users",
                    method="GET",
                    status="implemented"
                ),
                Endpoint(
                    id="get-user",
                    path="/users/{id}",
                    method="GET",
                    status="implemented"
                ),
                Endpoint(
                    id="create-user",
                    path="/users",
                    method="POST",
                    status="implemented"
                )
            ]
        )
        
        contract_path = temp_repo / ".kiro/contracts/backend-api.yaml"
        contract.save_to_yaml(str(contract_path))
        
        return contract
    
    def test_detector_initialization(self, temp_repo, sample_config):
        """Test detector initialization."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        assert detector.repo_root == temp_repo
        assert detector.config is not None
    
    def test_extract_path_from_url(self, temp_repo, sample_config):
        """Test URL path extraction."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # Full URL
        assert detector._extract_path_from_url("http://api.example.com/users") == "/users"
        
        # Path only
        assert detector._extract_path_from_url("/users") == "/users"
        
        # Without leading slash
        assert detector._extract_path_from_url("users") == "/users"
        
        # With path parameters
        assert detector._extract_path_from_url("/users/{id}") == "/users/{id}"
        
        # With query parameters
        assert detector._extract_path_from_url("/users?page=1") == "/users"
    
    def test_normalize_path(self, temp_repo, sample_config):
        """Test path normalization."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # Different parameter names should normalize to same path
        assert detector._normalize_path("/users/{id}") == "/users/{param}"
        assert detector._normalize_path("/users/{user_id}") == "/users/{param}"
        assert detector._normalize_path("/users/{userId}") == "/users/{param}"
        
        # Multiple parameters
        assert detector._normalize_path("/users/{id}/posts/{post_id}") == "/users/{param}/posts/{param}"
    
    def test_paths_match(self, temp_repo, sample_config):
        """Test path matching."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # Exact match
        assert detector._paths_match("/users", "/users")
        
        # Normalized parameters match
        path1 = detector._normalize_path("/users/{id}")
        path2 = detector._normalize_path("/users/{user_id}")
        assert detector._paths_match(path1, path2)
        
        # Different paths don't match
        assert not detector._paths_match("/users", "/posts")
    
    def test_detect_drift_missing_dependency(self, temp_repo, sample_config):
        """Test drift detection with missing dependency."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        issues = detector.detect_drift("nonexistent")
        
        assert len(issues) == 1
        assert issues[0].type == "configuration_error"
        assert issues[0].severity == "error"
        assert "not found" in issues[0].message
    
    def test_detect_drift_missing_contract(self, temp_repo, sample_config):
        """Test drift detection with missing contract file."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        issues = detector.detect_drift("backend")
        
        assert len(issues) == 1
        assert issues[0].type == "missing_contract"
        assert issues[0].severity == "error"
    
    def test_detect_drift_with_valid_contract(self, temp_repo, sample_config, sample_contract):
        """Test drift detection with valid contract but no API calls."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # No Python files with API calls, so no drift
        issues = detector.detect_drift("backend")
        
        assert len(issues) == 0
    
    def test_check_endpoint_exists_match(self, temp_repo, sample_config, sample_contract):
        """Test endpoint matching."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # Load contract
        contract = sample_contract
        
        # API call that matches
        api_call = APICall(
            method="GET",
            path="/users",
            file_path="backend/client.py",
            line_number=10
        )
        
        issue = detector._check_endpoint_exists(api_call, contract)
        assert issue is None  # No drift
    
    def test_check_endpoint_exists_no_match(self, temp_repo, sample_config, sample_contract):
        """Test endpoint not matching."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        # Load contract
        contract = sample_contract
        
        # API call that doesn't match
        api_call = APICall(
            method="DELETE",
            path="/users",
            file_path="backend/client.py",
            line_number=10
        )
        
        issue = detector._check_endpoint_exists(api_call, contract)
        assert issue is not None
        assert issue.type == "missing_endpoint"
        assert issue.severity == "error"
        assert issue.method == "DELETE"
        assert issue.endpoint == "/users"
    
    def test_generate_suggestion_similar_endpoint(self, temp_repo, sample_config, sample_contract):
        """Test suggestion generation for similar endpoints."""
        detector = BridgeDriftDetector(str(temp_repo))
        
        contract = sample_contract
        
        # Wrong method
        api_call = APICall(
            method="DELETE",
            path="/users",
            file_path="backend/client.py",
            line_number=10
        )
        
        suggestion = detector._generate_suggestion(api_call, contract)
        assert "GET" in suggestion or "POST" in suggestion


class TestDriftReporting:
    """Test drift reporting functions."""
    
    def test_generate_drift_report_no_issues(self):
        """Test generating report with no issues."""
        report = generate_drift_report("backend", [])
        
        assert report.dependency_name == "backend"
        assert report.total_issues == 0
        assert report.errors == 0
        assert report.warnings == 0
        assert report.success is True
        assert "align" in report.message.lower()
    
    def test_generate_drift_report_with_issues(self):
        """Test generating report with issues."""
        issues = [
            DriftIssue(
                type="missing_endpoint",
                severity="error",
                endpoint="/users",
                method="DELETE",
                location="backend/client.py:10",
                message="Endpoint not found",
                suggestion="Check contract"
            ),
            DriftIssue(
                type="parameter_mismatch",
                severity="warning",
                endpoint="/users",
                method="POST",
                location="backend/client.py:20",
                message="Parameter mismatch",
                suggestion="Update parameters"
            )
        ]
        
        report = generate_drift_report("backend", issues)
        
        assert report.dependency_name == "backend"
        assert report.total_issues == 2
        assert report.errors == 1
        assert report.warnings == 1
        assert report.success is False
    
    def test_format_drift_report_success(self):
        """Test formatting successful report."""
        report = generate_drift_report("backend", [])
        formatted = format_drift_report(report)
        
        assert "backend" in formatted
        assert "SUCCESS" in formatted
        assert "Total Issues: 0" in formatted
    
    def test_format_drift_report_with_issues(self):
        """Test formatting report with issues."""
        issues = [
            DriftIssue(
                type="missing_endpoint",
                severity="error",
                endpoint="/users",
                method="DELETE",
                location="backend/client.py:10",
                message="Endpoint not found",
                suggestion="Check contract"
            )
        ]
        
        report = generate_drift_report("backend", issues)
        formatted = format_drift_report(report)
        
        assert "backend" in formatted
        assert "DRIFT DETECTED" in formatted
        assert "Total Issues: 1" in formatted
        assert "ERROR" in formatted
        assert "missing_endpoint" in formatted
        assert "DELETE /users" in formatted


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)
        
        # Create directory structure
        (repo_path / ".kiro/settings").mkdir(parents=True, exist_ok=True)
        (repo_path / ".kiro/contracts").mkdir(parents=True, exist_ok=True)
        
        # Create config
        config_path = repo_path / ".kiro/settings/bridge.json"
        config_data = {
            "bridge": {
                "enabled": True,
                "role": "consumer",
                "repo_id": "test-repo",
                "provides": {},
                "dependencies": {}
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        yield repo_path
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_detect_drift_function(self, temp_repo):
        """Test detect_drift convenience function."""
        issues = detect_drift("backend", str(temp_repo))
        
        # Should return configuration error since dependency doesn't exist
        assert len(issues) == 1
        assert issues[0].type == "configuration_error"
    
    def test_detect_all_drift_function(self, temp_repo):
        """Test detect_all_drift convenience function."""
        results = detect_all_drift(str(temp_repo))
        
        # Should return empty dict since no dependencies configured
        assert isinstance(results, dict)
        assert len(results) == 0
