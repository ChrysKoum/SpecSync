"""
Integration tests for bridge components.
Tests that contract extraction, models, and serialization work together.
"""
import pytest
from pathlib import Path
from backend.bridge_contract_extractor import ContractExtractor
from backend.bridge_models import Contract, BridgeConfig, Dependency


class TestBridgeIntegration:
    """Integration tests for bridge components."""
    
    def test_extract_and_save_contract(self, tmp_path):
        """Test extracting contract and saving with Contract model."""
        # Create a sample FastAPI file
        sample_code = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    id: int
    name: str

@app.get("/users")
def get_users():
    """Get all users."""
    return []

@app.get("/users/{id}")
def get_user(id: int):
    """Get a user by ID."""
    return {}
'''
        
        # Write sample file
        code_file = tmp_path / "api.py"
        code_file.write_text(sample_code)
        
        # Extract contract
        extractor = ContractExtractor(str(tmp_path))
        contract_dict = extractor.extract_from_files(["*.py"])
        
        # Verify extraction
        assert contract_dict['version'] == '1.0'
        assert len(contract_dict['endpoints']) == 2
        assert 'User' in contract_dict['models']
        
        # Convert to Contract model
        contract = Contract.from_dict(contract_dict)
        
        # Save using Contract model
        output_path = tmp_path / "contract.yaml"
        contract.save_to_yaml(str(output_path))
        
        assert output_path.exists()
        
        # Load and verify
        loaded_contract = Contract.load_from_yaml(str(output_path))
        assert len(loaded_contract.endpoints) == 2
        assert loaded_contract.repo_id == tmp_path.name
    
    def test_config_with_contract_workflow(self, tmp_path):
        """Test complete workflow: config -> sync -> contract."""
        # Create config
        config_path = tmp_path / "bridge.json"
        config = BridgeConfig(
            role="consumer",
            repo_id="test-repo",
            config_path=str(config_path)
        )
        
        # Add dependency
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="https://github.com/org/backend.git",
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=str(tmp_path / "backend-api.yaml")
        )
        
        config.add_dependency("backend", dep)
        
        # Verify config saved
        assert config_path.exists()
        
        # Load config
        loaded_config = BridgeConfig(config_path=str(config_path))
        loaded_config.load()
        
        # Verify dependency
        assert "backend" in loaded_config.dependencies
        backend_dep = loaded_config.get_dependency("backend")
        assert backend_dep.git_url == "https://github.com/org/backend.git"
        
        # Simulate contract for this dependency
        contract = Contract(
            version="1.0",
            repo_id="backend",
            role="provider",
            last_updated="2024-11-27T10:00:00Z"
        )
        
        # Save to dependency's local cache
        contract.save_to_yaml(backend_dep.local_cache)
        
        # Verify contract saved
        assert Path(backend_dep.local_cache).exists()
        
        # Load and verify
        cached_contract = Contract.load_from_yaml(backend_dep.local_cache)
        assert cached_contract.repo_id == "backend"
    
    def test_config_validation_workflow(self, tmp_path):
        """Test config validation catches errors."""
        config = BridgeConfig(role="consumer")
        
        # Add invalid dependency (missing git_url for git sync)
        dep = Dependency(
            name="backend",
            type="http-api",
            sync_method="git",
            git_url="",  # Missing!
            contract_path=".kiro/contracts/provided-api.yaml",
            local_cache=".kiro/contracts/backend-api.yaml"
        )
        
        config.dependencies["backend"] = dep
        
        # Validate should catch the error
        errors = config.validate()
        assert len(errors) > 0
        assert any("git_url" in error for error in errors)
