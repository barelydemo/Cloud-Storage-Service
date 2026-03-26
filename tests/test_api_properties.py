"""
Property-based tests for API endpoints using Hypothesis.

Feature: cloud-storage-service
"""

import pytest
import os
from hypothesis import given, settings, strategies as st
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

# Set environment variables before any imports
os.environ['AZURE_STORAGE_CONNECTION_STRING'] = 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net'
os.environ['AZURE_CONTAINER_NAME'] = 'test-container'

# Import after mocking to avoid initialization issues
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Strategy for generating valid filenames
filename_strategy = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        blacklist_categories=('Cc', 'Cs'),
        blacklist_characters='/\\:*?"<>|'
    )
).filter(lambda x: x.strip())


# Strategy for generating file data (1 byte to 50MB for upload tests)
file_data_strategy = st.binary(min_size=1, max_size=50*1024*1024)


def setup_test_app():
    """Helper function to set up test app with mocked dependencies."""
    from app.main import app
    import app.main as main_module
    from config.settings import Settings
    
    # Initialize settings
    main_module.settings = Settings()
    
    # Create mock instances
    mock_azure = MagicMock()
    mock_metadata = MagicMock()
    
    # Setup async mocks
    mock_azure.upload_blob = AsyncMock()
    mock_azure.blob_exists = AsyncMock(return_value=True)
    mock_azure.generate_sas_url = AsyncMock(return_value="https://test.blob.core.windows.net/container/test?sas=token")
    mock_metadata.record_upload = AsyncMock()
    mock_metadata.get_metadata = AsyncMock(return_value=None)
    
    # Set mocks in module
    main_module.azure_client = mock_azure
    main_module.metadata_store = mock_metadata
    
    return app, mock_azure, mock_metadata


@settings(max_examples=100)
@given(
    filename=filename_strategy,
    file_data=file_data_strategy
)
def test_property_1_upload_endpoint_accepts_multipart_form_data(filename, file_data):
    """
    Feature: cloud-storage-service, Property 1: Upload Endpoint Accepts Multipart Form Data
    
    **Validates: Requirements 1.1**
    
    For any valid file data submitted as multipart/form-data to the upload endpoint, 
    the service should accept and process the request without rejecting based on content type.
    """
    app, mock_azure, mock_metadata = setup_test_app()
    client = TestClient(app)
    
    # Create multipart form data
    files = {"file": (filename, BytesIO(file_data), "application/octet-stream")}
    
    # Send upload request
    response = client.post("/upload", files=files)
    
    # Verify the request was accepted (not rejected based on content type)
    # Should return either 201 (success) or 413 (file too large), but not 415 (unsupported media type)
    assert response.status_code in [201, 413], \
        f"Upload endpoint should accept multipart/form-data, got status {response.status_code}"
    
    # If successful, verify response is JSON
    if response.status_code == 201:
        assert response.headers.get("content-type") == "application/json", \
            "Response should be JSON"
        data = response.json()
        assert "filename" in data, "Response should contain filename"
        assert "size" in data, "Response should contain size"
        assert "upload_timestamp" in data, "Response should contain upload_timestamp"


@settings(max_examples=100)
@given(
    filename=filename_strategy,
    file_size_mb=st.integers(min_value=101, max_value=200)
)
def test_property_4_file_size_limit_enforcement(filename, file_size_mb):
    """
    Feature: cloud-storage-service, Property 4: File Size Limit Enforcement
    
    **Validates: Requirements 2.2**
    
    For any file exceeding the configured maximum file size, the upload request 
    should be rejected with HTTP 413 and error message "File too large".
    """
    app, mock_azure, mock_metadata = setup_test_app()
    client = TestClient(app)
    
    # Create file larger than limit
    file_size_bytes = file_size_mb * 1024 * 1024
    file_data = b"x" * file_size_bytes
    files = {"file": (filename, BytesIO(file_data), "application/octet-stream")}
    
    # Send upload request
    response = client.post("/upload", files=files)
    
    # Verify rejection with HTTP 413
    assert response.status_code == 413, \
        f"Files exceeding max size should return HTTP 413, got {response.status_code}"
    
    # Verify error message
    assert response.headers.get("content-type") == "application/json", \
        "Error response should be JSON"
    data = response.json()
    assert "detail" in data, "Error response should contain detail field"
    assert data["detail"] == "File too large", \
        f"Error message should be 'File too large', got '{data['detail']}'"
    
    # Verify upload was not attempted
    mock_azure.upload_blob.assert_not_called()



@settings(max_examples=100)
@given(
    filename=filename_strategy
)
def test_property_5_download_endpoint_accepts_filename_parameter(filename):
    """
    Feature: cloud-storage-service, Property 5: Download Endpoint Accepts Filename Parameter
    
    **Validates: Requirements 3.1**
    
    For any filename provided as a path parameter to the download endpoint, the service 
    should process the request and return either a success response with SAS URL or an 
    appropriate error response.
    """
    app, mock_azure, mock_metadata = setup_test_app()
    
    # Setup mocks - file exists
    from app.models import FileMetadata
    from datetime import datetime
    
    mock_metadata.get_metadata = AsyncMock(return_value=FileMetadata(
        filename=filename,
        size=1024,
        upload_timestamp=datetime.utcnow()
    ))
    mock_azure.blob_exists = AsyncMock(return_value=True)
    mock_azure.generate_sas_url = AsyncMock(return_value=f"https://test.blob.core.windows.net/container/{filename}?sas=token")
    
    client = TestClient(app)
    
    # Send download request
    response = client.get(f"/download/{filename}")
    
    # Verify the request was processed (should return 200 or appropriate error)
    assert response.status_code in [200, 404, 502], \
        f"Download endpoint should process filename parameter, got status {response.status_code}"
    
    # Verify response is JSON
    assert response.headers.get("content-type") == "application/json", \
        "Response should be JSON"
    
    # If successful, verify response structure
    if response.status_code == 200:
        data = response.json()
        assert "filename" in data, "Success response should contain filename"
        assert "sas_url" in data, "Success response should contain sas_url"
    else:
        # Error response should have detail field
        data = response.json()
        assert "detail" in data, "Error response should contain detail field"


@settings(max_examples=100)
@given(
    filename=filename_strategy
)
def test_property_8_no_server_side_file_streaming(filename):
    """
    Feature: cloud-storage-service, Property 8: No Server-Side File Streaming
    
    **Validates: Requirements 3.4**
    
    For any download request, the response should contain only a URL reference (SAS URL) 
    and not the actual file content, ensuring the client downloads directly from Azure.
    """
    app, mock_azure, mock_metadata = setup_test_app()
    
    # Setup mocks - file exists
    from app.models import FileMetadata
    from datetime import datetime
    
    mock_metadata.get_metadata = AsyncMock(return_value=FileMetadata(
        filename=filename,
        size=1024,
        upload_timestamp=datetime.utcnow()
    ))
    mock_azure.blob_exists = AsyncMock(return_value=True)
    mock_azure.generate_sas_url = AsyncMock(return_value=f"https://test.blob.core.windows.net/container/{filename}?sas=token")
    
    client = TestClient(app)
    
    # Send download request
    response = client.get(f"/download/{filename}")
    
    # Verify successful response
    assert response.status_code == 200, \
        f"Download should succeed for existing file, got {response.status_code}"
    
    # Verify response is JSON (not binary file content)
    assert response.headers.get("content-type") == "application/json", \
        "Response must be JSON, not file content"
    
    # Verify response contains URL, not file data
    data = response.json()
    assert "sas_url" in data, "Response must contain SAS URL"
    assert isinstance(data["sas_url"], str), "SAS URL must be a string"
    assert data["sas_url"].startswith("https://"), "SAS URL must be a valid HTTPS URL"
    
    # Verify response does not contain binary file content
    # (JSON response proves no streaming)
    assert "content" not in data, "Response should not contain file content"
    assert "data" not in data, "Response should not contain file data"


@settings(max_examples=100)
@given(
    filename=filename_strategy
)
def test_property_11_non_existent_file_returns_404(filename):
    """
    Feature: cloud-storage-service, Property 11: Non-Existent File Returns 404
    
    **Validates: Requirements 6.1**
    
    For any filename that does not exist in the metadata store, a download request 
    should return HTTP 404 with error message "Blob Not Found".
    """
    app, mock_azure, mock_metadata = setup_test_app()
    
    # Setup mocks - file does not exist
    mock_metadata.get_metadata = AsyncMock(return_value=None)
    mock_azure.blob_exists = AsyncMock(return_value=False)
    
    client = TestClient(app)
    
    # Send download request for non-existent file
    response = client.get(f"/download/{filename}")
    
    # Verify HTTP 404 response
    assert response.status_code == 404, \
        f"Non-existent file should return HTTP 404, got {response.status_code}"
    
    # Verify error message
    assert response.headers.get("content-type") == "application/json", \
        "Error response should be JSON"
    data = response.json()
    assert "detail" in data, "Error response should contain detail field"
    assert data["detail"] == "Blob Not Found", \
        f"Error message should be 'Blob Not Found', got '{data['detail']}'"



@settings(max_examples=50)
@given(
    filename=filename_strategy,
    file_data=st.binary(min_size=1, max_size=1024*1024)  # Smaller files for faster tests
)
def test_property_13_success_responses_in_json_format(filename, file_data):
    """
    Feature: cloud-storage-service, Property 13: Success Responses in JSON Format
    
    **Validates: Requirements 10.1**
    
    For any successful API request (upload or download), the response should be 
    valid JSON with appropriate content-type header.
    """
    app, mock_azure, mock_metadata = setup_test_app()
    
    # Setup mocks
    from app.models import FileMetadata
    from datetime import datetime
    
    mock_metadata.get_metadata = AsyncMock(return_value=FileMetadata(
        filename=filename,
        size=len(file_data),
        upload_timestamp=datetime.utcnow()
    ))
    mock_azure.blob_exists = AsyncMock(return_value=True)
    mock_azure.generate_sas_url = AsyncMock(return_value=f"https://test.blob.core.windows.net/container/{filename}?sas=token")
    
    client = TestClient(app)
    
    # Test upload endpoint
    files = {"file": (filename, BytesIO(file_data), "application/octet-stream")}
    upload_response = client.post("/upload", files=files)
    
    if upload_response.status_code == 201:
        # Verify JSON response
        assert upload_response.headers.get("content-type") == "application/json", \
            "Upload success response must be JSON"
        upload_data = upload_response.json()
        assert isinstance(upload_data, dict), "Response must be a JSON object"
        
    # Test download endpoint
    download_response = client.get(f"/download/{filename}")
    
    if download_response.status_code == 200:
        # Verify JSON response
        assert download_response.headers.get("content-type") == "application/json", \
            "Download success response must be JSON"
        download_data = download_response.json()
        assert isinstance(download_data, dict), "Response must be a JSON object"


@settings(max_examples=50)
@given(
    filename=filename_strategy
)
def test_property_14_error_responses_in_json_format_with_error_field(filename):
    """
    Feature: cloud-storage-service, Property 14: Error Responses in JSON Format with Error Field
    
    **Validates: Requirements 10.2**
    
    For any failed API request, the response should be valid JSON containing an 
    "error" field (or "detail" field in FastAPI) with a descriptive error message.
    """
    app, mock_azure, mock_metadata = setup_test_app()
    
    # Setup mocks for error scenarios
    from app.azure_client import AzureServiceError
    
    # Scenario 1: File not found (404)
    mock_metadata.get_metadata = AsyncMock(return_value=None)
    
    client = TestClient(app)
    
    # Test download endpoint with non-existent file
    response = client.get(f"/download/{filename}")
    
    # Verify error response is JSON
    assert response.status_code == 404, "Should return 404 for non-existent file"
    assert response.headers.get("content-type") == "application/json", \
        "Error response must be JSON"
    
    # Verify error field exists
    data = response.json()
    assert isinstance(data, dict), "Error response must be a JSON object"
    assert "detail" in data, "Error response must contain 'detail' field (FastAPI standard)"
    assert isinstance(data["detail"], str), "Error detail must be a string"
    assert len(data["detail"]) > 0, "Error detail must not be empty"
    
    # Scenario 2: File too large (413)
    large_file_data = b"x" * (101 * 1024 * 1024)  # 101 MB
    files = {"file": (filename, BytesIO(large_file_data), "application/octet-stream")}
    
    response = client.post("/upload", files=files)
    
    if response.status_code == 413:
        # Verify error response is JSON
        assert response.headers.get("content-type") == "application/json", \
            "Error response must be JSON"
        data = response.json()
        assert "detail" in data, "Error response must contain 'detail' field"
        assert isinstance(data["detail"], str), "Error detail must be a string"
