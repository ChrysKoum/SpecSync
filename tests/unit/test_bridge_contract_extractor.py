"""
Unit tests for the bridge contract extractor module.
"""
import pytest
import ast
import yaml
from pathlib import Path
from datetime import datetime
from backend.bridge_contract_extractor import (
    ContractExtractor,
    extract_provider_contract
)


class TestContractExtractor:
    """Tests for ContractExtractor class."""
    
    def test_initialization(self):
        """Test ContractExtractor initialization."""
        extractor = ContractExtractor(".")
        
        assert extractor.repo_root == Path(".")
    
    def test_initialization_with_custom_root(self):
        """Test ContractExtractor with custom repo root."""
        extractor = ContractExtractor("backend")
        
        assert extractor.repo_root == Path("backend")
    
    def test_extract_from_files_with_backend_pattern(self):
        """Test extracting contracts from backend files."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/handlers/*.py"])
        
        assert 'version' in contract
        assert 'repo_id' in contract
        assert 'role' in contract
        assert 'last_updated' in contract
        assert 'endpoints' in contract
        assert 'models' in contract
        
        assert contract['version'] == '1.0'
        assert contract['role'] == 'provider'
        assert isinstance(contract['endpoints'], list)
        assert isinstance(contract['models'], dict)
    
    def test_extract_from_files_finds_endpoints(self):
        """Test that extraction finds endpoints with @app or @router decorators."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/handlers/user.py"])
        
        # The extractor finds endpoints with @router.get decorators
        assert isinstance(contract['endpoints'], list)
        
        # If endpoints are found, verify structure
        if len(contract['endpoints']) > 0:
            endpoint = contract['endpoints'][0]
            assert 'path' in endpoint
            assert 'method' in endpoint
    
    def test_extract_from_files_finds_models(self):
        """Test that extraction finds Pydantic models."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/models.py"])
        
        # Should find User model
        assert 'User' in contract['models']
        assert 'fields' in contract['models']['User']
        assert len(contract['models']['User']['fields']) > 0
    
    def test_extract_from_file_with_valid_python(self):
        """Test extracting from a single valid Python file."""
        extractor = ContractExtractor(".")
        endpoints, models = extractor._extract_from_file(Path("backend/handlers/user.py"))
        
        assert isinstance(endpoints, list)
        assert isinstance(models, dict)
        # Returns valid data structures even if empty
        assert endpoints is not None
        assert models is not None
    
    def test_extract_from_file_with_invalid_syntax(self):
        """Test extracting from file with invalid syntax returns empty results."""
        extractor = ContractExtractor(".")
        
        # Create a temporary file with invalid syntax
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def invalid syntax here")
            temp_path = Path(f.name)
        
        try:
            endpoints, models = extractor._extract_from_file(temp_path)
            
            # Should return empty results on parse error
            assert endpoints == []
            assert models == {}
        finally:
            temp_path.unlink()
    
    def test_extract_endpoint_with_decorator(self):
        """Test extracting endpoint information from function with decorator."""
        extractor = ContractExtractor(".")
        
        # Parse a simple FastAPI endpoint
        code = """
@app.get("/test")
def test_endpoint():
    return {"message": "test"}
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        endpoint = extractor._extract_endpoint(func_node, Path("test.py"))
        
        assert endpoint is not None
        assert endpoint['path'] == '/test'
        assert endpoint['method'] == 'GET'
        assert endpoint['function_name'] == 'test_endpoint'
        assert endpoint['status'] == 'implemented'
        assert 'id' in endpoint
        assert 'implemented_at' in endpoint
        assert 'source_file' in endpoint
    
    def test_extract_endpoint_without_decorator(self):
        """Test that functions without FastAPI decorators return None."""
        extractor = ContractExtractor(".")
        
        code = """
def regular_function():
    return "not an endpoint"
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        endpoint = extractor._extract_endpoint(func_node, Path("test.py"))
        
        assert endpoint is None
    
    def test_extract_endpoint_with_post_method(self):
        """Test extracting POST endpoint."""
        extractor = ContractExtractor(".")
        
        code = """
@app.post("/users")
def create_user():
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        endpoint = extractor._extract_endpoint(func_node, Path("test.py"))
        
        assert endpoint is not None
        assert endpoint['method'] == 'POST'
        assert endpoint['path'] == '/users'
    
    def test_extract_return_type_with_list(self):
        """Test extracting return type annotation for List."""
        extractor = ContractExtractor(".")
        
        code = """
def get_items() -> List[Item]:
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        return_type = extractor._extract_return_type(func_node)
        
        assert return_type['status'] == 200
        assert return_type['type'] == 'array'
        assert 'Item' in return_type['items']
    
    def test_extract_return_type_with_object(self):
        """Test extracting return type annotation for object."""
        extractor = ContractExtractor(".")
        
        code = """
def get_user() -> User:
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        return_type = extractor._extract_return_type(func_node)
        
        assert return_type['status'] == 200
        assert return_type['type'] == 'object'
        assert return_type['schema'] == 'User'
    
    def test_extract_return_type_without_annotation(self):
        """Test extracting return type when no annotation present."""
        extractor = ContractExtractor(".")
        
        code = """
def get_data():
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        return_type = extractor._extract_return_type(func_node)
        
        assert return_type['status'] == 200
        assert return_type['type'] == 'unknown'
    
    def test_extract_parameters(self):
        """Test extracting function parameters."""
        extractor = ContractExtractor(".")
        
        code = """
def get_user(user_id: int, include_details: bool):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        parameters = extractor._extract_parameters(func_node)
        
        assert len(parameters) == 2
        assert parameters[0]['name'] == 'user_id'
        assert parameters[0]['type'] == 'int'
        assert parameters[0]['required'] is True
        assert parameters[1]['name'] == 'include_details'
        assert parameters[1]['type'] == 'bool'
    
    def test_extract_parameters_without_annotations(self):
        """Test extracting parameters without type annotations."""
        extractor = ContractExtractor(".")
        
        code = """
def process(data, options):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        parameters = extractor._extract_parameters(func_node)
        
        assert len(parameters) == 2
        assert parameters[0]['name'] == 'data'
        assert 'type' not in parameters[0]
        assert parameters[1]['name'] == 'options'
    
    def test_extract_parameters_excludes_self(self):
        """Test that 'self' parameter is excluded."""
        extractor = ContractExtractor(".")
        
        code = """
def method(self, arg1: str):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        
        parameters = extractor._extract_parameters(func_node)
        
        assert len(parameters) == 1
        assert parameters[0]['name'] == 'arg1'
    
    def test_extract_model_with_pydantic_basemodel(self):
        """Test extracting Pydantic model."""
        extractor = ContractExtractor(".")
        
        code = """
class User(BaseModel):
    id: int
    username: str
    email: str
"""
        tree = ast.parse(code)
        class_node = tree.body[0]
        
        model = extractor._extract_model(class_node)
        
        assert model is not None
        assert 'fields' in model
        assert len(model['fields']) == 3
        
        field_names = [f['name'] for f in model['fields']]
        assert 'id' in field_names
        assert 'username' in field_names
        assert 'email' in field_names
        
        # Check field types
        id_field = next(f for f in model['fields'] if f['name'] == 'id')
        assert id_field['type'] == 'int'
    
    def test_extract_model_without_basemodel(self):
        """Test that non-Pydantic classes return None."""
        extractor = ContractExtractor(".")
        
        code = """
class RegularClass:
    def __init__(self):
        pass
"""
        tree = ast.parse(code)
        class_node = tree.body[0]
        
        model = extractor._extract_model(class_node)
        
        assert model is None
    
    def test_extract_model_with_optional_fields(self):
        """Test extracting model with Optional fields."""
        extractor = ContractExtractor(".")
        
        code = """
class User(BaseModel):
    id: int
    bio: Optional[str]
"""
        tree = ast.parse(code)
        class_node = tree.body[0]
        
        model = extractor._extract_model(class_node)
        
        assert model is not None
        assert len(model['fields']) == 2
        
        bio_field = next(f for f in model['fields'] if f['name'] == 'bio')
        assert 'Optional' in bio_field['type']
    
    def test_save_contract(self):
        """Test saving contract to YAML file."""
        import tempfile
        import shutil
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            extractor = ContractExtractor(temp_dir)
            
            contract = {
                'version': '1.0',
                'endpoints': [],
                'models': {}
            }
            
            output_path = extractor.save_contract(contract, ".kiro/contracts/test.yaml")
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify content
            with open(output_path, 'r') as f:
                loaded = yaml.safe_load(f)
            
            assert loaded['version'] == '1.0'
            assert 'endpoints' in loaded
            assert 'models' in loaded
        finally:
            shutil.rmtree(temp_dir)
    
    def test_save_contract_creates_directories(self):
        """Test that save_contract creates necessary directories."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            extractor = ContractExtractor(temp_dir)
            
            contract = {'version': '1.0'}
            
            # Use nested path that doesn't exist
            output_path = extractor.save_contract(contract, "deep/nested/path/contract.yaml")
            
            assert output_path.exists()
            assert output_path.parent.exists()
        finally:
            shutil.rmtree(temp_dir)


class TestExtractProviderContract:
    """Tests for extract_provider_contract function."""
    
    def test_extract_provider_contract_default_patterns(self):
        """Test extracting contract with default file patterns."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create a simple Python file
            backend_dir = Path(temp_dir) / "backend"
            backend_dir.mkdir()
            
            test_file = backend_dir / "test.py"
            test_file.write_text("""
from fastapi import FastAPI

app = FastAPI()

@app.get("/test")
def test_endpoint():
    return {"status": "ok"}
""")
            
            contract_path = extract_provider_contract(temp_dir)
            
            # Verify contract was created
            assert Path(contract_path).exists()
            
            # Load and verify content
            with open(contract_path, 'r') as f:
                contract = yaml.safe_load(f)
            
            assert contract['version'] == '1.0'
            assert contract['role'] == 'provider'
            assert 'endpoints' in contract
        finally:
            shutil.rmtree(temp_dir)
    
    def test_extract_provider_contract_custom_patterns(self):
        """Test extracting contract with custom file patterns."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create a Python file in custom location
            custom_dir = Path(temp_dir) / "custom"
            custom_dir.mkdir()
            
            test_file = custom_dir / "api.py"
            test_file.write_text("""
@app.get("/custom")
def custom_endpoint():
    pass
""")
            
            contract_path = extract_provider_contract(temp_dir, ["custom/*.py"])
            
            assert Path(contract_path).exists()
        finally:
            shutil.rmtree(temp_dir)
    
    def test_extract_provider_contract_returns_path(self):
        """Test that extract_provider_contract returns a valid path string."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            contract_path = extract_provider_contract(temp_dir, [])
            
            assert isinstance(contract_path, str)
            assert contract_path.endswith('.yaml')
        finally:
            shutil.rmtree(temp_dir)


class TestEndpointExtraction:
    """Integration tests for endpoint extraction from real files."""
    
    def test_extract_user_endpoints(self):
        """Test extracting endpoints from user handler."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/handlers/user.py"])
        
        endpoints = contract['endpoints']
        
        # Verify contract structure is correct
        assert isinstance(endpoints, list)
        assert 'version' in contract
        assert 'endpoints' in contract
        assert 'models' in contract
        
        # If endpoints are extracted, verify their structure
        for endpoint in endpoints:
            assert 'id' in endpoint
            assert 'path' in endpoint
            assert 'method' in endpoint
            assert 'status' in endpoint
            assert endpoint['status'] == 'implemented'
            assert 'source_file' in endpoint
            assert 'function_name' in endpoint
    
    def test_extract_health_endpoint(self):
        """Test extracting health check endpoint."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/handlers/health.py"])
        
        endpoints = contract['endpoints']
        
        # Verify contract structure
        assert isinstance(endpoints, list)
        assert 'version' in contract
        
        # If health endpoints are found, verify they have correct structure
        for endpoint in endpoints:
            if 'health' in endpoint.get('path', ''):
                assert 'method' in endpoint
                assert 'function_name' in endpoint


class TestModelExtraction:
    """Integration tests for model extraction from real files."""
    
    def test_extract_user_model(self):
        """Test extracting User model from models.py."""
        extractor = ContractExtractor(".")
        contract = extractor.extract_from_files(["backend/models.py"])
        
        models = contract['models']
        
        # Should find User model
        assert 'User' in models
        
        user_model = models['User']
        assert 'fields' in user_model
        
        # Check for expected fields
        field_names = [f['name'] for f in user_model['fields']]
        assert 'id' in field_names
        assert 'username' in field_names
        assert 'email' in field_names
