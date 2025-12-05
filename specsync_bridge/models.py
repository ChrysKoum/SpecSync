"""
Data models for SpecSync Bridge.
Defines contract schema classes and configuration models.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import json
import yaml


@dataclass
class Endpoint:
    """Represents an API endpoint in a contract."""
    id: str
    path: str
    method: str
    status: str = "implemented"
    implemented_at: Optional[str] = None
    source_file: Optional[str] = None
    function_name: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    response: Dict[str, Any] = field(default_factory=dict)
    consumers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Endpoint':
        return cls(**data)


@dataclass
class Model:
    """Represents a data model in a contract."""
    name: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Model':
        return cls(**data)


@dataclass
class Contract:
    """Represents a complete API contract."""
    version: str
    repo_id: str
    role: str
    last_updated: str
    endpoints: List[Endpoint] = field(default_factory=list)
    models: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'repo_id': self.repo_id,
            'role': self.role,
            'last_updated': self.last_updated,
            'endpoints': [ep.to_dict() if isinstance(ep, Endpoint) else ep for ep in self.endpoints],
            'models': self.models
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Contract':
        endpoints = [
            Endpoint.from_dict(ep) if isinstance(ep, dict) else ep 
            for ep in data.get('endpoints', [])
        ]
        return cls(
            version=data['version'],
            repo_id=data['repo_id'],
            role=data['role'],
            last_updated=data['last_updated'],
            endpoints=endpoints,
            models=data.get('models', {})
        )
    
    def save_to_yaml(self, file_path: str) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        return path
    
    @classmethod
    def load_from_yaml(cls, file_path: str) -> 'Contract':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class Dependency:
    """Represents a dependency configuration."""
    name: str
    type: str
    sync_method: str
    contract_path: str
    local_cache: str
    git_url: Optional[str] = None
    sync_on_commit: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dependency':
        return cls(**data)


@dataclass
class AutoSyncConfig:
    """Auto-sync configuration."""
    enabled: bool = False
    on_startup: bool = True
    interval: Optional[str] = "1h"  # none, 30min, 1h, 2h, 3h, 6h
    silent: bool = True
    notify_on_changes: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutoSyncConfig':
        return cls(**data)
    
    def get_interval_seconds(self) -> Optional[int]:
        """Convert interval string to seconds."""
        if not self.interval or self.interval == "none":
            return None
        intervals = {
            "30min": 1800,
            "1h": 3600,
            "2h": 7200,
            "3h": 10800,
            "6h": 21600
        }
        return intervals.get(self.interval)


@dataclass
class BridgeConfig:
    """Manages bridge configuration."""
    enabled: bool = True
    role: str = "consumer"
    repo_id: str = ""
    provides: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, Dependency] = field(default_factory=dict)
    auto_sync: AutoSyncConfig = field(default_factory=AutoSyncConfig)
    config_path: str = ".kiro/settings/bridge.json"
    
    def __post_init__(self):
        if self.dependencies:
            self.dependencies = {
                name: Dependency.from_dict(dep) if isinstance(dep, dict) else dep
                for name, dep in self.dependencies.items()
            }
        if isinstance(self.auto_sync, dict):
            self.auto_sync = AutoSyncConfig.from_dict(self.auto_sync)
    
    def load(self) -> 'BridgeConfig':
        path = Path(self.config_path)
        if not path.exists():
            return self
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        bridge_data = data.get('bridge', {})
        self.enabled = bridge_data.get('enabled', True)
        self.role = bridge_data.get('role', 'consumer')
        self.repo_id = bridge_data.get('repo_id', '')
        self.provides = bridge_data.get('provides', {})
        deps_data = bridge_data.get('dependencies', {})
        self.dependencies = {
            name: Dependency.from_dict(dep_data)
            for name, dep_data in deps_data.items()
        }
        auto_sync_data = bridge_data.get('auto_sync', {})
        if auto_sync_data:
            self.auto_sync = AutoSyncConfig.from_dict(auto_sync_data)
        return self
    
    def save(self) -> None:
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            'bridge': {
                'enabled': self.enabled,
                'role': self.role,
                'repo_id': self.repo_id,
                'provides': self.provides,
                'dependencies': {
                    name: dep.to_dict()
                    for name, dep in self.dependencies.items()
                },
                'auto_sync': self.auto_sync.to_dict() if isinstance(self.auto_sync, AutoSyncConfig) else self.auto_sync
            }
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
    
    def add_dependency(self, name: str, dependency: Dependency) -> None:
        self.dependencies[name] = dependency
        self.save()
    
    def remove_dependency(self, name: str) -> None:
        if name in self.dependencies:
            dep = self.dependencies[name]
            cached_file = Path(dep.local_cache)
            del self.dependencies[name]
            self.save()
            if cached_file.exists():
                cached_file.unlink()
    
    def get_dependency(self, name: str) -> Optional[Dependency]:
        return self.dependencies.get(name)
    
    def list_dependencies(self) -> List[str]:
        return list(self.dependencies.keys())
    
    def validate(self) -> List[str]:
        errors = []
        if not self.role:
            errors.append("Role is required")
        if self.role not in ['consumer', 'provider', 'both']:
            errors.append(f"Invalid role: {self.role}")
        for name, dep in self.dependencies.items():
            if not dep.name:
                errors.append(f"Dependency {name}: name is required")
            if not dep.type:
                errors.append(f"Dependency {name}: type is required")
            if not dep.sync_method:
                errors.append(f"Dependency {name}: sync_method is required")
            if dep.sync_method == 'git' and not dep.git_url:
                errors.append(f"Dependency {name}: git_url is required for git sync")
            if not dep.contract_path:
                errors.append(f"Dependency {name}: contract_path is required")
            if not dep.local_cache:
                errors.append(f"Dependency {name}: local_cache is required")
        return errors
    
    @classmethod
    def create_default(cls, role: str = "consumer", config_path: str = ".kiro/settings/bridge.json") -> 'BridgeConfig':
        config = cls(enabled=True, role=role, repo_id="", config_path=config_path)
        if role in ['provider', 'both']:
            config.provides = {
                'contract_file': '.kiro/contracts/provided-api.yaml',
                'extract_from': ['**/*.py'],
                'auto_update': True
            }
        return config


@dataclass
class SyncResult:
    """Result of a sync operation."""
    dependency_name: str
    success: bool
    changes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    endpoint_count: int = 0
    cached_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriftIssue:
    """Represents a drift issue between consumer and provider."""
    type: str
    severity: str
    endpoint: str
    method: str
    location: str
    message: str
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_contract_from_yaml(file_path: str) -> Contract:
    return Contract.load_from_yaml(file_path)


def load_config(config_path: str = ".kiro/settings/bridge.json") -> BridgeConfig:
    config = BridgeConfig(config_path=config_path)
    return config.load()
