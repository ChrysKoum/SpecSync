"""
Sync engine for SpecSync Bridge.
Synchronizes contracts between repositories using git.
"""
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.bridge_models import (
    BridgeConfig, 
    Dependency, 
    SyncResult, 
    Contract,
    load_contract_from_yaml
)


class ContractDiff:
    """Represents differences between two contracts."""
    
    def __init__(self):
        self.added_endpoints: List[Dict[str, Any]] = []
        self.removed_endpoints: List[Dict[str, Any]] = []
        self.modified_endpoints: List[Dict[str, Any]] = []
    
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.added_endpoints or self.removed_endpoints or self.modified_endpoints)
    
    def get_change_descriptions(self) -> List[str]:
        """Generate human-readable change descriptions."""
        changes = []
        
        for endpoint in self.added_endpoints:
            changes.append(f"Added: {endpoint['method']} {endpoint['path']}")
        
        for endpoint in self.removed_endpoints:
            changes.append(f"Removed: {endpoint['method']} {endpoint['path']}")
        
        for endpoint in self.modified_endpoints:
            changes.append(f"Modified: {endpoint['method']} {endpoint['path']}")
        
        return changes


class SyncEngine:
    """Synchronizes contracts between repositories."""
    
    # Maximum number of concurrent syncs
    MAX_CONCURRENT_SYNCS = 5
    
    def __init__(self, config: BridgeConfig, repo_root: str = ".", progress_callback: Optional[Callable[[str, str], None]] = None):
        self.config = config
        self.repo_root = Path(repo_root)
        self.progress_callback = progress_callback
    
    def sync_dependency(self, dependency_name: str) -> SyncResult:
        """
        Sync a single dependency.
        
        Args:
            dependency_name: Name of the dependency to sync
            
        Returns:
            SyncResult with sync status and details
        """
        dependency = self.config.get_dependency(dependency_name)
        
        if not dependency:
            return SyncResult(
                dependency_name=dependency_name,
                success=False,
                errors=[f"Dependency '{dependency_name}' not found in configuration"]
            )
        
        # Determine sync method
        if dependency.sync_method == 'git':
            return self._sync_via_git(dependency)
        elif dependency.sync_method == 'http':
            return self._sync_via_http(dependency)
        elif dependency.sync_method == 's3':
            return self._sync_via_cloud(dependency)
        else:
            return SyncResult(
                dependency_name=dependency_name,
                success=False,
                errors=[f"Unsupported sync method: {dependency.sync_method}"]
            )
    
    def sync_all_dependencies(self) -> List[SyncResult]:
        """
        Sync all configured dependencies in parallel.
        
        Uses ThreadPoolExecutor to sync multiple dependencies concurrently.
        Limits concurrent syncs to MAX_CONCURRENT_SYNCS (5) to avoid resource exhaustion.
        Continues syncing other dependencies even if one fails (partial failure resilience).
        
        Returns:
            List of SyncResult for each dependency
        """
        dependency_names = self.config.list_dependencies()
        
        if not dependency_names:
            return []
        
        # If only one dependency, no need for parallel execution
        if len(dependency_names) == 1:
            result = self.sync_dependency(dependency_names[0])
            return [result]
        
        results = []
        
        # Use ThreadPoolExecutor for parallel sync
        # Limit to MAX_CONCURRENT_SYNCS to avoid resource exhaustion
        max_workers = min(len(dependency_names), self.MAX_CONCURRENT_SYNCS)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all sync tasks
            future_to_dep = {
                executor.submit(self._sync_with_progress, dep_name): dep_name
                for dep_name in dependency_names
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_dep):
                dep_name = future_to_dep[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Handle unexpected exceptions during sync
                    # Create a failed SyncResult for this dependency
                    error_result = SyncResult(
                        dependency_name=dep_name,
                        success=False,
                        errors=[f"Unexpected error during sync: {str(e)}"]
                    )
                    results.append(error_result)
        
        # Sort results by dependency name for consistent ordering
        results.sort(key=lambda r: r.dependency_name)
        
        return results
    
    def _sync_with_progress(self, dependency_name: str) -> SyncResult:
        """
        Sync a dependency with progress reporting.
        
        Args:
            dependency_name: Name of the dependency to sync
            
        Returns:
            SyncResult
        """
        # Report progress: starting
        if self.progress_callback:
            self.progress_callback(dependency_name, "starting")
        
        try:
            # Perform the sync
            result = self.sync_dependency(dependency_name)
            
            # Report progress: completed
            if self.progress_callback:
                status = "completed" if result.success else "failed"
                self.progress_callback(dependency_name, status)
            
            return result
            
        except Exception as e:
            # Report progress: failed
            if self.progress_callback:
                self.progress_callback(dependency_name, "failed")
            
            # Re-raise to be caught by the executor
            raise
    
    def _sync_via_git(self, dependency: Dependency) -> SyncResult:
        """
        Sync contract via git clone/pull.
        
        Args:
            dependency: Dependency configuration
            
        Returns:
            SyncResult with sync status
        """
        temp_dir = None
        
        try:
            # Create temporary directory for git operations
            temp_dir = Path(tempfile.mkdtemp(prefix='specsync_'))
            
            # Clone or pull the repository
            repo_path = self._clone_or_pull_repo(dependency.git_url, temp_dir)
            
            # Locate the contract file in the cloned repo
            contract_source = repo_path / dependency.contract_path
            
            if not contract_source.exists():
                return SyncResult(
                    dependency_name=dependency.name,
                    success=False,
                    errors=[f"Contract file not found: {dependency.contract_path}"]
                )
            
            # Load the new contract
            new_contract = load_contract_from_yaml(str(contract_source))
            
            # Prepare local cache path
            cache_path = self.repo_root / dependency.local_cache
            
            # Load old contract if exists for diff
            old_contract = None
            if cache_path.exists():
                try:
                    old_contract = load_contract_from_yaml(str(cache_path))
                except:
                    pass  # Ignore errors loading old contract
            
            # Record consumer expectations before saving new contract
            self._record_consumer_expectations(dependency.name, new_contract)
            
            # Copy contract to local cache
            self._copy_contract_file(contract_source, cache_path)
            
            # Compare contracts to detect changes
            diff = self._compare_contracts(old_contract, new_contract)
            
            # Count endpoints
            endpoint_count = len(new_contract.endpoints)
            
            return SyncResult(
                dependency_name=dependency.name,
                success=True,
                changes=diff.get_change_descriptions(),
                endpoint_count=endpoint_count,
                cached_file=str(cache_path)
            )
            
        except subprocess.CalledProcessError as e:
            # Git command failed
            error_msg = f"Git operation failed: {e.cmd}\nError: {e.stderr if hasattr(e, 'stderr') else str(e)}"
            
            # Try offline fallback
            return self._offline_fallback(dependency, error_msg)
            
        except Exception as e:
            # Other errors
            error_msg = f"Sync failed: {str(e)}"
            return self._offline_fallback(dependency, error_msg)
            
        finally:
            # Clean up temporary directory
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass  # Best effort cleanup
    
    def _clone_or_pull_repo(self, git_url: str, temp_dir: Path) -> Path:
        """
        Clone a git repository to a temporary directory.
        
        Args:
            git_url: Git repository URL
            temp_dir: Temporary directory path
            
        Returns:
            Path to cloned repository
        """
        repo_path = temp_dir / "repo"
        
        # Use shallow clone for efficiency
        cmd = [
            'git', 'clone',
            '--depth', '1',
            git_url,
            str(repo_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return repo_path
    
    def _copy_contract_file(self, source: Path, dest: Path) -> None:
        """
        Copy contract file from source to destination.
        
        Args:
            source: Source file path
            dest: Destination file path
        """
        # Ensure destination directory exists
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source, dest)
    
    def _compare_contracts(self, old: Optional[Contract], new: Contract) -> ContractDiff:
        """
        Compare two contracts and detect changes.
        
        Args:
            old: Old contract (None if first sync)
            new: New contract
            
        Returns:
            ContractDiff with detected changes
        """
        diff = ContractDiff()
        
        if old is None:
            # First sync - all endpoints are "added"
            diff.added_endpoints = [ep.to_dict() if hasattr(ep, 'to_dict') else ep for ep in new.endpoints]
            return diff
        
        # Create lookup maps by (method, path)
        old_endpoints = {
            (ep.method if hasattr(ep, 'method') else ep['method'], 
             ep.path if hasattr(ep, 'path') else ep['path']): ep
            for ep in old.endpoints
        }
        
        new_endpoints = {
            (ep.method if hasattr(ep, 'method') else ep['method'],
             ep.path if hasattr(ep, 'path') else ep['path']): ep
            for ep in new.endpoints
        }
        
        # Find added endpoints
        for key, endpoint in new_endpoints.items():
            if key not in old_endpoints:
                ep_dict = endpoint.to_dict() if hasattr(endpoint, 'to_dict') else endpoint
                diff.added_endpoints.append(ep_dict)
        
        # Find removed endpoints
        for key, endpoint in old_endpoints.items():
            if key not in new_endpoints:
                ep_dict = endpoint.to_dict() if hasattr(endpoint, 'to_dict') else endpoint
                diff.removed_endpoints.append(ep_dict)
        
        # Find modified endpoints (same key but different content)
        for key in old_endpoints.keys() & new_endpoints.keys():
            old_ep = old_endpoints[key]
            new_ep = new_endpoints[key]
            
            # Convert to dicts for comparison
            old_dict = old_ep.to_dict() if hasattr(old_ep, 'to_dict') else old_ep
            new_dict = new_ep.to_dict() if hasattr(new_ep, 'to_dict') else new_ep
            
            # Compare relevant fields (ignore timestamps)
            old_compare = {k: v for k, v in old_dict.items() if k not in ['implemented_at', 'consumers']}
            new_compare = {k: v for k, v in new_dict.items() if k not in ['implemented_at', 'consumers']}
            
            if old_compare != new_compare:
                diff.modified_endpoints.append(new_dict)
        
        return diff
    
    def _record_consumer_expectations(self, dependency_name: str, contract: Contract) -> None:
        """
        Record which endpoints the consumer expects to use.
        
        This method:
        1. Scans consumer code for API calls to this dependency
        2. Records usage locations (file and line number)
        3. Stores expectations in a separate file for tracking
        
        Args:
            dependency_name: Name of the dependency
            contract: The provider's contract
        """
        from backend.bridge_drift_detector import BridgeDriftDetector
        
        # Create drift detector to find API calls
        detector = BridgeDriftDetector(str(self.repo_root))
        
        # Find all API calls in consumer code
        api_calls = detector._find_api_calls_in_code()
        
        # Build expectations data structure
        expectations = []
        
        for api_call in api_calls:
            # Check if this call matches any endpoint in the contract
            for endpoint in contract.endpoints:
                if (detector._paths_match(
                    detector._normalize_path(api_call.path),
                    detector._normalize_path(endpoint.path)
                ) and api_call.method == endpoint.method):
                    # Found a match - record the expectation
                    expectation = {
                        'endpoint': f"{api_call.method} {api_call.path}",
                        'status': 'using',
                        'usage_locations': [f"{api_call.file_path}:{api_call.line_number}"]
                    }
                    
                    # Check if we already have this endpoint
                    existing = next((e for e in expectations if e['endpoint'] == expectation['endpoint']), None)
                    if existing:
                        # Add location to existing expectation
                        if expectation['usage_locations'][0] not in existing['usage_locations']:
                            existing['usage_locations'].append(expectation['usage_locations'][0])
                    else:
                        expectations.append(expectation)
                    break
        
        # Save expectations to a separate file
        expectations_file = self.repo_root / f".kiro/contracts/{dependency_name}-expectations.yaml"
        expectations_file.parent.mkdir(parents=True, exist_ok=True)
        
        import yaml
        expectations_data = {
            'dependency': dependency_name,
            'last_updated': datetime.utcnow().isoformat() + 'Z',
            'expectations': expectations
        }
        
        with open(expectations_file, 'w', encoding='utf-8') as f:
            yaml.dump(expectations_data, f, default_flow_style=False, sort_keys=False)
    
    def _offline_fallback(self, dependency: Dependency, error_msg: str) -> SyncResult:
        """
        Fallback to cached contract when sync fails.
        
        Args:
            dependency: Dependency configuration
            error_msg: Error message from failed sync
            
        Returns:
            SyncResult with cached contract or error
        """
        cache_path = self.repo_root / dependency.local_cache
        
        if cache_path.exists():
            # Use cached contract
            try:
                cached_contract = load_contract_from_yaml(str(cache_path))
                endpoint_count = len(cached_contract.endpoints)
                
                warning = f"⚠️  Using cached contract (sync failed: {error_msg})"
                
                return SyncResult(
                    dependency_name=dependency.name,
                    success=True,  # Success with warning
                    changes=[warning],
                    endpoint_count=endpoint_count,
                    cached_file=str(cache_path),
                    errors=[error_msg]
                )
            except Exception as e:
                return SyncResult(
                    dependency_name=dependency.name,
                    success=False,
                    errors=[error_msg, f"Failed to load cached contract: {str(e)}"]
                )
        else:
            # No cache available
            return SyncResult(
                dependency_name=dependency.name,
                success=False,
                errors=[error_msg, "No cached contract available"]
            )
    
    def _sync_via_http(self, dependency: Dependency) -> SyncResult:
        """
        Sync contract via HTTP endpoint.
        
        Args:
            dependency: Dependency configuration
            
        Returns:
            SyncResult with sync status
        """
        # Placeholder for HTTP sync implementation
        return SyncResult(
            dependency_name=dependency.name,
            success=False,
            errors=["HTTP sync not yet implemented"]
        )
    
    def _sync_via_cloud(self, dependency: Dependency) -> SyncResult:
        """
        Sync contract via cloud storage (S3, etc.).
        
        Args:
            dependency: Dependency configuration
            
        Returns:
            SyncResult with sync status
        """
        # Placeholder for cloud sync implementation
        return SyncResult(
            dependency_name=dependency.name,
            success=False,
            errors=["Cloud sync not yet implemented"]
        )


def sync_dependency(dependency_name: str, config_path: str = ".kiro/settings/bridge.json") -> SyncResult:
    """
    Sync a single dependency.
    
    Args:
        dependency_name: Name of dependency to sync
        config_path: Path to bridge configuration
        
    Returns:
        SyncResult
    """
    from backend.bridge_models import load_config
    
    config = load_config(config_path)
    engine = SyncEngine(config)
    return engine.sync_dependency(dependency_name)


def sync_all(config_path: str = ".kiro/settings/bridge.json") -> List[SyncResult]:
    """
    Sync all configured dependencies.
    
    Args:
        config_path: Path to bridge configuration
        
    Returns:
        List of SyncResult
    """
    from backend.bridge_models import load_config
    
    config = load_config(config_path)
    engine = SyncEngine(config)
    return engine.sync_all_dependencies()


if __name__ == '__main__':
    # Test sync
    results = sync_all()
    for result in results:
        if result.success:
            print(f"✓ Synced {result.dependency_name}: {result.endpoint_count} endpoints")
            for change in result.changes:
                print(f"  - {change}")
        else:
            print(f"✗ Failed to sync {result.dependency_name}")
            for error in result.errors:
                print(f"  - {error}")
