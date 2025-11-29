"""
Unit tests for bridge breaking change detection.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from backend.bridge_breaking_changes import (
    BreakingChangeDetector,
    BreakingChange,
    detect_breaking_changes,
    format_breaking_changes
)
from backend.bridge_models import Contract, Endpoint


class TestBreakingChange:
    """Tests for BreakingChange dataclass."""
    
    def test_breaking_change_creation(self):
        """Test creating a breaking change."""
        change = BreakingChange(
            type="endpoint_removed",
            severity="error",
            endpoint="/users/{id}",
            method="GET",
            message="Endpoint was removed",
            affected_consumers=["frontend", "mobile"],
            suggestion="Notify consumers"
        )
        
        assert change.type == "endpoint_removed"
        assert change.severity == "error"
        assert len(change.affected_consumers) == 2
    
    def test_breaking_change_to_dict(self):
        """Test converting breaking change to dict."""
        change = BreakingChange(
            type="endpoint_modified",
            severity="warning",
            endpoint="/users",
            method="GET",
            message="Endpoint was modified",
            affected_consumers=["frontend"],
            suggestion="Check compatibility"
        )
        
        data = change.to_dict()
        
        assert data['type'] == "endpoint_modified"
        assert data['severity'] == "warning"
        assert data['affected_consumers'] == ["frontend"]


class TestBreakingChangeDetector:
    """Tests for BreakingChangeDetector class."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def detector(self, temp_repo):
        """Create a detector instance."""
        return BreakingChangeDetector(str(temp_repo))
    
    @pytest.fixture
    def old_contract(self):
        """Create an old contract with consumers."""
        return Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(
                    id="get-user",
                    path="/users/{id}",
                    method="GET",
                    consumers=["frontend", "mobile"]
                ),
                Endpoint(
                    id="list-users",
                    path="/users",
                    method="GET",
                    consumers=["frontend"]
                ),
                Endpoint(
                    id="unused-endpoint",
                    path="/admin/stats",
                    method="GET",
                    consumers=[]
                )
            ]
        )
    
    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert detector.repo_root.exists()
    
    def test_detect_removed_endpoint_with_consumers(self, detector, old_contract):
        """Test detecting removed endpoint that has consumers."""
        new_contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(
                    id="list-users",
                    path="/users",
                    method="GET",
                    consumers=["frontend"]
                )
            ]
        )
        
        changes = detector.detect_breaking_changes(old_contract, new_contract)
        
        # Should detect removed endpoint with consumers
        removed = [c for c in changes if c.type == "endpoint_removed"]
        assert len(removed) == 1
        assert removed[0].endpoint == "/users/{id}"
        assert removed[0].severity == "error"
        assert "frontend" in removed[0].affected_consumers
        assert "mobile" in removed[0].affected_consumers
    
    def test_detect_modified_endpoint_with_consumers(self, detector, old_contract):
        """Test detecting modified endpoint that has consumers."""
        new_contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(
                    id="get-user",
                    path="/users/{id}",
                    method="GET",
                    parameters=[{"name": "include_posts", "type": "boolean"}],  # Added parameter
                    consumers=["frontend", "mobile"]
                ),
                Endpoint(
                    id="list-users",
                    path="/users",
                    method="GET",
                    consumers=["frontend"]
                ),
                Endpoint(
                    id="unused-endpoint",
                    path="/admin/stats",
                    method="GET",
                    consumers=[]
                )
            ]
        )
        
        changes = detector.detect_breaking_changes(old_contract, new_contract)
        
        # Should detect modified endpoint with consumers
        modified = [c for c in changes if c.type == "endpoint_modified"]
        assert len(modified) == 1
        assert modified[0].endpoint == "/users/{id}"
        assert modified[0].severity == "warning"
        assert "frontend" in modified[0].affected_consumers
    
    def test_identify_unused_endpoints(self, detector, old_contract):
        """Test identifying endpoints with no consumers."""
        changes = detector.detect_breaking_changes(old_contract, old_contract)
        
        # Should identify unused endpoint
        unused = [c for c in changes if c.type == "unused_endpoint"]
        assert len(unused) == 1
        assert unused[0].endpoint == "/admin/stats"
        assert unused[0].severity == "info"
        assert len(unused[0].affected_consumers) == 0
    
    def test_no_breaking_changes(self, detector, old_contract):
        """Test when there are no breaking changes."""
        # Same contract
        changes = detector.detect_breaking_changes(old_contract, old_contract)
        
        # Should only have unused endpoint info
        errors = [c for c in changes if c.severity == "error"]
        warnings = [c for c in changes if c.severity == "warning"]
        
        assert len(errors) == 0
        assert len(warnings) == 0
    
    def test_get_endpoint_consumers(self, detector):
        """Test getting consumers from endpoint."""
        endpoint = Endpoint(
            id="test",
            path="/test",
            method="GET",
            consumers=["frontend", "mobile"]
        )
        
        consumers = detector._get_endpoint_consumers(endpoint)
        
        assert len(consumers) == 2
        assert "frontend" in consumers
        assert "mobile" in consumers
    
    def test_get_endpoint_consumers_empty(self, detector):
        """Test getting consumers from endpoint with no consumers."""
        endpoint = Endpoint(
            id="test",
            path="/test",
            method="GET",
            consumers=[]
        )
        
        consumers = detector._get_endpoint_consumers(endpoint)
        
        assert len(consumers) == 0
    
    def test_endpoint_modified_detection(self, detector):
        """Test detecting if endpoint was modified."""
        old_ep = Endpoint(
            id="test",
            path="/test",
            method="GET",
            parameters=[]
        )
        
        new_ep = Endpoint(
            id="test",
            path="/test",
            method="GET",
            parameters=[{"name": "page", "type": "integer"}]
        )
        
        assert detector._endpoint_modified(old_ep, new_ep)
    
    def test_endpoint_not_modified(self, detector):
        """Test detecting when endpoint was not modified."""
        old_ep = Endpoint(
            id="test",
            path="/test",
            method="GET",
            parameters=[]
        )
        
        new_ep = Endpoint(
            id="test",
            path="/test",
            method="GET",
            parameters=[]
        )
        
        assert not detector._endpoint_modified(old_ep, new_ep)


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    def test_format_breaking_changes_empty(self):
        """Test formatting with no breaking changes."""
        result = format_breaking_changes([])
        
        assert "No breaking changes detected" in result
    
    def test_format_breaking_changes_with_errors(self):
        """Test formatting with error-level changes."""
        changes = [
            BreakingChange(
                type="endpoint_removed",
                severity="error",
                endpoint="/users/{id}",
                method="GET",
                message="Endpoint removed",
                affected_consumers=["frontend"],
                suggestion="Notify consumers"
            )
        ]
        
        result = format_breaking_changes(changes)
        
        assert "ERRORS" in result
        assert "/users/{id}" in result
        assert "frontend" in result
    
    def test_format_breaking_changes_with_warnings(self):
        """Test formatting with warning-level changes."""
        changes = [
            BreakingChange(
                type="endpoint_modified",
                severity="warning",
                endpoint="/users",
                method="GET",
                message="Endpoint modified",
                affected_consumers=["frontend"],
                suggestion="Check compatibility"
            )
        ]
        
        result = format_breaking_changes(changes)
        
        assert "WARNINGS" in result
        assert "/users" in result
    
    def test_format_breaking_changes_with_info(self):
        """Test formatting with info-level changes."""
        changes = [
            BreakingChange(
                type="unused_endpoint",
                severity="info",
                endpoint="/admin/stats",
                method="GET",
                message="No consumers",
                affected_consumers=[],
                suggestion="Safe to remove"
            )
        ]
        
        result = format_breaking_changes(changes)
        
        assert "INFO" in result
        assert "/admin/stats" in result
