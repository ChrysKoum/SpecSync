"""
Unit tests for bridge sync engine.
"""
import pytest
from pathlib import Path
from backend.bridge_sync import SyncEngine, ContractDiff
from backend.bridge_models import BridgeConfig, Dependency, Contract, Endpoint


class TestContractDiff:
    """Tests for ContractDiff class."""
    
    def test_empty_diff_has_no_changes(self):
        """Test that empty diff reports no changes."""
        diff = ContractDiff()
        assert not diff.has_changes()
        assert diff.get_change_descriptions() == []
    
    def test_added_endpoints_detected(self):
        """Test that added endpoints are detected."""
        diff = ContractDiff()
        diff.added_endpoints = [
            {'method': 'GET', 'path': '/users'},
            {'method': 'POST', 'path': '/users'}
        ]
        
        assert diff.has_changes()
        changes = diff.get_change_descriptions()
        assert len(changes) == 2
        assert "Added: GET /users" in changes
        assert "Added: POST /users" in changes
    
    def test_removed_endpoints_detected(self):
        """Test that removed endpoints are detected."""
        diff = ContractDiff()
        diff.removed_endpoints = [
            {'method': 'DELETE', 'path': '/users/{id}'}
        ]
        
        assert diff.has_changes()
        changes = diff.get_change_descriptions()
        assert len(changes) == 1
        assert "Removed: DELETE /users/{id}" in changes
    
    def test_modified_endpoints_detected(self):
        """Test that modified endpoints are detected."""
        diff = ContractDiff()
        diff.modified_endpoints = [
            {'method': 'PUT', 'path': '/users/{id}'}
        ]
        
        assert diff.has_changes()
        changes = diff.get_change_descriptions()
        assert len(changes) == 1
        assert "Modified: PUT /users/{id}" in changes


class TestSyncEngine:
    """Tests for SyncEngine class."""
    
    def test_sync_nonexistent_dependency(self):
        """Test syncing a dependency that doesn't exist."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        result = engine.sync_dependency("nonexistent")
        
        assert not result.success
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()
    
    def test_sync_unsupported_method(self):
        """Test syncing with unsupported sync method."""
        config = BridgeConfig(role="consumer")
        dep = Dependency(
            name="test",
            type="http-api",
            sync_method="ftp",  # Unsupported
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/test-api.yaml"
        )
        config.dependencies["test"] = dep
        
        engine = SyncEngine(config)
        result = engine.sync_dependency("test")
        
        assert not result.success
        assert "Unsupported sync method" in result.errors[0]
    
    def test_compare_contracts_first_sync(self):
        """Test comparing contracts when old is None (first sync)."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        new_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET"),
                Endpoint(id="post-users", path="/users", method="POST")
            ]
        )
        
        diff = engine._compare_contracts(None, new_contract)
        
        assert diff.has_changes()
        assert len(diff.added_endpoints) == 2
        assert len(diff.removed_endpoints) == 0
        assert len(diff.modified_endpoints) == 0
    
    def test_compare_contracts_no_changes(self):
        """Test comparing identical contracts."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        endpoint = Endpoint(id="get-users", path="/users", method="GET")
        
        old_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[endpoint]
        )
        
        new_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",  # Different timestamp
            endpoints=[endpoint]
        )
        
        diff = engine._compare_contracts(old_contract, new_contract)
        
        assert not diff.has_changes()
    
    def test_compare_contracts_added_endpoint(self):
        """Test detecting added endpoints."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        old_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET")
            ]
        )
        
        new_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET"),
                Endpoint(id="post-users", path="/users", method="POST")
            ]
        )
        
        diff = engine._compare_contracts(old_contract, new_contract)
        
        assert diff.has_changes()
        assert len(diff.added_endpoints) == 1
        assert diff.added_endpoints[0]['method'] == 'POST'
        assert diff.added_endpoints[0]['path'] == '/users'
    
    def test_compare_contracts_removed_endpoint(self):
        """Test detecting removed endpoints."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        old_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET"),
                Endpoint(id="delete-users", path="/users/{id}", method="DELETE")
            ]
        )
        
        new_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET")
            ]
        )
        
        diff = engine._compare_contracts(old_contract, new_contract)
        
        assert diff.has_changes()
        assert len(diff.removed_endpoints) == 1
        assert diff.removed_endpoints[0]['method'] == 'DELETE'
        assert diff.removed_endpoints[0]['path'] == '/users/{id}'
    
    def test_compare_contracts_modified_endpoint(self):
        """Test detecting modified endpoints."""
        config = BridgeConfig(role="consumer")
        engine = SyncEngine(config)
        
        old_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(
                    id="get-users",
                    path="/users",
                    method="GET",
                    parameters=[]
                )
            ]
        )
        
        new_contract = Contract(
            version="1.0",
            repo_id="test",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(
                    id="get-users",
                    path="/users",
                    method="GET",
                    parameters=[{'name': 'limit', 'type': 'int'}]
                )
            ]
        )
        
        diff = engine._compare_contracts(old_contract, new_contract)
        
        assert diff.has_changes()
        assert len(diff.modified_endpoints) == 1
        assert diff.modified_endpoints[0]['method'] == 'GET'
        assert diff.modified_endpoints[0]['path'] == '/users'
    
    def test_offline_fallback_with_cache(self, tmp_path):
        """Test offline fallback uses cached contract."""
        # Create a cached contract
        cache_path = tmp_path / "backend-api.yaml"
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET")
            ]
        )
        contract.save_to_yaml(str(cache_path))
        
        # Create config with dependency
        config = BridgeConfig(role="consumer")
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://invalid.url",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(cache_path)
        )
        config.dependencies["backend"] = dep
        
        engine = SyncEngine(config, repo_root=str(tmp_path))
        
        # Test fallback
        result = engine._offline_fallback(dep, "Network error")
        
        assert result.success  # Success with warning
        assert result.endpoint_count == 1
        assert len(result.changes) > 0
        assert "cached contract" in result.changes[0].lower()
    
    def test_offline_fallback_without_cache(self, tmp_path):
        """Test offline fallback fails without cache."""
        config = BridgeConfig(role="consumer")
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://invalid.url",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(tmp_path / "nonexistent.yaml")
        )
        
        engine = SyncEngine(config, repo_root=str(tmp_path))
        
        # Test fallback
        result = engine._offline_fallback(dep, "Network error")
        
        assert not result.success
        assert "No cached contract available" in result.errors
    
    def test_sync_all_dependencies(self):
        """Test syncing all dependencies."""
        config = BridgeConfig(role="consumer")
        
        # Add multiple dependencies with unsupported methods (for testing)
        dep1 = Dependency(
            name="backend",
            type="http-api",
            sync_method="http",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        dep2 = Dependency(
            name="auth",
            type="http-api",
            sync_method="http",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/auth-api.yaml"
        )
        
        config.dependencies["backend"] = dep1
        config.dependencies["auth"] = dep2
        
        engine = SyncEngine(config)
        results = engine.sync_all_dependencies()
        
        assert len(results) == 2
        assert results[0].dependency_name in ["backend", "auth"]
        assert results[1].dependency_name in ["backend", "auth"]
