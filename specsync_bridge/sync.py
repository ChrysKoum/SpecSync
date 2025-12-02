"""
Sync engine for SpecSync Bridge.
Synchronizes contracts between repositories using git.
"""
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Callable
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from specsync_bridge.models import (
    BridgeConfig, Dependency, SyncResult, Contract, load_contract_from_yaml
)


class ContractDiff:
    """Represents differences between two contracts."""
    
    def __init__(self):
        self.added_endpoints: List[dict] = []
        self.removed_endpoints: List[dict] = []
        self.modified_endpoints: List[dict] = []
    
    def has_changes(self) -> bool:
        return bool(self.added_endpoints or self.removed_endpoints or self.modified_endpoints)
    
    def get_change_descriptions(self) -> List[str]:
        changes = []
        for ep in self.added_endpoints:
            changes.append(f"Added: {ep['method']} {ep['path']}")
        for ep in self.removed_endpoints:
            changes.append(f"Removed: {ep['method']} {ep['path']}")
        for ep in self.modified_endpoints:
            changes.append(f"Modified: {ep['method']} {ep['path']}")
        return changes


class SyncEngine:
    """Synchronizes contracts between repositories."""
    
    MAX_CONCURRENT_SYNCS = 5
    
    def __init__(self, config: BridgeConfig, repo_root: str = ".", 
                 progress_callback: Optional[Callable[[str, str], None]] = None):
        self.config = config
        self.repo_root = Path(repo_root)
        self.progress_callback = progress_callback
    
    def sync_dependency(self, dependency_name: str) -> SyncResult:
        dependency = self.config.get_dependency(dependency_name)
        if not dependency:
            return SyncResult(
                dependency_name=dependency_name,
                success=False,
                errors=[f"Dependency '{dependency_name}' not found"]
            )
        
        if dependency.sync_method == 'git':
            return self._sync_via_git(dependency)
        else:
            return SyncResult(
                dependency_name=dependency_name,
                success=False,
                errors=[f"Unsupported sync method: {dependency.sync_method}"]
            )
    
    def sync_all_dependencies(self) -> List[SyncResult]:
        dependency_names = self.config.list_dependencies()
        if not dependency_names:
            return []
        
        if len(dependency_names) == 1:
            return [self.sync_dependency(dependency_names[0])]
        
        results = []
        max_workers = min(len(dependency_names), self.MAX_CONCURRENT_SYNCS)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dep = {
                executor.submit(self._sync_with_progress, dep_name): dep_name
                for dep_name in dependency_names
            }
            for future in as_completed(future_to_dep):
                dep_name = future_to_dep[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(SyncResult(
                        dependency_name=dep_name,
                        success=False,
                        errors=[f"Unexpected error: {str(e)}"]
                    ))
        
        results.sort(key=lambda r: r.dependency_name)
        return results
    
    def _sync_with_progress(self, dependency_name: str) -> SyncResult:
        if self.progress_callback:
            self.progress_callback(dependency_name, "starting")
        try:
            result = self.sync_dependency(dependency_name)
            if self.progress_callback:
                self.progress_callback(dependency_name, "completed" if result.success else "failed")
            return result
        except Exception:
            if self.progress_callback:
                self.progress_callback(dependency_name, "failed")
            raise
    
    def _sync_via_git(self, dependency: Dependency) -> SyncResult:
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix='specsync_'))
            repo_path = self._clone_repo(dependency.git_url, temp_dir)
            contract_source = repo_path / dependency.contract_path
            
            if not contract_source.exists():
                return SyncResult(
                    dependency_name=dependency.name,
                    success=False,
                    errors=[f"Contract not found: {dependency.contract_path}"]
                )
            
            new_contract = load_contract_from_yaml(str(contract_source))
            cache_path = self.repo_root / dependency.local_cache
            
            old_contract = None
            if cache_path.exists():
                try:
                    old_contract = load_contract_from_yaml(str(cache_path))
                except:
                    pass
            
            self._copy_contract(contract_source, cache_path)
            diff = self._compare_contracts(old_contract, new_contract)
            
            return SyncResult(
                dependency_name=dependency.name,
                success=True,
                changes=diff.get_change_descriptions(),
                endpoint_count=len(new_contract.endpoints),
                cached_file=str(cache_path)
            )
        except subprocess.CalledProcessError as e:
            return self._offline_fallback(dependency, f"Git failed: {e}")
        except Exception as e:
            return self._offline_fallback(dependency, str(e))
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _clone_repo(self, git_url: str, temp_dir: Path) -> Path:
        repo_path = temp_dir / "repo"
        subprocess.run(
            ['git', 'clone', '--depth', '1', git_url, str(repo_path)],
            capture_output=True, text=True, check=True
        )
        return repo_path
    
    def _copy_contract(self, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    
    def _compare_contracts(self, old: Optional[Contract], new: Contract) -> ContractDiff:
        diff = ContractDiff()
        if old is None:
            diff.added_endpoints = [ep.to_dict() if hasattr(ep, 'to_dict') else ep for ep in new.endpoints]
            return diff
        
        old_eps = {(ep.method, ep.path): ep for ep in old.endpoints}
        new_eps = {(ep.method, ep.path): ep for ep in new.endpoints}
        
        for key, ep in new_eps.items():
            if key not in old_eps:
                diff.added_endpoints.append(ep.to_dict() if hasattr(ep, 'to_dict') else ep)
        
        for key, ep in old_eps.items():
            if key not in new_eps:
                diff.removed_endpoints.append(ep.to_dict() if hasattr(ep, 'to_dict') else ep)
        
        return diff
    
    def _offline_fallback(self, dependency: Dependency, error_msg: str) -> SyncResult:
        cache_path = self.repo_root / dependency.local_cache
        if cache_path.exists():
            try:
                contract = load_contract_from_yaml(str(cache_path))
                return SyncResult(
                    dependency_name=dependency.name,
                    success=True,
                    changes=[f"⚠️ Using cached contract ({error_msg})"],
                    endpoint_count=len(contract.endpoints),
                    cached_file=str(cache_path),
                    errors=[error_msg]
                )
            except Exception as e:
                pass
        return SyncResult(
            dependency_name=dependency.name,
            success=False,
            errors=[error_msg, "No cached contract available"]
        )


def sync_dependency(dependency_name: str, config_path: str = ".kiro/settings/bridge.json") -> SyncResult:
    from specsync_bridge.models import load_config
    config = load_config(config_path)
    engine = SyncEngine(config)
    return engine.sync_dependency(dependency_name)


def sync_all(config_path: str = ".kiro/settings/bridge.json") -> List[SyncResult]:
    from specsync_bridge.models import load_config
    config = load_config(config_path)
    engine = SyncEngine(config)
    return engine.sync_all_dependencies()
