"""
Data models for SpecSync Bridge.
Defines contract schema classes and configuration models.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import yaml


# ============================================================================
# Contract Schema Classes
# ============================================================================

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
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Endpoint':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Model:
    """Represents a data model in a contract."""
    name: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Model':
        """Create from dictionary."""
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
        """Convert to dictionary."""
        data = {
            'version': self.version,
            'repo_id': self.repo_id,
            'role': self.role,
            'last_updated': self.last_updated,
            'endpoints': [ep.to_dict() if isinstance(ep, Endpoint) else ep for ep in self.endpoints],
            'models': self.models
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Contract':
        """Create from dictionary."""
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
        """Save contract to YAML file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        return path
    
    @classmethod
    def load_from_yaml(cls, file_path: str) -> 'Contract':
        """Load contract from YAML file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


# ============================================================================
# Configuration Data Models
# ============================================================================

@dataclass
class Dependency:
    """Represents a dependency configuration."""
    name: str
    type: str  # "http-api", "graphql", "grpc"
    sync_method: str  # "git", "http", "s3"
    contract_path: str
    local_cache: str
    git_url: Optional[str] = None
    sync_on_commit: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dependency':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BridgeConfig:
    """Manages bridge configuration."""
    enabled: bool = True
    role: str = "consumer"  # "consumer", "provider", "both"
    repo_id: str = ""
    provides: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, Dependency] = field(default_factory=dict)
    config_path: str = ".kiro/settings/bridge.json"
    
    def __post_init__(self):
        """Initialize after creation."""
        # Convert dependency dicts to Dependency objects if needed
        if self.dependencies:
            self.dependencies = {
                name: Dependency.from_dict(dep) if isinstance(dep, dict) else dep
                for name, dep in self.dependencies.items()
            }
    
    def load(self) -> 'BridgeConfig':
        """Load configuration from file."""
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
        
        # Load dependencies
        deps_data = bridge_data.get('dependencies', {})
        self.dependencies = {
            name: Dependency.from_dict(dep_data)
            for name, dep_data in deps_data.items()
        }
        
        return self
    
    def save(self) -> None:
        """Save configuration to file."""
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict format
        config_data = {
            'bridge': {
                'enabled': self.enabled,
                'role': self.role,
                'repo_id': self.repo_id,
                'provides': self.provides,
                'dependencies': {
                    name: dep.to_dict()
                    for name, dep in self.dependencies.items()
                }
            }
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
    
    def add_dependency(self, name: str, dependency: Dependency) -> None:
        """Add a dependency to the configuration."""
        self.dependencies[name] = dependency
        self.save()
    
    def remove_dependency(self, name: str) -> None:
        """
        Remove a dependency from the configuration.
        Also deletes the cached contract file if it exists.
        """
        if name in self.dependencies:
            # Get the cached contract path before removing
            dep = self.dependencies[name]
            cached_file = Path(dep.local_cache)
            
            # Remove from config
            del self.dependencies[name]
            self.save()
            
            # Delete cached contract file if it exists
            if cached_file.exists():
                cached_file.unlink()
    
    def get_dependency(self, name: str) -> Optional[Dependency]:
        """Get a dependency by name."""
        return self.dependencies.get(name)
    
    def list_dependencies(self) -> List[str]:
        """List all dependency names."""
        return list(self.dependencies.keys())
    
    def validate(self) -> List[str]:
        """
        Validate configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.role:
            errors.append("Role is required")
        
        if self.role not in ['consumer', 'provider', 'both']:
            errors.append(f"Invalid role: {self.role}")
        
        # Validate dependencies
        for name, dep in self.dependencies.items():
            if not dep.name:
                errors.append(f"Dependency {name}: name is required")
            
            if not dep.type:
                errors.append(f"Dependency {name}: type is required")
            
            if not dep.sync_method:
                errors.append(f"Dependency {name}: sync_method is required")
            
            if dep.sync_method == 'git' and not dep.git_url:
                errors.append(f"Dependency {name}: git_url is required for git sync method")
            
            if not dep.contract_path:
                errors.append(f"Dependency {name}: contract_path is required")
            
            if not dep.local_cache:
                errors.append(f"Dependency {name}: local_cache is required")
        
        return errors
    
    @classmethod
    def create_default(cls, role: str = "consumer", config_path: str = ".kiro/settings/bridge.json") -> 'BridgeConfig':
        """Create a default configuration."""
        config = cls(
            enabled=True,
            role=role,
            repo_id="",
            config_path=config_path
        )
        
        if role in ['provider', 'both']:
            config.provides = {
                'contract_file': '.kiro/contracts/provided-api.yaml',
                'extract_from': ['backend/**/*.py'],
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
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    endpoint_count: int = 0
    cached_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncResult':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class DriftIssue:
    """Represents a drift issue between consumer and provider."""
    type: str  # "missing_endpoint", "parameter_mismatch", "method_mismatch", etc.
    severity: str  # "error", "warning"
    endpoint: str
    method: str
    location: str  # File and line number
    message: str
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DriftIssue':
        """Create from dictionary."""
        return cls(**data)


# ============================================================================
# Utility Functions
# ============================================================================

def load_contract_from_yaml(file_path: str) -> Contract:
    """Load a contract from a YAML file."""
    return Contract.load_from_yaml(file_path)


def save_contract_to_yaml(contract: Contract, file_path: str) -> Path:
    """Save a contract to a YAML file."""
    return contract.save_to_yaml(file_path)


def load_config(config_path: str = ".kiro/settings/bridge.json") -> BridgeConfig:
    """Load bridge configuration."""
    config = BridgeConfig(config_path=config_path)
    return config.load()


def save_config(config: BridgeConfig) -> None:
    """Save bridge configuration."""
    config.save()
