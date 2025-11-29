"""
Breaking change detection for SpecSync Bridge.

This module helps providers detect when they're making breaking changes
that could affect consumers.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import yaml

from backend.bridge_models import Contract, Endpoint, load_contract_from_yaml


@dataclass
class BreakingChange:
    """Represents a breaking change detected in a provider contract."""
    type: str  # "endpoint_removed", "endpoint_modified", "unused_endpoint"
    severity: str  # "error", "warning", "info"
    endpoint: str
    method: str
    message: str
    affected_consumers: List[str]
    suggestion: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'type': self.type,
            'severity': self.severity,
            'endpoint': self.endpoint,
            'method': self.method,
            'message': self.message,
            'affected_consumers': self.affected_consumers,
            'suggestion': self.suggestion
        }


class BreakingChangeDetector:
    """
    Detects breaking changes in provider contracts.
    
    This class helps providers understand the impact of their changes
    by checking which endpoints have consumers and warning about
    modifications or removals.
    """
    
    def __init__(self, repo_root: str = "."):
        """
        Initialize breaking change detector.
        
        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = Path(repo_root)
    
    def detect_breaking_changes(
        self, 
        old_contract: Contract, 
        new_contract: Contract
    ) -> List[BreakingChange]:
        """
        Detect breaking changes between two contract versions.
        
        Args:
            old_contract: Previous contract version
            new_contract: New contract version
            
        Returns:
            List of breaking changes detected
        """
        changes = []
        
        # Create lookup maps by (method, path)
        old_endpoints = {
            (ep.method if hasattr(ep, 'method') else ep['method'], 
             ep.path if hasattr(ep, 'path') else ep['path']): ep
            for ep in old_contract.endpoints
        }
        
        new_endpoints = {
            (ep.method if hasattr(ep, 'method') else ep['method'],
             ep.path if hasattr(ep, 'path') else ep['path']): ep
            for ep in new_contract.endpoints
        }
        
        # Check for removed endpoints
        for key, endpoint in old_endpoints.items():
            if key not in new_endpoints:
                # Endpoint was removed
                consumers = self._get_endpoint_consumers(endpoint)
                
                if consumers:
                    # Breaking change - endpoint has consumers
                    changes.append(BreakingChange(
                        type="endpoint_removed",
                        severity="error",
                        endpoint=self._get_endpoint_path(endpoint),
                        method=self._get_endpoint_method(endpoint),
                        message=f"Endpoint {self._get_endpoint_method(endpoint)} {self._get_endpoint_path(endpoint)} was removed but has active consumers",
                        affected_consumers=consumers,
                        suggestion=f"Consider deprecating instead of removing, or notify consumers: {', '.join(consumers)}"
                    ))
        
        # Check for modified endpoints
        for key in old_endpoints.keys() & new_endpoints.keys():
            old_ep = old_endpoints[key]
            new_ep = new_endpoints[key]
            
            # Check if endpoint was modified
            if self._endpoint_modified(old_ep, new_ep):
                consumers = self._get_endpoint_consumers(old_ep)
                
                if consumers:
                    # Breaking change - modified endpoint has consumers
                    changes.append(BreakingChange(
                        type="endpoint_modified",
                        severity="warning",
                        endpoint=self._get_endpoint_path(old_ep),
                        method=self._get_endpoint_method(old_ep),
                        message=f"Endpoint {self._get_endpoint_method(old_ep)} {self._get_endpoint_path(old_ep)} was modified and has active consumers",
                        affected_consumers=consumers,
                        suggestion=f"Verify changes are backward compatible, or notify consumers: {', '.join(consumers)}"
                    ))
        
        # Check for unused endpoints
        unused = self._identify_unused_endpoints(new_contract)
        changes.extend(unused)
        
        return changes
    
    def _get_endpoint_consumers(self, endpoint: Any) -> List[str]:
        """
        Get list of consumers for an endpoint.
        
        Args:
            endpoint: Endpoint object or dict
            
        Returns:
            List of consumer names
        """
        if hasattr(endpoint, 'consumers'):
            return endpoint.consumers or []
        elif isinstance(endpoint, dict):
            return endpoint.get('consumers', [])
        return []
    
    def _get_endpoint_path(self, endpoint: Any) -> str:
        """Get endpoint path."""
        if hasattr(endpoint, 'path'):
            return endpoint.path
        return endpoint.get('path', '')
    
    def _get_endpoint_method(self, endpoint: Any) -> str:
        """Get endpoint method."""
        if hasattr(endpoint, 'method'):
            return endpoint.method
        return endpoint.get('method', '')
    
    def _endpoint_modified(self, old_ep: Any, new_ep: Any) -> bool:
        """
        Check if an endpoint was modified.
        
        Args:
            old_ep: Old endpoint
            new_ep: New endpoint
            
        Returns:
            True if endpoint was modified
        """
        # Convert to dicts for comparison
        old_dict = old_ep.to_dict() if hasattr(old_ep, 'to_dict') else old_ep
        new_dict = new_ep.to_dict() if hasattr(new_ep, 'to_dict') else new_ep
        
        # Compare relevant fields (ignore timestamps and consumers)
        old_compare = {k: v for k, v in old_dict.items() 
                      if k not in ['implemented_at', 'consumers', 'source_file', 'function_name']}
        new_compare = {k: v for k, v in new_dict.items() 
                      if k not in ['implemented_at', 'consumers', 'source_file', 'function_name']}
        
        return old_compare != new_compare
    
    def _identify_unused_endpoints(self, contract: Contract) -> List[BreakingChange]:
        """
        Identify endpoints with no consumers.
        
        Args:
            contract: Contract to check
            
        Returns:
            List of unused endpoint warnings
        """
        unused = []
        
        for endpoint in contract.endpoints:
            consumers = self._get_endpoint_consumers(endpoint)
            
            if not consumers:
                # No consumers - potentially removable
                unused.append(BreakingChange(
                    type="unused_endpoint",
                    severity="info",
                    endpoint=self._get_endpoint_path(endpoint),
                    method=self._get_endpoint_method(endpoint),
                    message=f"Endpoint {self._get_endpoint_method(endpoint)} {self._get_endpoint_path(endpoint)} has no recorded consumers",
                    affected_consumers=[],
                    suggestion="This endpoint may be safe to remove or deprecate"
                ))
        
        return unused
    
    def load_consumer_expectations(self, dependency_name: str) -> Dict[str, List[str]]:
        """
        Load consumer expectations for a dependency.
        
        Args:
            dependency_name: Name of the dependency
            
        Returns:
            Dictionary mapping endpoints to usage locations
        """
        expectations_file = self.repo_root / f".kiro/contracts/{dependency_name}-expectations.yaml"
        
        if not expectations_file.exists():
            return {}
        
        try:
            with open(expectations_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            expectations = {}
            for exp in data.get('expectations', []):
                endpoint = exp.get('endpoint', '')
                locations = exp.get('usage_locations', [])
                expectations[endpoint] = locations
            
            return expectations
        except Exception:
            return {}
    
    def update_contract_with_consumers(
        self, 
        contract_path: str,
        consumer_name: str,
        expectations: Dict[str, List[str]]
    ) -> None:
        """
        Update a provider contract with consumer information.
        
        Args:
            contract_path: Path to the contract file
            consumer_name: Name of the consumer
            expectations: Dictionary of endpoint expectations
        """
        # Load the contract
        contract = load_contract_from_yaml(contract_path)
        
        # Update each endpoint with consumer info
        for endpoint in contract.endpoints:
            endpoint_key = f"{self._get_endpoint_method(endpoint)} {self._get_endpoint_path(endpoint)}"
            
            if endpoint_key in expectations:
                # This endpoint is used by the consumer
                consumers = self._get_endpoint_consumers(endpoint)
                
                if consumer_name not in consumers:
                    consumers.append(consumer_name)
                    
                    # Update the endpoint
                    if hasattr(endpoint, 'consumers'):
                        endpoint.consumers = consumers
                    elif isinstance(endpoint, dict):
                        endpoint['consumers'] = consumers
        
        # Save the updated contract
        contract.save_to_yaml(contract_path)


def detect_breaking_changes(
    old_contract_path: str,
    new_contract_path: str,
    repo_root: str = "."
) -> List[BreakingChange]:
    """
    Convenience function to detect breaking changes.
    
    Args:
        old_contract_path: Path to old contract
        new_contract_path: Path to new contract
        repo_root: Repository root directory
        
    Returns:
        List of breaking changes
    """
    old_contract = load_contract_from_yaml(old_contract_path)
    new_contract = load_contract_from_yaml(new_contract_path)
    
    detector = BreakingChangeDetector(repo_root)
    return detector.detect_breaking_changes(old_contract, new_contract)


def format_breaking_changes(changes: List[BreakingChange]) -> str:
    """
    Format breaking changes as a human-readable string.
    
    Args:
        changes: List of breaking changes
        
    Returns:
        Formatted string
    """
    if not changes:
        return "✓ No breaking changes detected"
    
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append("Breaking Changes Detected")
    lines.append(f"{'='*60}")
    
    errors = [c for c in changes if c.severity == "error"]
    warnings = [c for c in changes if c.severity == "warning"]
    info = [c for c in changes if c.severity == "info"]
    
    if errors:
        lines.append(f"\n🚨 ERRORS ({len(errors)}):")
        for change in errors:
            lines.append(f"\n  {change.method} {change.endpoint}")
            lines.append(f"  Type: {change.type}")
            lines.append(f"  Message: {change.message}")
            if change.affected_consumers:
                lines.append(f"  Affected Consumers: {', '.join(change.affected_consumers)}")
            lines.append(f"  Suggestion: {change.suggestion}")
    
    if warnings:
        lines.append(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for change in warnings:
            lines.append(f"\n  {change.method} {change.endpoint}")
            lines.append(f"  Type: {change.type}")
            lines.append(f"  Message: {change.message}")
            if change.affected_consumers:
                lines.append(f"  Affected Consumers: {', '.join(change.affected_consumers)}")
            lines.append(f"  Suggestion: {change.suggestion}")
    
    if info:
        lines.append(f"\nℹ️  INFO ({len(info)}):")
        for change in info:
            lines.append(f"\n  {change.method} {change.endpoint}")
            lines.append(f"  Message: {change.message}")
            lines.append(f"  Suggestion: {change.suggestion}")
    
    lines.append(f"\n{'='*60}\n")
    return "\n".join(lines)
