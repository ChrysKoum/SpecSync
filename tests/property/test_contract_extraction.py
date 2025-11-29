"""
Property-based tests for contract extraction.

**Feature: bridge, Property 1: Endpoint extraction completeness**
*For any* Python file containing FastAPI endpoints, extracting the contract 
should produce entries for all decorated endpoint functions with their complete 
metadata (path, method, parameters, response type).
**Validates: Requirements 1.1, 1.3**

**Feature: bridge, Property 2: Multi-file aggregation**
*For any* set of Python files containing endpoints, extracting from all files 
should produce a single contract containing all endpoints from all files.
**Validates: Requirements 1.5**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from pathlib import Path
import tempfile
import shutil
from backend.bridge_contract_extractor import ContractExtractor


# ============================================================================
# Hypothesis Strategies
# ============================================================================

@st.composite
def fastapi_endpoint_code(draw):
    """Generate random valid FastAPI endpoint code."""
    # Python keywords to avoid
    python_keywords = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
        'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
        'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
        'while', 'with', 'yield'
    }
    
    methods = ['get', 'post', 'put', 'delete', 'patch']
    method = draw(st.sampled_from(methods))
    
    # Generate path
    path_segments = draw(st.lists(
        st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=8),
        min_size=1,
        max_size=3
    ))
    path = '/' + '/'.join(path_segments)
    
    # Generate function name (avoid Python keywords)
    func_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz_',
        min_size=3,
        max_size=20
    ).filter(lambda x: x[0] != '_' and not x.startswith('__') and x not in python_keywords))
    
    # Generate parameters
    param_count = draw(st.integers(min_value=0, max_value=3))
    params = []
    param_defs = []
    for i in range(param_count):
        param_name = f"param{i}"
        param_type = draw(st.sampled_from(['int', 'str', 'bool']))
        params.append(f"{param_name}: {param_type}")
        param_defs.append((param_name, param_type))
    
    params_str = ', '.join(params) if params else ''
    
    # Generate return type
    return_type = draw(st.sampled_from(['dict', 'str', 'int', 'User', 'List[User]']))
    
    code = f"""
@app.{method}("{path}")
def {func_name}({params_str}) -> {return_type}:
    pass
"""
    
    return {
        'code': code,
        'method': method.upper(),
        'path': path,
        'function_name': func_name,
        'parameters': param_defs,
        'return_type': return_type
    }


@st.composite
def multiple_endpoints_code(draw):
    """Generate code with multiple FastAPI endpoints."""
    num_endpoints = draw(st.integers(min_value=1, max_value=5))
    endpoints = []
    seen_keys = set()
    
    for i in range(num_endpoints):
        endpoint = draw(fastapi_endpoint_code())
        
        # Ensure unique (method, path) combination
        key = (endpoint['method'], endpoint['path'])
        attempts = 0
        while key in seen_keys and attempts < 10:
            endpoint = draw(fastapi_endpoint_code())
            key = (endpoint['method'], endpoint['path'])
            attempts += 1
        
        if key not in seen_keys:
            endpoints.append(endpoint)
            seen_keys.add(key)
    
    # Combine all endpoint codes
    combined_code = '\n'.join([ep['code'] for ep in endpoints])
    
    return {
        'code': combined_code,
        'endpoints': endpoints
    }


# ============================================================================
# Property Tests
# ============================================================================

class TestEndpointExtraction:
    """
    Property-based tests for endpoint extraction completeness.
    
    **Feature: bridge, Property 1: Endpoint extraction completeness**
    """
    
    @given(endpoint_data=fastapi_endpoint_code())
    @settings(max_examples=100)
    def test_endpoint_extraction_completeness(self, endpoint_data):
        """
        Property: For any Python file containing FastAPI endpoints, extracting 
        the contract should produce entries for all decorated endpoint functions 
        with their complete metadata.
        
        **Feature: bridge, Property 1: Endpoint extraction completeness**
        **Validates: Requirements 1.1, 1.3**
        """
        # Arrange - Create temp directory and file
        tmp_dir = tempfile.mkdtemp()
        try:
            test_file = Path(tmp_dir) / "test_api.py"
            test_file.write_text(endpoint_data['code'])
            
            extractor = ContractExtractor(tmp_dir)
            
            # Act
            contract = extractor.extract_from_files(["*.py"])
            
            # Assert - Should have exactly one endpoint
            assert len(contract['endpoints']) == 1, \
                "Should extract exactly one endpoint from single endpoint code"
            
            endpoint = contract['endpoints'][0]
            
            # Assert - Complete metadata should be present
            assert 'path' in endpoint, "Endpoint should have path"
            assert 'method' in endpoint, "Endpoint should have method"
            assert 'function_name' in endpoint, "Endpoint should have function_name"
            assert 'source_file' in endpoint, "Endpoint should have source_file"
            assert 'parameters' in endpoint, "Endpoint should have parameters"
            assert 'response' in endpoint, "Endpoint should have response"
            assert 'status' in endpoint, "Endpoint should have status"
            assert 'implemented_at' in endpoint, "Endpoint should have implemented_at"
            
            # Assert - Metadata should match expected values
            assert endpoint['path'] == endpoint_data['path'], \
                f"Path should be {endpoint_data['path']}"
            assert endpoint['method'] == endpoint_data['method'], \
                f"Method should be {endpoint_data['method']}"
            assert endpoint['function_name'] == endpoint_data['function_name'], \
                f"Function name should be {endpoint_data['function_name']}"
            
            # Assert - Parameters should match
            assert len(endpoint['parameters']) == len(endpoint_data['parameters']), \
                "Should extract all parameters"
            
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(endpoints_data=multiple_endpoints_code())
    @settings(max_examples=100)
    def test_multiple_endpoints_extraction(self, endpoints_data):
        """
        Property: For any Python file with multiple endpoints, all endpoints 
        should be extracted.
        
        **Feature: bridge, Property 1: Endpoint extraction completeness**
        **Validates: Requirements 1.1, 1.3**
        """
        # Arrange - Create temp directory and file
        tmp_dir = tempfile.mkdtemp()
        try:
            test_file = Path(tmp_dir) / "test_api.py"
            test_file.write_text(endpoints_data['code'])
            
            extractor = ContractExtractor(tmp_dir)
            
            # Act
            contract = extractor.extract_from_files(["*.py"])
            
            # Assert - Should extract all endpoints
            expected_count = len(endpoints_data['endpoints'])
            actual_count = len(contract['endpoints'])
            
            assert actual_count == expected_count, \
                f"Should extract all {expected_count} endpoints, got {actual_count}"
            
            # Assert - All paths should be present
            extracted_paths = {ep['path'] for ep in contract['endpoints']}
            expected_paths = {ep['path'] for ep in endpoints_data['endpoints']}
            
            assert extracted_paths == expected_paths, \
                "All endpoint paths should be extracted"
            
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestMultiFileAggregation:
    """
    Property-based tests for multi-file aggregation.
    
    **Feature: bridge, Property 2: Multi-file aggregation**
    """
    
    @given(
        file1_data=fastapi_endpoint_code(),
        file2_data=fastapi_endpoint_code()
    )
    @settings(max_examples=100)
    def test_multi_file_aggregation(self, file1_data, file2_data):
        """
        Property: For any set of Python files containing endpoints, extracting 
        from all files should produce a single contract containing all endpoints 
        from all files.
        
        **Feature: bridge, Property 2: Multi-file aggregation**
        **Validates: Requirements 1.5**
        """
        # Assume endpoints are different (different paths or methods)
        assume(file1_data['path'] != file2_data['path'] or 
               file1_data['method'] != file2_data['method'])
        
        # Arrange - Create temp directory and multiple files
        tmp_dir = tempfile.mkdtemp()
        try:
            file1 = Path(tmp_dir) / "api1.py"
            file1.write_text(file1_data['code'])
            
            file2 = Path(tmp_dir) / "api2.py"
            file2.write_text(file2_data['code'])
            
            extractor = ContractExtractor(tmp_dir)
            
            # Act
            contract = extractor.extract_from_files(["*.py"])
            
            # Assert - Should have endpoints from both files
            assert len(contract['endpoints']) == 2, \
                "Should aggregate endpoints from both files"
            
            # Assert - Both paths should be present
            extracted_paths = {ep['path'] for ep in contract['endpoints']}
            assert file1_data['path'] in extracted_paths, \
                "Should include endpoint from first file"
            assert file2_data['path'] in extracted_paths, \
                "Should include endpoint from second file"
            
            # Assert - Contract should be a single unified structure
            assert 'version' in contract, "Contract should have version"
            assert 'endpoints' in contract, "Contract should have endpoints list"
            assert isinstance(contract['endpoints'], list), \
                "Endpoints should be in a single list"
            
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(
        endpoint1=fastapi_endpoint_code(),
        endpoint2=fastapi_endpoint_code()
    )
    @settings(max_examples=100)
    def test_duplicate_endpoint_handling(self, endpoint1, endpoint2):
        """
        Property: When the same endpoint (method + path) appears in multiple 
        files, only the first occurrence should be included (alphabetically first file).
        
        **Feature: bridge, Property 2: Multi-file aggregation**
        **Validates: Requirements 1.5**
        """
        # Force same path and method but different function names
        endpoint2_modified = endpoint2.copy()
        endpoint2_modified['path'] = endpoint1['path']
        endpoint2_modified['method'] = endpoint1['method']
        endpoint2_modified['function_name'] = endpoint1['function_name'] + '_v2'
        
        # Recreate code with modified values
        method_lower = endpoint2_modified['method'].lower()
        params_str = ', '.join([f"{p[0]}: {p[1]}" for p in endpoint2_modified['parameters']])
        endpoint2_modified['code'] = f"""
@app.{method_lower}("{endpoint2_modified['path']}")
def {endpoint2_modified['function_name']}({params_str}) -> {endpoint2_modified['return_type']}:
    pass
"""
        
        # Arrange - Create temp directory and multiple files with duplicate endpoint
        # Use filenames that ensure api1.py is processed first (alphabetically)
        tmp_dir = tempfile.mkdtemp()
        try:
            file1 = Path(tmp_dir) / "a_api1.py"
            file1.write_text(endpoint1['code'])
            
            file2 = Path(tmp_dir) / "b_api2.py"
            file2.write_text(endpoint2_modified['code'])
            
            extractor = ContractExtractor(tmp_dir)
            
            # Act
            contract = extractor.extract_from_files(["*.py"])
            
            # Assert - Should only have one endpoint (first occurrence)
            endpoints_with_path = [
                ep for ep in contract['endpoints']
                if ep['path'] == endpoint1['path'] and ep['method'] == endpoint1['method']
            ]
            
            assert len(endpoints_with_path) == 1, \
                "Duplicate endpoints should be deduplicated"
            
            # Assert - First occurrence (from a_api1.py) should win
            assert endpoints_with_path[0]['function_name'] == endpoint1['function_name'], \
                "First occurrence (alphabetically first file) should be kept"
            
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
    
    @given(
        num_files=st.integers(min_value=2, max_value=5),
        endpoints_per_file=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=50)
    def test_large_scale_aggregation(self, num_files, endpoints_per_file):
        """
        Property: For any number of files with any number of endpoints each, 
        all unique endpoints should be aggregated into a single contract.
        
        **Feature: bridge, Property 2: Multi-file aggregation**
        **Validates: Requirements 1.5**
        """
        # Arrange - Create temp directory and multiple files
        tmp_dir = tempfile.mkdtemp()
        try:
            total_endpoints = 0
            
            for file_idx in range(num_files):
                code_parts = []
                for ep_idx in range(endpoints_per_file):
                    # Create unique endpoint
                    path = f"/api/file{file_idx}/endpoint{ep_idx}"
                    method = ['get', 'post', 'put'][ep_idx % 3]
                    func_name = f"func_f{file_idx}_e{ep_idx}"
                    
                    code = f"""
@app.{method}("{path}")
def {func_name}():
    pass
"""
                    code_parts.append(code)
                    total_endpoints += 1
                
                file_path = Path(tmp_dir) / f"api{file_idx}.py"
                file_path.write_text('\n'.join(code_parts))
            
            extractor = ContractExtractor(tmp_dir)
            
            # Act
            contract = extractor.extract_from_files(["*.py"])
            
            # Assert - Should have all endpoints
            assert len(contract['endpoints']) == total_endpoints, \
                f"Should aggregate all {total_endpoints} endpoints"
            
            # Assert - All endpoints should have required metadata
            for endpoint in contract['endpoints']:
                assert 'path' in endpoint
                assert 'method' in endpoint
                assert 'function_name' in endpoint
                assert 'source_file' in endpoint
            
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
