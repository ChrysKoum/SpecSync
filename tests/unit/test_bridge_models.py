"""
Unit tests for bridge data models.
"""
import pytest
import json
import yaml
from pathlib import Path
from datetime import datetime
from backend.bridge_models import (
    Endpoint, Model, Contract, Dependency, BridgeConfig,
    SyncResult, DriftIssue, load_contract_from_yaml, save_contract_to_yaml
)


class TestEndpoint:
    """Tests for Endpoint model."""
    
    def test_endpoint_creation(self):
        """Test creating an endpoint."""
        endpoint = Endpoint(
            id="get-users",
            path="/users",
            method="GET",
            status="implemented"
        )
        
        assert endpoint.id == "get-users"
        assert endpoint.path == "/users"
        assert endpoint.method == "GET"
        assert endpoint.status == "implemented"
    
    def test_endpoint_to_dict(self):
        """Test converting endpoint to dictionary."""
        endpoint = Endpoint(
            id="get-users",
            path="/users",
            method="GET",
            parameters=[{"name": "id", "type": "int"}]
        )
        
        data = endpoint.to_dict()
        assert data['id'] == "get-users"
        assert data['path'] == "/users"
        assert len(data['parameters']) == 1
    
    def test_endpoint_from_dict(self):
        """Test creating endpoint from dictionary."""
        data = {
            'id': 'post-users',
            'path': '/users',
            'method': 'POST',
            'status': 'implemented',
            'parameters': []
        }
        
        endpoint = Endpoint.from_dict(data)
        assert endpoint.id == 'post-users'
        assert endpoint.method == 'POST'


class TestContract:
    """Tests for Contract model."""
    
    def test_contract_creation(self):
        """Test creating a contract."""
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z"
        )
        
        assert contract.version == "1.0"
        assert contract.repo_id == "backend"
        assert contract.role == "provider"
    
    def test_contract_with_endpoints(self):
        """Test contract with endpoints."""
        endpoint = Endpoint(
            id="get-users",
            path="/users",
            method="GET"
        )
        
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[endpoint]
        )
        
        assert len(contract.endpoints) == 1
        assert contract.endpoints[0].path == "/users"
    
    def test_contract_to_dict(self):
        """Test converting contract to dictionary."""
        endpoint = Endpoint(id="get-users", path="/users", method="GET")
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[endpoint]
        )
        
        data = contract.to_dict()
        assert data['version'] == "1.0"
        assert len(data['endpoints']) == 1
        assert data['endpoints'][0]['path'] == "/users"
    
    def test_contract_save_and_load_yaml(self, tmp_path):
        """Test saving and loading contract from YAML."""
        endpoint = Endpoint(id="get-users", path="/users", method="GET")
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[endpoint]
        )
        
        # Save to YAML
        yaml_path = tmp_path / "contract.yaml"
        contract.save_to_yaml(str(yaml_path))
        
        assert yaml_path.exists()
        
        # Load from YAML
        loaded_contract = Contract.load_from_yaml(str(yaml_path))
        assert loaded_contract.version == "1.0"
        assert loaded_contract.repo_id == "backend"
        assert len(loaded_contract.endpoints) == 1


class TestDependency:
    """Tests for Dependency model."""
    
    def test_dependency_creation(self):
        """Test creating a dependency."""
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        assert dep.name == "backend"
        assert dep.type == "http-api"
        assert dep.sync_method == "git"
    
    def test_dependency_to_dict(self):
        """Test converting dependency to dictionary."""
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        data = dep.to_dict()
        assert data['name'] == "backend"
        assert data['git_url'] == "https://github.com/org/backend.git"


class TestBridgeConfig:
    """Tests for BridgeConfig model."""
    
    def test_config_creation(self):
        """Test creating a bridge config."""
        config = BridgeConfig(
            enabled=True,
            role="consumer",
            repo_id="frontend"
        )
        
        assert config.enabled is True
        assert config.role == "consumer"
        assert config.repo_id == "frontend"
    
    def test_config_add_dependency(self):
        """Test adding a dependency to config."""
        config = BridgeConfig(role="consumer")
        
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        config.dependencies["backend"] = dep
        
        assert "backend" in config.dependencies
        assert config.dependencies["backend"].name == "backend"
    
    def test_config_save_and_load(self, tmp_path):
        """Test saving and loading config."""
        config_path = tmp_path / "bridge.json"
        
        config = BridgeConfig(
            enabled=True,
            role="consumer",
            repo_id="frontend",
            config_path=str(config_path)
        )
        
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        config.add_dependency("backend", dep)
        
        # Load config
        loaded_config = BridgeConfig(config_path=str(config_path))
        loaded_config.load()
        
        assert loaded_config.role == "consumer"
        assert "backend" in loaded_config.dependencies
        assert loaded_config.dependencies["backend"].git_url == "https://github.com/org/backend.git"
    
    def test_config_validation(self):
        """Test config validation."""
        config = BridgeConfig(role="consumer")
        
        # Valid config
        errors = config.validate()
        assert len(errors) == 0
        
        # Invalid role
        config.role = "invalid"
        errors = config.validate()
        assert len(errors) > 0
    
    def test_config_create_default(self):
        """Test creating default config."""
        config = BridgeConfig.create_default(role="provider")
        
        assert config.role == "provider"
        assert 'contract_file' in config.provides
        assert config.provides['contract_file'] == '.kiro/contracts/provided-api.yaml'
    
    def test_config_remove_dependency_deletes_cache(self, tmp_path):
        """Test that removing a dependency deletes the cached contract file."""
        config_path = tmp_path / "bridge.json"
        cache_file = tmp_path / "backend-api.yaml"
        
        # Create a cached contract file
        cache_file.write_text("version: 1.0\nrepo_id: backend")
        assert cache_file.exists()
        
        config = BridgeConfig(
            enabled=True,
            role="consumer",
            config_path=str(config_path)
        )
        
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(cache_file)
        )
        
        config.add_dependency("backend", dep)
        assert "backend" in config.dependencies
        
        # Remove dependency
        config.remove_dependency("backend")
        
        # Verify dependency removed from config
        assert "backend" not in config.dependencies
        
        # Verify cached file was deleted
        assert not cache_file.exists()
    
    def test_config_get_dependency(self):
        """Test getting a dependency by name."""
        config = BridgeConfig(role="consumer")
        
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        config.dependencies["backend"] = dep
        
        # Get existing dependency
        retrieved = config.get_dependency("backend")
        assert retrieved is not None
        assert retrieved.name == "backend"
        
        # Get non-existent dependency
        missing = config.get_dependency("nonexistent")
        assert missing is None
    
    def test_config_list_dependencies(self):
        """Test listing all dependencies."""
        config = BridgeConfig(role="consumer")
        
        dep1 = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        dep2 = Dependency(
            name="auth",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/auth.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/auth-api.yaml"
        )
        
        config.dependencies["backend"] = dep1
        config.dependencies["auth"] = dep2
        
        deps = config.list_dependencies()
        assert len(deps) == 2
        assert "backend" in deps
        assert "auth" in deps


class TestSyncResult:
    """Tests for SyncResult model."""
    
    def test_sync_result_creation(self):
        """Test creating a sync result."""
        result = SyncResult(
            dependency_name="backend",
            success=True,
            changes=["Added endpoint: GET /users"],
            endpoint_count=5
        )
        
        assert result.dependency_name == "backend"
        assert result.success is True
        assert len(result.changes) == 1
        assert result.endpoint_count == 5
    
    def test_sync_result_to_dict(self):
        """Test converting sync result to dictionary."""
        result = SyncResult(
            dependency_name="backend",
            success=True,
            endpoint_count=5
        )
        
        data = result.to_dict()
        assert data['dependency_name'] == "backend"
        assert data['success'] is True


class TestDriftIssue:
    """Tests for DriftIssue model."""
    
    def test_drift_issue_creation(self):
        """Test creating a drift issue."""
        issue = DriftIssue(
            type="missing_endpoint",
            severity="error",
            endpoint="/users/{id}",
            method="GET",
            location="frontend/api.py:42",
            message="Endpoint not found in contract",
            suggestion="Update contract or remove API call"
        )
        
        assert issue.type == "missing_endpoint"
        assert issue.severity == "error"
        assert issue.endpoint == "/users/{id}"
    
    def test_drift_issue_to_dict(self):
        """Test converting drift issue to dictionary."""
        issue = DriftIssue(
            type="missing_endpoint",
            severity="error",
            endpoint="/users/{id}",
            method="GET",
            location="frontend/api.py:42",
            message="Endpoint not found in contract",
            suggestion="Update contract or remove API call"
        )
        
        data = issue.to_dict()
        assert data['type'] == "missing_endpoint"
        assert data['location'] == "frontend/api.py:42"
