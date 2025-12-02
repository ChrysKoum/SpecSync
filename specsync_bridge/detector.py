"""
Bridge Drift Detector for API call validation.
Detects drift between consumer API calls and provider contracts.
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from specsync_bridge.models import Contract, DriftIssue, BridgeConfig, load_contract_from_yaml


@dataclass
class APICall:
    """Represents an API call found in consumer code."""
    method: str
    path: str
    file_path: str
    line_number: int


class BridgeDriftDetector:
    """Detects drift between consumer API calls and provider contracts."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.config = BridgeConfig(config_path=str(self.repo_root / ".kiro/settings/bridge.json"))
        self.config.load()
    
    def detect_drift(self, dependency_name: str) -> List[DriftIssue]:
        dependency = self.config.get_dependency(dependency_name)
        if not dependency:
            return [DriftIssue(
                type="configuration_error", severity="error",
                endpoint="", method="", location="",
                message=f"Dependency '{dependency_name}' not found",
                suggestion="Add the dependency first"
            )]
        
        cache_path = self.repo_root / dependency.local_cache
        if not cache_path.exists():
            return [DriftIssue(
                type="missing_contract", severity="error",
                endpoint="", method="", location="",
                message=f"Contract not found: {dependency.local_cache}",
                suggestion="Run 'specsync-bridge sync' first"
            )]
        
        try:
            contract = load_contract_from_yaml(str(cache_path))
        except Exception as e:
            return [DriftIssue(
                type="invalid_contract", severity="error",
                endpoint="", method="", location="",
                message=f"Failed to load contract: {e}",
                suggestion="Check contract format or re-sync"
            )]
        
        api_calls = self._find_api_calls()
        issues = []
        for call in api_calls:
            issue = self._check_endpoint(call, contract)
            if issue:
                issues.append(issue)
        return issues
    
    def detect_all_drift(self) -> Dict[str, List[DriftIssue]]:
        return {name: self.detect_drift(name) for name in self.config.list_dependencies()}
    
    def _find_api_calls(self) -> List[APICall]:
        calls = []
        for py_file in self.repo_root.glob("**/*.py"):
            if self._should_skip(py_file):
                continue
            try:
                calls.extend(self._extract_calls_from_file(py_file))
            except:
                continue
        return calls
    
    def _should_skip(self, path: Path) -> bool:
        skip = ['test', '.venv', '__pycache__', 'node_modules']
        return any(s in str(path) for s in skip)
    
    def _extract_calls_from_file(self, file_path: Path) -> List[APICall]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            tree = ast.parse(content)
        except:
            return []
        
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = self._parse_call(node, file_path)
                if call:
                    calls.append(call)
        return calls
    
    def _parse_call(self, node: ast.Call, file_path: Path) -> Optional[APICall]:
        if not isinstance(node.func, ast.Attribute):
            return None
        
        method = node.func.attr.upper()
        if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            return None
        
        if isinstance(node.func.value, ast.Name):
            if node.func.value.id not in ['requests', 'httpx', 'client', 'session']:
                return None
        else:
            return None
        
        if not node.args:
            return None
        
        url = self._extract_url(node.args[0])
        if not url:
            return None
        
        path = self._url_to_path(url)
        return APICall(
            method=method,
            path=path,
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=node.lineno
        )
    
    def _extract_url(self, node) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                else:
                    parts.append("{}")
            return "".join(parts)
        return None
    
    def _url_to_path(self, url: str) -> str:
        if '://' in url:
            url = url.split('://', 1)[1]
            if '/' in url:
                url = '/' + url.split('/', 1)[1]
            else:
                url = '/'
        if not url.startswith('/'):
            url = '/' + url
        return url.split('?')[0].split('#')[0]
    
    def _check_endpoint(self, call: APICall, contract: Contract) -> Optional[DriftIssue]:
        call_path = re.sub(r'\{[^}]+\}', '{param}', call.path)
        
        for ep in contract.endpoints:
            ep_path = re.sub(r'\{[^}]+\}', '{param}', ep.path)
            if call_path == ep_path and call.method == ep.method:
                return None
        
        return DriftIssue(
            type="missing_endpoint",
            severity="error",
            endpoint=call.path,
            method=call.method,
            location=f"{call.file_path}:{call.line_number}",
            message=f"API call {call.method} {call.path} not in contract",
            suggestion="Sync latest contract or remove this call"
        )


def detect_drift(dependency_name: str, repo_root: str = ".") -> List[DriftIssue]:
    return BridgeDriftDetector(repo_root).detect_drift(dependency_name)


def detect_all_drift(repo_root: str = ".") -> Dict[str, List[DriftIssue]]:
    return BridgeDriftDetector(repo_root).detect_all_drift()
