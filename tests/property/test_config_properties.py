"""
Property-based tests for BridgeConfig.

**Feature: bridge, Property 15: Configuration initialization**
**Feature: bridge, Property 16: Dependency persistence**
**Feature: bridge, Property 17: Configuration validation**
**Feature: bridge, Property 19: Dependency removal cleanup**
"""
import pytest
from hypothesis import given, strategies as st, settings
from pathlib import Path
import json
import tempfile
import shutil
from backend.bridge_models import BridgeConfig, Dependency


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def valid_role_strategy(draw):
    """Generate valid role values."""
    return draw(st.sampled_from(['consumer', 'provider', 'both']))


@st.composite
def repo_id_strategy(draw):
    """Generate valid repository IDs."""
    return draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    )))


@st.composite
def dependency_strategy(draw):
    """Generate valid Dependency objects."""
    name = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    )))
    
    return Dependency(
        name=name,
        type=draw(st.sampled_from(['http-api', 'graphql', 'grpc'])),
        sync_method=draw(st.sampled_from(['git', 'http', 's3'])),
        git_url=f"https://github.com/org/{name}.git",
        contract_path=".kiro/contracts/provided-api.yaml",
        local_cache=f".kiro/contracts/{name}-api.yaml",
        sync_on_commit=draw(st.booleans())
    )


# ============================================================================
# Property 15: Configuration initialization
# ============================================================================

@given(role=valid_role_strategy())
@settings(max_examples=100)
def test_property_15_config_initialization(role):
    """
    **Feature: bridge, Property 15: Configuration initialization**
    **Validates: Requirements 5.1**
    
    For any init operation, the system should create a valid bridge.json file 
    at `.kiro/settings/bridge.json` with required fields.
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        
        # Create default configuration
        config = BridgeConfig.create_default(role=role, config_path=str(config_path))
        config.save()
        
        # Verify file was created
        assert config_path.exists(), "Configuration file should be created"
        
        # Verify file contains valid JSON
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        # Verify required fields are present
        assert 'bridge' in data, "Configuration should have 'bridge' key"
        bridge_data = data['bridge']
        
        assert 'enabled' in bridge_data, "Configuration should have 'enabled' field"
        assert 'role' in bridge_data, "Configuration should have 'role' field"
        assert 'repo_id' in bridge_data, "Configuration should have 'repo_id' field"
        assert 'provides' in bridge_data, "Configuration should have 'provides' field"
        assert 'dependencies' in bridge_data, "Configuration should have 'dependencies' field"
        
        # Verify role is correct
        assert bridge_data['role'] == role, f"Role should be {role}"
        
        # Verify role-specific configuration
        if role in ['provider', 'both']:
            assert 'contract_file' in bridge_data['provides'], \
                "Provider config should have contract_file"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================================
# Property 16: Dependency persistence
# ============================================================================

@given(
    role=valid_role_strategy(),
    dependency=dependency_strategy()
)
@settings(max_examples=100)
def test_property_16_dependency_persistence(role, dependency):
    """
    **Feature: bridge, Property 16: Dependency persistence**
    **Validates: Requirements 5.2**
    
    For any add-dependency operation with valid parameters, the configuration 
    should be updated to include the new dependency with all provided details 
    (name, git_url, contract_path).
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        
        # Create configuration
        config = BridgeConfig.create_default(role=role, config_path=str(config_path))
        
        # Add dependency
        config.add_dependency(dependency.name, dependency)
        
        # Load configuration from file
        loaded_config = BridgeConfig(config_path=str(config_path))
        loaded_config.load()
        
        # Verify dependency was persisted
        assert dependency.name in loaded_config.dependencies, \
            f"Dependency {dependency.name} should be in configuration"
        
        loaded_dep = loaded_config.dependencies[dependency.name]
        
        # Verify all details were persisted
        assert loaded_dep.name == dependency.name, "Name should match"
        assert loaded_dep.git_url == dependency.git_url, "Git URL should match"
        assert loaded_dep.contract_path == dependency.contract_path, "Contract path should match"
        assert loaded_dep.local_cache == dependency.local_cache, "Local cache should match"
        assert loaded_dep.type == dependency.type, "Type should match"
        assert loaded_dep.sync_method == dependency.sync_method, "Sync method should match"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================================
# Property 17: Configuration validation
# ============================================================================

@given(
    role=st.text(min_size=1, max_size=20),
    has_required_fields=st.booleans()
)
@settings(max_examples=100)
def test_property_17_config_validation(role, has_required_fields):
    """
    **Feature: bridge, Property 17: Configuration validation**
    **Validates: Requirements 5.3**
    
    For any configuration save operation, if required fields are missing, 
    the operation should fail with a descriptive error.
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        
        if has_required_fields and role in ['consumer', 'provider', 'both']:
            # Valid configuration
            config = BridgeConfig(
                enabled=True,
                role=role,
                repo_id="test-repo",
                config_path=str(config_path)
            )
            
            errors = config.validate()
            assert len(errors) == 0, "Valid configuration should have no errors"
        else:
            # Invalid configuration (invalid role or missing fields)
            config = BridgeConfig(
                enabled=True,
                role=role,
                repo_id="",
                config_path=str(config_path)
            )
            
            errors = config.validate()
            
            if role not in ['consumer', 'provider', 'both']:
                # Should have error about invalid role
                assert any('Invalid role' in error for error in errors), \
                    f"Should have error about invalid role: {role}"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)


@given(dependency=dependency_strategy())
@settings(max_examples=100)
def test_property_17_dependency_validation(dependency):
    """
    **Feature: bridge, Property 17: Configuration validation**
    **Validates: Requirements 5.3**
    
    Test that dependencies with missing required fields are detected.
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        config = BridgeConfig(role='consumer', config_path=str(config_path))
        
        # Add valid dependency
        config.add_dependency(dependency.name, dependency)
        
        # Validate - should have no errors
        errors = config.validate()
        assert len(errors) == 0, f"Valid dependency should have no errors: {errors}"
        
        # Create invalid dependency (missing git_url for git sync)
        if dependency.sync_method == 'git':
            invalid_dep = Dependency(
                name="invalid",
                type=dependency.type,
                sync_method='git',
                git_url=None,  # Missing required field
                contract_path=dependency.contract_path,
                local_cache=".kiro/contracts/invalid-api.yaml"
            )
            
            config.add_dependency("invalid", invalid_dep)
            errors = config.validate()
            
            # Should have error about missing git_url
            assert any('git_url is required' in error for error in errors), \
                "Should have error about missing git_url for git sync method"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================================
# Property 19: Dependency removal cleanup
# ============================================================================

@given(dependency=dependency_strategy())
@settings(max_examples=100)
def test_property_19_dependency_removal_cleanup(dependency):
    """
    **Feature: bridge, Property 19: Dependency removal cleanup**
    **Validates: Requirements 5.5**
    
    For any remove-dependency operation, the cached contract file for that 
    dependency should be deleted if it exists.
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        cache_file = tmp_dir / f"{dependency.name}-api.yaml"
        
        # Update dependency to use tmp_path for cache
        dependency.local_cache = str(cache_file)
        
        # Create configuration and add dependency
        config = BridgeConfig(role='consumer', config_path=str(config_path))
        config.add_dependency(dependency.name, dependency)
        
        # Create cached contract file
        cache_file.write_text("version: 1.0\nrepo_id: test")
        assert cache_file.exists(), "Cache file should exist before removal"
        
        # Remove dependency
        config.remove_dependency(dependency.name)
        
        # Verify dependency removed from config
        assert dependency.name not in config.dependencies, \
            "Dependency should be removed from configuration"
        
        # Verify cached file was deleted
        assert not cache_file.exists(), \
            "Cached contract file should be deleted when dependency is removed"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)


@given(dependency=dependency_strategy())
@settings(max_examples=100)
def test_property_19_removal_without_cache_file(dependency):
    """
    **Feature: bridge, Property 19: Dependency removal cleanup**
    **Validates: Requirements 5.5**
    
    Test that removing a dependency works even if the cache file doesn't exist.
    """
    # Create temporary directory
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        config_path = tmp_dir / "bridge.json"
        cache_file = tmp_dir / f"{dependency.name}-api.yaml"
        
        # Update dependency to use tmp_path for cache
        dependency.local_cache = str(cache_file)
        
        # Create configuration and add dependency
        config = BridgeConfig(role='consumer', config_path=str(config_path))
        config.add_dependency(dependency.name, dependency)
        
        # Don't create cache file - it doesn't exist
        assert not cache_file.exists(), "Cache file should not exist"
        
        # Remove dependency - should not raise error
        config.remove_dependency(dependency.name)
        
        # Verify dependency removed from config
        assert dependency.name not in config.dependencies, \
            "Dependency should be removed from configuration"
    finally:
        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
