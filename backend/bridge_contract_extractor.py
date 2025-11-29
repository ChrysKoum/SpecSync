"""
Contract extractor for SpecSync Bridge.
Extracts API contracts from code (Python FastAPI).
"""
import ast
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class ContractExtractor:
    """Extracts API contracts from Python FastAPI code."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
    
    def extract_from_files(self, file_patterns: List[str]) -> Dict[str, Any]:
        """
        Extract contracts from Python files.
        
        Args:
            file_patterns: List of glob patterns (e.g., ["backend/**/*.py"])
            
        Returns:
            Contract dictionary
        """
        endpoints = []
        models = {}
        seen_endpoints = set()  # Track unique endpoints by (method, path)
        
        for pattern in file_patterns:
            # Sort files for deterministic ordering
            files = sorted(self.repo_root.glob(pattern))
            for file_path in files:
                if file_path.is_file():
                    file_endpoints, file_models = self._extract_from_file(file_path)
                    
                    # Handle duplicate endpoint detection
                    for endpoint in file_endpoints:
                        endpoint_key = (endpoint['method'], endpoint['path'])
                        if endpoint_key not in seen_endpoints:
                            endpoints.append(endpoint)
                            seen_endpoints.add(endpoint_key)
                        # Silently skip duplicates - first occurrence wins
                    
                    models.update(file_models)
        
        return {
            'version': '1.0',
            'repo_id': self.repo_root.name,
            'role': 'provider',
            'last_updated': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'endpoints': endpoints,
            'models': models
        }
    
    def _extract_from_file(self, file_path: Path) -> tuple:
        """Extract endpoints and models from a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except:
            return [], {}
        
        endpoints = []
        models = {}
        
        for node in ast.walk(tree):
            # Extract FastAPI endpoints
            if isinstance(node, ast.FunctionDef):
                endpoint = self._extract_endpoint(node, file_path)
                if endpoint:
                    endpoints.append(endpoint)
            
            # Extract Pydantic models
            if isinstance(node, ast.ClassDef):
                model = self._extract_model(node)
                if model:
                    models[node.name] = model
        
        return endpoints, models
    
    def _extract_endpoint(self, node: ast.FunctionDef, file_path: Path) -> Optional[Dict]:
        """Extract endpoint information from a function definition."""
        # Look for FastAPI decorators (@app.get, @app.post, etc.)
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    method = decorator.func.attr.upper()
                    
                    # Get the path from decorator arguments
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
                        
                        # Extract return type
                        return_type = self._extract_return_type(node)
                        
                        # Extract parameters
                        parameters = self._extract_parameters(node)
                        
                        return {
                            'id': f"{method.lower()}-{path.replace('/', '-').strip('-')}",
                            'path': path,
                            'method': method,
                            'status': 'implemented',
                            'implemented_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                            'source_file': str(file_path.relative_to(self.repo_root)),
                            'function_name': node.name,
                            'parameters': parameters,
                            'response': return_type
                        }
        
        return None
    
    def _extract_return_type(self, node: ast.FunctionDef) -> Dict:
        """Extract return type annotation."""
        if node.returns:
            return_type = ast.unparse(node.returns)
            
            # Parse common types
            if 'List[' in return_type:
                return {
                    'status': 200,
                    'type': 'array',
                    'items': return_type.replace('List[', '').replace(']', '')
                }
            else:
                return {
                    'status': 200,
                    'type': 'object',
                    'schema': return_type
                }
        
        return {'status': 200, 'type': 'unknown'}
    
    def _extract_parameters(self, node: ast.FunctionDef) -> List[Dict]:
        """Extract function parameters."""
        parameters = []
        
        for arg in node.args.args:
            if arg.arg not in ['self', 'cls']:
                param = {
                    'name': arg.arg,
                    'required': True
                }
                
                # Extract type annotation
                if arg.annotation:
                    param['type'] = ast.unparse(arg.annotation)
                
                parameters.append(param)
        
        return parameters
    
    def _extract_model(self, node: ast.ClassDef) -> Optional[Dict]:
        """Extract Pydantic model information."""
        # Check if it's a Pydantic model (has BaseModel in bases)
        is_pydantic = any(
            isinstance(base, ast.Name) and base.id == 'BaseModel'
            for base in node.bases
        )
        
        if not is_pydantic:
            return None
        
        fields = []
        
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field = {
                    'name': item.target.id,
                    'type': ast.unparse(item.annotation) if item.annotation else 'unknown'
                }
                fields.append(field)
        
        return {'fields': fields}
    
    def save_contract(self, contract: Dict, output_path: str = ".kiro/contracts/provided-api.yaml"):
        """Save contract to YAML file."""
        output_file = self.repo_root / output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(contract, f, default_flow_style=False, sort_keys=False)
        
        return output_file


def extract_provider_contract(repo_root: str = ".", 
                              file_patterns: List[str] = None) -> str:
    """
    Extract and save provider contract.
    
    Args:
        repo_root: Root directory of the repository
        file_patterns: Patterns to search for code files
        
    Returns:
        Path to saved contract file
    """
    if file_patterns is None:
        file_patterns = ["backend/**/*.py", "*.py"]
    
    extractor = ContractExtractor(repo_root)
    contract = extractor.extract_from_files(file_patterns)
    output_path = extractor.save_contract(contract)
    
    return str(output_path)


if __name__ == '__main__':
    # Test extraction
    contract_path = extract_provider_contract()
    print(f"✓ Contract extracted to: {contract_path}")
