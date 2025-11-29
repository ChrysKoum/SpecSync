"""
Integration tests for bridge sync functionality.
Tests the complete sync workflow including git operations.
"""
import pytest
from pathlib import Path
from backend.bridge_sync import SyncEngine
from backend.bridge_models import BridgeConfig, Dependency, Contract, Endpoint


class TestSyncIntegration:
    """Integration tests for sync engine."""
    
    def test_sync_with_local_git_repo(self, tmp_path):
        """Test syncing from a local git repository."""
        # Create a mock provider repository
        provider_repo = tmp_path / "provider"
        provider_repo.mkdir()
        
        # Initialize git repo
        import subprocess
        subprocess.run(['git', 'init'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=provider_repo, check=True, capture_output=True)
        
        # Create a contract in the provider repo
        contracts_dir = provider_repo / ".kiro" / "contracts"
        contracts_dir.mkdir(parents=True)
        
        contract = Contract(
            version="1.0",
            repo_id="provider",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET"),
                Endpoint(id="post-users", path="/users", method="POST")
            ]
        )
        
        contract_path = contracts_dir / "provided-api.yaml"
        contract.save_to_yaml(str(contract_path))
        
        # Commit the contract
        subprocess.run(['git', 'add', '.'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add contract'], cwd=provider_repo, check=True, capture_output=True)
        
        # Create consumer repository
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        # Create config for consumer
        config = BridgeConfig(role="consumer", repo_id="consumer")
        dep = Dependency(
            name="provider",
            type="http-api",
            sync_method="git",
            git_url=str(provider_repo),  # Use local path as git URL
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/provider-api.yaml"
        )
        config.dependencies["provider"] = dep
        
        # Create sync engine
        engine = SyncEngine(config, repo_root=str(consumer_repo))
        
        # Sync the dependency
        result = engine.sync_dependency("provider")
        
        # Verify sync succeeded
        assert result.success, f"Sync failed: {result.errors}"
        assert result.endpoint_count == 2
        assert len(result.changes) == 2  # Both endpoints are "added" on first sync
        
        # Verify contract was cached
        cached_path = consumer_repo / ".kiro" / "contracts" / "provider-api.yaml"
        assert cached_path.exists()
        
        # Load and verify cached contract
        cached_contract = Contract.load_from_yaml(str(cached_path))
        assert len(cached_contract.endpoints) == 2
        assert cached_contract.repo_id == "provider"
    
    def test_sync_detects_changes(self, tmp_path):
        """Test that sync detects changes between versions."""
        # Create consumer repo with existing cached contract
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        cache_dir = consumer_repo / ".kiro" / "contracts"
        cache_dir.mkdir(parents=True)
        
        # Create initial cached contract
        old_contract = Contract(
            version="1.0",
            repo_id="provider",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET")
            ]
        )
        
        cache_path = cache_dir / "provider-api.yaml"
        old_contract.save_to_yaml(str(cache_path))
        
        # Create provider repo with updated contract
        provider_repo = tmp_path / "provider"
        provider_repo.mkdir()
        
        import subprocess
        subprocess.run(['git', 'init'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=provider_repo, check=True, capture_output=True)
        
        provider_contracts_dir = provider_repo / ".kiro" / "contracts"
        provider_contracts_dir.mkdir(parents=True)
        
        # New contract with additional endpoint
        new_contract = Contract(
            version="1.0",
            repo_id="provider",
            role="provider",
            last_updated="2024-11-27T11:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET"),
                Endpoint(id="post-users", path="/users", method="POST"),
                Endpoint(id="get-user", path="/users/{id}", method="GET")
            ]
        )
        
        provider_contract_path = provider_contracts_dir / "provided-api.yaml"
        new_contract.save_to_yaml(str(provider_contract_path))
        
        subprocess.run(['git', 'add', '.'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Update contract'], cwd=provider_repo, check=True, capture_output=True)
        
        # Setup config and sync
        config = BridgeConfig(role="consumer", repo_id="consumer")
        dep = Dependency(
            name="provider",
            type="http-api",
            sync_method="git",
            git_url=str(provider_repo),
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(cache_path)
        )
        config.dependencies["provider"] = dep
        
        engine = SyncEngine(config, repo_root=str(consumer_repo))
        result = engine.sync_dependency("provider")
        
        # Verify changes detected
        assert result.success
        assert result.endpoint_count == 3
        assert len(result.changes) == 2  # Two new endpoints added
        assert any("POST /users" in change for change in result.changes)
        assert any("GET /users/{id}" in change for change in result.changes)
    
    def test_offline_fallback_integration(self, tmp_path):
        """Test that offline fallback works when git fails."""
        # Create consumer repo with cached contract
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        cache_dir = consumer_repo / ".kiro" / "contracts"
        cache_dir.mkdir(parents=True)
        
        # Create cached contract
        cached_contract = Contract(
            version="1.0",
            repo_id="provider",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-users", path="/users", method="GET")
            ]
        )
        
        cache_path = cache_dir / "provider-api.yaml"
        cached_contract.save_to_yaml(str(cache_path))
        
        # Setup config with invalid git URL
        config = BridgeConfig(role="consumer", repo_id="consumer")
        dep = Dependency(
            name="provider",
            type="http-api",
            sync_method="git",
            git_url="https://invalid.example.com/repo.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(cache_path)
        )
        config.dependencies["provider"] = dep
        
        engine = SyncEngine(config, repo_root=str(consumer_repo))
        result = engine.sync_dependency("provider")
        
        # Should succeed with warning (using cached contract)
        assert result.success
        assert result.endpoint_count == 1
        assert len(result.errors) > 0  # Has error message
        assert any("cached contract" in change.lower() for change in result.changes)
    
    def test_parallel_sync_multiple_dependencies(self, tmp_path):
        """Test syncing multiple dependencies in parallel."""
        # Create multiple provider repositories
        num_providers = 3
        provider_repos = []
        
        for i in range(num_providers):
            provider_repo = tmp_path / f"provider{i}"
            provider_repo.mkdir()
            
            # Initialize git repo
            import subprocess
            subprocess.run(['git', 'init'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=provider_repo, check=True, capture_output=True)
            
            # Create contract
            contracts_dir = provider_repo / ".kiro" / "contracts"
            contracts_dir.mkdir(parents=True)
            
            contract = Contract(
                version="1.0",
                repo_id=f"provider{i}",
                role="provider",
                last_updated="2024-11-27T10:00:00Z",
                endpoints=[
                    Endpoint(id=f"get-items-{i}", path=f"/items{i}", method="GET")
                ]
            )
            
            contract_path = contracts_dir / "provided-api.yaml"
            contract.save_to_yaml(str(contract_path))
            
            # Commit
            subprocess.run(['git', 'add', '.'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add contract'], cwd=provider_repo, check=True, capture_output=True)
            
            provider_repos.append(provider_repo)
        
        # Create consumer repository
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        # Create config with multiple dependencies
        config = BridgeConfig(role="consumer", repo_id="consumer")
        
        for i, provider_repo in enumerate(provider_repos):
            dep = Dependency(
                name=f"provider{i}",
                type="http-api",
                sync_method="git",
                git_url=str(provider_repo),
                contract_path=".kiro/contracts/provided-api.yaml",
                local_cache=f".kiro/contracts/provider{i}-api.yaml"
            )
            config.dependencies[f"provider{i}"] = dep
        
        # Track progress callbacks
        progress_events = []
        
        def progress_callback(dep_name: str, status: str):
            progress_events.append((dep_name, status))
        
        # Create sync engine with progress callback
        engine = SyncEngine(config, repo_root=str(consumer_repo), progress_callback=progress_callback)
        
        # Sync all dependencies
        results = engine.sync_all_dependencies()
        
        # Verify all syncs succeeded
        assert len(results) == num_providers
        for result in results:
            assert result.success, f"Sync failed for {result.dependency_name}: {result.errors}"
            assert result.endpoint_count == 1
        
        # Verify all contracts were cached
        for i in range(num_providers):
            cached_path = consumer_repo / ".kiro" / "contracts" / f"provider{i}-api.yaml"
            assert cached_path.exists()
        
        # Verify progress callbacks were called
        assert len(progress_events) == num_providers * 2  # starting + completed for each
        starting_events = [e for e in progress_events if e[1] == "starting"]
        completed_events = [e for e in progress_events if e[1] == "completed"]
        assert len(starting_events) == num_providers
        assert len(completed_events) == num_providers
    
    def test_parallel_sync_partial_failure(self, tmp_path):
        """Test that parallel sync continues when one dependency fails."""
        # Create one valid provider
        provider_repo = tmp_path / "provider_valid"
        provider_repo.mkdir()
        
        import subprocess
        subprocess.run(['git', 'init'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=provider_repo, check=True, capture_output=True)
        
        contracts_dir = provider_repo / ".kiro" / "contracts"
        contracts_dir.mkdir(parents=True)
        
        contract = Contract(
            version="1.0",
            repo_id="provider_valid",
            role="provider",
            last_updated="2024-11-27T10:00:00Z",
            endpoints=[
                Endpoint(id="get-items", path="/items", method="GET")
            ]
        )
        
        contract_path = contracts_dir / "provided-api.yaml"
        contract.save_to_yaml(str(contract_path))
        
        subprocess.run(['git', 'add', '.'], cwd=provider_repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Add contract'], cwd=provider_repo, check=True, capture_output=True)
        
        # Create consumer repository
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        # Create config with one valid and one invalid dependency
        config = BridgeConfig(role="consumer", repo_id="consumer")
        
        # Valid dependency
        dep_valid = Dependency(
            name="provider_valid",
            type="http-api",
            sync_method="git",
            git_url=str(provider_repo),
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/provider_valid-api.yaml"
        )
        config.dependencies["provider_valid"] = dep_valid
        
        # Invalid dependency (bad git URL)
        dep_invalid = Dependency(
            name="provider_invalid",
            type="http-api",
            sync_method="git",
            git_url="https://invalid.example.com/repo.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/provider_invalid-api.yaml"
        )
        config.dependencies["provider_invalid"] = dep_invalid
        
        # Create sync engine
        engine = SyncEngine(config, repo_root=str(consumer_repo))
        
        # Sync all dependencies
        results = engine.sync_all_dependencies()
        
        # Verify we got results for both dependencies
        assert len(results) == 2
        
        # Find results by name
        valid_result = next(r for r in results if r.dependency_name == "provider_valid")
        invalid_result = next(r for r in results if r.dependency_name == "provider_invalid")
        
        # Valid dependency should succeed
        assert valid_result.success
        assert valid_result.endpoint_count == 1
        
        # Invalid dependency should fail
        assert not invalid_result.success
        assert len(invalid_result.errors) > 0
        
        # Verify valid contract was cached
        cached_path = consumer_repo / ".kiro" / "contracts" / "provider_valid-api.yaml"
        assert cached_path.exists()
    
    def test_parallel_sync_respects_max_workers(self, tmp_path):
        """Test that parallel sync limits concurrent workers."""
        # Create more dependencies than MAX_CONCURRENT_SYNCS
        num_providers = 7  # More than MAX_CONCURRENT_SYNCS (5)
        
        for i in range(num_providers):
            provider_repo = tmp_path / f"provider{i}"
            provider_repo.mkdir()
            
            import subprocess
            subprocess.run(['git', 'init'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=provider_repo, check=True, capture_output=True)
            
            contracts_dir = provider_repo / ".kiro" / "contracts"
            contracts_dir.mkdir(parents=True)
            
            contract = Contract(
                version="1.0",
                repo_id=f"provider{i}",
                role="provider",
                last_updated="2024-11-27T10:00:00Z",
                endpoints=[
                    Endpoint(id=f"get-items-{i}", path=f"/items{i}", method="GET")
                ]
            )
            
            contract_path = contracts_dir / "provided-api.yaml"
            contract.save_to_yaml(str(contract_path))
            
            subprocess.run(['git', 'add', '.'], cwd=provider_repo, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', 'Add contract'], cwd=provider_repo, check=True, capture_output=True)
        
        # Create consumer repository
        consumer_repo = tmp_path / "consumer"
        consumer_repo.mkdir()
        
        # Create config with all dependencies
        config = BridgeConfig(role="consumer", repo_id="consumer")
        
        for i in range(num_providers):
            provider_repo = tmp_path / f"provider{i}"
            dep = Dependency(
                name=f"provider{i}",
                type="http-api",
                sync_method="git",
                git_url=str(provider_repo),
                contract_path=".kiro/contracts/provided-api.yaml",
                local_cache=f".kiro/contracts/provider{i}-api.yaml"
            )
            config.dependencies[f"provider{i}"] = dep
        
        # Create sync engine
        engine = SyncEngine(config, repo_root=str(consumer_repo))
        
        # Sync all dependencies
        results = engine.sync_all_dependencies()
        
        # Verify all syncs completed (even though limited to 5 concurrent)
        assert len(results) == num_providers
        for result in results:
            assert result.success, f"Sync failed for {result.dependency_name}: {result.errors}"
