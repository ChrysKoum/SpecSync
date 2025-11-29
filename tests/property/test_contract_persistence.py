"""
Property-based tests for contract persistence.

**Feature: bridge, Property 3: Contract persistence**
*For any* extracted contract, saving it should create a file at the specified 
path containing all contract data and a valid ISO 8601 timestamp.
**Validates: Requirements 1.2, 1.4**
"""
import pytest
from hypothesis import given, strategies as st, settings
from pathlib import Path
import yaml
import re
import tempfile
import shutil
from datetime import datetime
from backend.bridge_models import Contract, Endpoint


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def endpoint_strategy(draw):
    """Generate random valid endpoint definitions."""
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    path_segments = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=10),
        min_size=1,
        max_size=4
    ))
    path = '/' + '/'.join(path_segments)
    method = draw(st.sampled_from(methods))
    
    return Endpoint(
        id=draw(st.text(min_size=1, max_size=50)),
        path=path,
        method=method,
        status=draw(st.sampled_from(['implemented', 'deprecated', 'planned'])),
        implemented_at=draw(st.one_of(st.none(), st.just(datetime.utcnow().isoformat() + 'Z'))),
        source_file=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        function_name=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        parameters=draw(st.lists(
            st.fixed_dictionaries({
                'name': st.text(min_size=1, max_size=20),
                'type': st.sampled_from(['string', 'integer', 'boolean', 'object']),
                'required': st.booleans()
            }),
            max_size=5
        )),
        response=draw(st.fixed_dictionaries({
            'status': st.integers(min_value=200, max_value=599),
            'type': st.sampled_from(['object', 'array', 'string', 'unknown'])
        })),
        consumers=draw(st.lists(st.text(min_size=1, max_size=20), max_size=5))
    )


@st.composite
def contract_strategy(draw):
    """Generate random valid contracts."""
    return Contract(
        version=draw(st.sampled_from(['1.0', '1.1', '2.0'])),
        repo_id=draw(st.text(min_size=1, max_size=50)),
        role=draw(st.sampled_from(['provider', 'consumer', 'both'])),
        last_updated=datetime.utcnow().isoformat() + 'Z',
        endpoints=draw(st.lists(endpoint_strategy(), min_size=0, max_size=10)),
        models=draw(st.dictionaries(
            keys=st.text(min_size=1, max_size=30),
            values=st.fixed_dictionaries({
                'fields': st.lists(
                    st.fixed_dictionaries({
                        'name': st.text(min_size=1, max_size=20),
                        'type': st.sampled_from(['string', 'integer', 'boolean', 'object'])
                    }),
                    max_size=10
                )
            }),
            max_size=5
        ))
    )


# ============================================================================
# Property Tests
# ============================================================================

class TestContractPersistence:
    """
    Property-based tests for contract persistence.
    
    **Feature: bridge, Property 3: Contract persistence**
    """
    
    @given(contract=contract_strategy())
    @settings(max_examples=100)
    def test_contract_persistence_creates_file(self, contract):
        """
        Property: For any extracted contract, saving it should create a file 
        at the specified path.
        
        **Feature: bridge, Property 3: Contract persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        # Arrange - Create temp directory
        tmp_dir = tempfile.mkdtemp()
        try:
            output_path = Path(tmp_dir) / "test_contract.yaml"
            
            # Act
            result_path = contract.save_to_yaml(str(output_path))
            
            # Assert - File should exist
            assert output_path.exists(), "Contract file should be created"
            assert result_path == output_path, "Returned path should match specified path"
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(contract=contract_strategy())
    @settings(max_examples=100)
    def test_contract_persistence_contains_all_data(self, contract):
        """
        Property: For any extracted contract, the saved file should contain 
        all contract data.
        
        **Feature: bridge, Property 3: Contract persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        # Arrange - Create temp directory
        tmp_dir = tempfile.mkdtemp()
        try:
            output_path = Path(tmp_dir) / "test_contract.yaml"
            
            # Act
            contract.save_to_yaml(str(output_path))
            
            # Load the saved file
            with open(output_path, 'r', encoding='utf-8') as f:
                saved_data = yaml.safe_load(f)
            
            # Assert - All required fields should be present
            assert 'version' in saved_data, "Contract should have version"
            assert 'repo_id' in saved_data, "Contract should have repo_id"
            assert 'role' in saved_data, "Contract should have role"
            assert 'last_updated' in saved_data, "Contract should have last_updated"
            assert 'endpoints' in saved_data, "Contract should have endpoints"
            assert 'models' in saved_data, "Contract should have models"
            
            # Assert - Data should match original
            assert saved_data['version'] == contract.version
            assert saved_data['repo_id'] == contract.repo_id
            assert saved_data['role'] == contract.role
            assert len(saved_data['endpoints']) == len(contract.endpoints)
            assert len(saved_data['models']) == len(contract.models)
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(contract=contract_strategy())
    @settings(max_examples=100)
    def test_contract_persistence_has_valid_iso8601_timestamp(self, contract):
        """
        Property: For any extracted contract, the saved file should contain 
        a valid ISO 8601 timestamp.
        
        **Feature: bridge, Property 3: Contract persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        # Arrange - Create temp directory
        tmp_dir = tempfile.mkdtemp()
        try:
            output_path = Path(tmp_dir) / "test_contract.yaml"
            
            # Act
            contract.save_to_yaml(str(output_path))
            
            # Load the saved file
            with open(output_path, 'r', encoding='utf-8') as f:
                saved_data = yaml.safe_load(f)
            
            # Assert - Timestamp should be valid ISO 8601 format
            timestamp = saved_data['last_updated']
            
            # ISO 8601 format: YYYY-MM-DDTHH:MM:SS.ffffffZ or YYYY-MM-DDTHH:MM:SSZ
            iso8601_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$'
            assert re.match(iso8601_pattern, timestamp), \
                f"Timestamp '{timestamp}' should be valid ISO 8601 format"
            
            # Should be parseable as datetime
            try:
                # Remove 'Z' and parse
                datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                pytest.fail(f"Timestamp '{timestamp}' should be parseable as datetime")
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(contract=contract_strategy())
    @settings(max_examples=100)
    def test_contract_persistence_round_trip(self, contract):
        """
        Property: For any contract, saving and loading should preserve all data.
        
        **Feature: bridge, Property 3: Contract persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        # Arrange - Create temp directory
        tmp_dir = tempfile.mkdtemp()
        try:
            output_path = Path(tmp_dir) / "test_contract.yaml"
            
            # Act
            contract.save_to_yaml(str(output_path))
            loaded_contract = Contract.load_from_yaml(str(output_path))
            
            # Assert - Core fields should match
            assert loaded_contract.version == contract.version
            assert loaded_contract.repo_id == contract.repo_id
            assert loaded_contract.role == contract.role
            assert loaded_contract.last_updated == contract.last_updated
            
            # Assert - Endpoints count should match
            assert len(loaded_contract.endpoints) == len(contract.endpoints)
            
            # Assert - Models count should match
            assert len(loaded_contract.models) == len(contract.models)
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(
        contract=contract_strategy(),
        subdir=st.text(alphabet=st.characters(whitelist_categories=('Ll', 'Nd')), min_size=1, max_size=20)
    )
    @settings(max_examples=100)
    def test_contract_persistence_creates_parent_directories(self, contract, subdir):
        """
        Property: For any contract and any nested path, saving should create 
        parent directories if they don't exist.
        
        **Feature: bridge, Property 3: Contract persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        # Arrange - Create temp directory
        tmp_dir = tempfile.mkdtemp()
        try:
            nested_path = Path(tmp_dir) / subdir / "nested" / "contract.yaml"
            
            # Act
            result_path = contract.save_to_yaml(str(nested_path))
            
            # Assert - File and parent directories should exist
            assert nested_path.exists(), "Contract file should be created"
            assert nested_path.parent.exists(), "Parent directories should be created"
            assert result_path == nested_path
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
