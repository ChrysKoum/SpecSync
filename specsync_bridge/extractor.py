"""
Contract extractor for SpecSync Bridge.
Extracts API contracts from Python code (FastAPI, Flask, etc.).
"""
import ast
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class ContractExtractor:
    """Extracts API contracts from Python code."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
    
    def extract_from_files(self, file_patterns: List[str]) -> Dict[str, Any]:
        endpoints = []
        models = {}
        seen_endpoints = set()
        
        for pattern in file_patterns:
            files = sorted(self.repo_root.glob(pattern))
            for file_path in files:
                if file_path.is_file() and not self._should_skip(file_path):
                    file_endpoints, file_models = self._extract_from_file(file_path)
                    for endpoint in file_endpoints:
                        key = (endpoint['method'], endpoint['path'])
                        if key not in seen_endpoints:
                            endpoints.append(endpoint)
                            seen_endpoints.add(key)
                    models.update(file_models)
        
        return {
            'version': '1.0',
            'repo_id': self.repo_root.name,
            'role': 'provider',
            'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'endpoints': endpoints,
            'models': models
        }
    
    def _should_skip(self, file_path: Path) -> bool:
        skip_patterns = ['test_', '_test.py', 'conftest', '__pycache__', '.venv', 'node_modules']
        return any(p in str(file_path) for p in skip_patterns)
    
    def _extract_from_file(self, file_path: Path) -> tuple:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except:
            return [], {}
        
        endpoints = []
        models = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                endpoint = self._extract_endpoint(node, file_path)
                if endpoint:
                    endpoints.append(endpoint)
            if isinstance(node, ast.ClassDef):
                model = self._extract_model(node)
                if model:
                    models[node.name] = model
        
        return endpoints, models
    
    def _extract_endpoint(self, node: ast.FunctionDef, file_path: Path) -> Optional[Dict]:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                method = decorator.func.attr.upper()
                if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
                        return {
                            'id': f"{method.lower()}-{path.replace('/', '-').strip('-')}",
                            'path': path,
                            'method': method,
                            'status': 'implemented',
                            'implemented_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                            'source_file': str(file_path.relative_to(self.repo_root)),
                            'function_name': node.name,
                            'parameters': self._extract_parameters(node),
                            'response': self._extract_return_type(node)
                        }
        return None
    
    def _extract_parameters(self, node: ast.FunctionDef) -> List[Dict]:
        params = []
        for arg in node.args.args:
            if arg.arg not in ['self', 'cls']:
                param = {'name': arg.arg, 'required': True}
                if arg.annotation:
                    param['type'] = ast.unparse(arg.annotation)
                params.append(param)
        return params
    
    def _extract_return_type(self, node: ast.FunctionDef) -> Dict:
        if node.returns:
            return_type = ast.unparse(node.returns)
            if 'List[' in return_type:
                return {'status': 200, 'type': 'array', 'items': return_type.replace('List[', '').replace(']', '')}
            return {'status': 200, 'type': 'object', 'schema': return_type}
        return {'status': 200, 'type': 'unknown'}
    
    def _extract_model(self, node: ast.ClassDef) -> Optional[Dict]:
        is_pydantic = any(
            isinstance(base, ast.Name) and base.id == 'BaseModel'
            for base in node.bases
        )
        if not is_pydantic:
            return None
        
        fields = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append({
                    'name': item.target.id,
                    'type': ast.unparse(item.annotation) if item.annotation else 'unknown'
                })
        return {'fields': fields}
    
    def save_contract(self, contract: Dict, output_path: str = ".kiro/contracts/provided-api.yaml") -> Path:
        output_file = self.repo_root / output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(contract, f, default_flow_style=False, sort_keys=False)
        return output_file


def extract_provider_contract(repo_root: str = ".", file_patterns: List[str] = None) -> str:
    if file_patterns is None:
        file_patterns = ["**/*.py"]
    extractor = ContractExtractor(repo_root)
    contract = extractor.extract_from_files(file_patterns)
    output_path = extractor.save_contract(contract)
    return str(output_path)


def detect_repo_role(repo_root: str = ".") -> dict:
    """
    Auto-detect if this repo is a provider, consumer, or both.
    
    Detection logic:
    - Provider: Has FastAPI/Flask endpoints (provides APIs)
    - Consumer: Has HTTP client calls (requests, httpx, etc.)
    - Both: Has both endpoints and client calls
    
    Returns:
        dict with 'role', 'has_endpoints', 'has_api_calls', 'suggestion'
    """
    import ast
    from pathlib import Path
    
    root = Path(repo_root)
    has_endpoints = False
    has_api_calls = False
    endpoint_count = 0
    api_call_count = 0
    
    # Scan Python files
    for py_file in root.glob("**/*.py"):
        # Skip test files and venv
        if any(s in str(py_file) for s in ['test', '.venv', '__pycache__', 'node_modules']):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
        except:
            continue
        
        for node in ast.walk(tree):
            # Check for endpoint decorators (provider) - supports @app.get, @router.get, etc.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        method = dec.func.attr.lower()
                        if method in ['get', 'post', 'put', 'delete', 'patch']:
                            # Check if it's a web framework decorator
                            if isinstance(dec.func.value, ast.Name):
                                obj_name = dec.func.value.id.lower()
                                if obj_name in ['app', 'router', 'api', 'blueprint', 'route']:
                                    has_endpoints = True
                                    endpoint_count += 1
            
            # Check for HTTP client calls (consumer)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method = node.func.attr.lower()
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    if isinstance(node.func.value, ast.Name):
                        lib = node.func.value.id
                        if lib in ['requests', 'httpx', 'client', 'session']:
                            has_api_calls = True
                            api_call_count += 1
    
    # Determine role
    if has_endpoints and has_api_calls:
        role = "both"
        suggestion = "This repo both provides and consumes APIs (microservice pattern)"
    elif has_endpoints:
        role = "provider"
        suggestion = f"Detected {endpoint_count} API endpoint(s). This repo provides APIs."
    elif has_api_calls:
        role = "consumer"
        suggestion = f"Detected {api_call_count} API call(s). This repo consumes external APIs."
    else:
        role = "unknown"
        suggestion = "No API endpoints or calls detected. Choose role manually."
    
    return {
        "role": role,
        "has_endpoints": has_endpoints,
        "has_api_calls": has_api_calls,
        "endpoint_count": endpoint_count,
        "api_call_count": api_call_count,
        "suggestion": suggestion
    }
