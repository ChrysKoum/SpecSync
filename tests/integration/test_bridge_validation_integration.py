"""
Integration tests for bridge validation in SpecSync workflow.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import json

from backend.validator import ValidationOrchestrator
from backend.bridge_models import BridgeConfig, Dependency, Contract, Endpoint


class TestBridgeValidationIntegration:
    """Test bridge validation integration with SpecSync."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create directory structure
        (temp_dir / ".kiro/settings").mkdir(parents=True, exist_ok=True)
        (temp_dir / ".kiro/contracts").mkdir(parents=True, exist_ok=True)
        (temp_dir / ".kiro/steering").mkdir(parents=True, exist_ok=True)
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)
        
        # Create minimal steering rules file
        steering_rules = temp_dir / ".kiro/steering/rules.md"
        steering_rules.write_text("""# Steering Rules

## File Correlation Patterns

### Code to Spec Mapping
- `src/*.py` maps to `.kiro/specs/app.yaml`

## Minimal Change Policy
Suggest only necessary modifications.
""", encoding='utf-8')
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_bridge_validation_not_configured(self, temp_repo):
        """Test validation when bridge is not configured."""
        # Change to temp directory
        import os
        original_dir = os.getcwd()
        os.chdir(temp_repo)
        
        try:
            orchestrator = ValidationOrchestrator()
            
            git_context = {
                'branch': 'main',
                'stagedFiles': ['src/api.py'],
                'diff': ''
            }
            
            result = orchestrator.validate(git_context)
            
            # Bridge report should indicate not configured
            assert 'bridge_report' in result
            assert result['bridge_report']['enabled'] == False
            assert result['bridge_report']['has_issues'] == False
            
        finally:
            os.chdir(original_dir)
    
    def test_bridge_validation_with_no_drift(self, temp_repo):
        """Test validation when API calls align with contracts."""
        import os
        original_dir = os.getcwd()
        os.chdir(temp_repo)
        
        try:
            # Create bridge configuration
            config = BridgeConfig.create_default(
                role="consumer",
                config_path=str(temp_repo / ".kiro/settings/bridge.json")
            )
            
            dep = Dependency(
                name="backend",
                type="http-api",
                sync_method="git",
                git_url="https://github.com/test/backend.git",
                contract_path=".kiro/contracts/provided-api.yaml",
                local_cache=".kiro/contracts/backend-api.yaml",
                sync_on_commit=True
            )
            config.add_dependency("backend", dep)
            
            # Create a contract with matching endpoint
            contract = Contract(
                version="1.0",
                repo_id="backend",
                role="provider",
                last_updated="2024-11-27T10:00:00Z",
                endpoints=[
                    Endpoint(
                        id="get-users",
                        path="/users",
                        method="GET",
                        status="implemented",
                        source_file="backend/handlers/user.py",
                        function_name="get_users"
                    )
                ]
            )
            contract.save_to_yaml(str(temp_repo / ".kiro/contracts/backend-api.yaml"))
            
            # Create source file with matching API call
            api_file = temp_repo / "src/api.py"
            api_file.write_text("""
import requests

def fetch_users():
    response = requests.get("/users")
    return response.json()
""")
            
            orchestrator = ValidationOrchestrator()
            
            git_context = {
                'branch': 'main',
                'stagedFiles': ['src/api.py'],
                'diff': ''
            }
            
            result = orchestrator.validate(git_context)
            
            # Bridge validation should pass
            assert 'bridge_report' in result
            assert result['bridge_report']['enabled'] == True
            assert result['bridge_report']['has_issues'] == False
            assert len(result['bridge_report']['dependencies_checked']) == 1
            
        finally:
            os.chdir(original_dir)
    
    def test_bridge_validation_with_drift(self, temp_repo):
        """Test validation when API calls don't match contracts."""
        import os
        original_dir = os.getcwd()
        os.chdir(temp_repo)
        
        try:
            # Create bridge configuration
            config = BridgeConfig.create_default(
                role="consumer",
                config_path=str(temp_repo / ".kiro/settings/bridge.json")
            )
            
            dep = Dependency(
                name="backend",
                type="http-api",
                sync_method="git",
                git_url="https://github.com/test/backend.git",
                contract_path=".kiro/contracts/provided-api.yaml",
                local_cache=".kiro/contracts/backend-api.yaml",
                sync_on_commit=True
            )
            config.add_dependency("backend", dep)
            
            # Create a contract with different endpoint
            contract = Contract(
                version="1.0",
                repo_id="backend",
                role="provider",
                last_updated="2024-11-27T10:00:00Z",
                endpoints=[
                    Endpoint(
                        id="get-users",
                        path="/users",
                        method="GET",
                        status="implemented",
                        source_file="backend/handlers/user.py",
                        function_name="get_users"
                    )
                ]
            )
            contract.save_to_yaml(str(temp_repo / ".kiro/contracts/backend-api.yaml"))
            
            # Create source file with non-matching API call
            api_file = temp_repo / "src/api.py"
            api_file.write_text("""
import requests

def fetch_user_profile():
    # This endpoint doesn't exist in the contract
    response = requests.get("/users/profile")
    return response.json()
""")
            
            orchestrator = ValidationOrchestrator()
            
            git_context = {
                'branch': 'main',
                'stagedFiles': ['src/api.py'],
                'diff': ''
            }
            
            result = orchestrator.validate(git_context)
            
            # Bridge validation should detect drift
            assert 'bridge_report' in result
            assert result['bridge_report']['enabled'] == True
            assert result['bridge_report']['has_issues'] == True
            assert result['bridge_report']['total_issues'] > 0
            
            # Check that validation failed overall
            assert result['success'] == False
            assert result['has_bridge_issues'] == True
            
            # Check that suggestions include bridge issues
            if 'suggestions' in result and result['suggestions']:
                bridge_suggestions = [
                    s for s in result['suggestions'].get('ordered_suggestions', [])
                    if s.get('type') == 'bridge'
                ]
                assert len(bridge_suggestions) > 0
            
        finally:
            os.chdir(original_dir)
    
    def test_bridge_validation_timing(self, temp_repo):
        """Test that bridge validation includes timing information."""
        import os
        original_dir = os.getcwd()
        os.chdir(temp_repo)
        
        try:
            # Create minimal bridge configuration
            config = BridgeConfig.create_default(
                role="consumer",
                config_path=str(temp_repo / ".kiro/settings/bridge.json")
            )
            config.save()
            
            orchestrator = ValidationOrchestrator()
            
            git_context = {
                'branch': 'main',
                'stagedFiles': [],
                'diff': ''
            }
            
            result = orchestrator.validate(git_context)
            
            # Check timing data includes bridge validation
            assert 'timing' in result
            # Bridge validation should be present even if no files to validate
            # (it checks configuration)
            
        finally:
            os.chdir(original_dir)
    
    def test_bridge_validation_error_handling(self, temp_repo):
        """Test that bridge validation errors don't block commits."""
        import os
        original_dir = os.getcwd()
        os.chdir(temp_repo)
        
        try:
            # Create invalid bridge configuration
            config_file = temp_repo / ".kiro/settings/bridge.json"
            config_file.write_text("invalid json{")
            
            orchestrator = ValidationOrchestrator()
            
            git_context = {
                'branch': 'main',
                'stagedFiles': ['src/api.py'],
                'diff': ''
            }
            
            result = orchestrator.validate(git_context)
            
            # Validation should not crash
            assert 'bridge_report' in result
            # Bridge should report error but not block
            assert result['bridge_report']['enabled'] == True
            assert 'error' in result['bridge_report']
            
        finally:
            os.chdir(original_dir)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
