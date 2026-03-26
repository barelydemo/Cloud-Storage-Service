"""
Unit tests for API endpoints.
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO
from datetime import datetime

from app.models import FileMetadata

# Set environment variables before importing app
os.environ['AZURE_STORAGE_CONNECTION_STRING'] = 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net'
os.environ['AZURE_CONTAINER_NAME'] = 'test-container'


@pytest.fixture
def test_client():
    """Create test client with mocked dependencies."""
    with patch('app.main.AzureStorageClient') as mock_azure_class, \
         patch('app.main.MetadataStore') as mock_metadata_class:
        
        # Create mock instances
        mock_azure = MagicMock()
        mock_metadata = MagicMock()
        
        mock_azure_class.return_value = mock_azure
        mock_metadata_class.return_value = mock_metadata
        
        # Mock initialize
        mock_metadata.initialize = AsyncMock()
        
        # Import app after mocking
        from app.main import app
        import app.main as main_module
        from config.settings import Settings
        
        # Initialize settings in the module
        main_module.settings = Settings()
        main_module.azure_client = mock_azure
        main_module.metadata_store = mock_metadata
        
        # Create test client
        client = TestClient(app)
        
        yield client, mock_azure, mock_metadata


def test_upload_file_success(test_client):
    """Test successful file upload returns HTTP 201 with metadata."""
    client, mock_azure, mock_metadata = test_client
    
    # Setup mocks
    mock_azure.upload_blob = AsyncMock()
    mock_metadata.record_upload = AsyncMock()
    
    # Create test file
    filename = "test.txt"
    file_data = b"test content"
    files = {"file": (filename, BytesIO(file_data), "text/plain")}
    
    # Send upload request
    response = client.post("/upload", files=files)
    
    # Verify response
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == filename
    assert data["size"] == len(file_data)
    assert "upload_timestamp" in data


def test_upload_file_too_large(test_client):
    """Test file exceeding limit returns HTTP 413."""
    client, mock_azure, mock_metadata = test_client
    
    # Create file larger than 100MB limit
    filename = "large.bin"
    file_data = b"x" * (101 * 1024 * 1024)
    files = {"file": (filename, BytesIO(file_data), "application/octet-stream")}
    
    # Send upload request
    response = client.post("/upload", files=files)
    
    # Verify response
    assert response.status_code == 413
    data = response.json()
    assert data["detail"] == "File too large"


def test_download_file_success(test_client):
    """Test successful download returns HTTP 200 with SAS URL."""
    client, mock_azure, mock_metadata = test_client
    
    # Setup mocks
    filename = "test.txt"
    mock_metadata.get_metadata = AsyncMock(return_value=FileMetadata(
        filename=filename,
        size=1024,
        upload_timestamp=datetime.utcnow()
    ))
    mock_azure.blob_exists = AsyncMock(return_value=True)
    mock_azure.generate_sas_url = AsyncMock(
        return_value=f"https://test.blob.core.windows.net/container/{filename}?sas=token"
    )
    
    # Send download request
    response = client.get(f"/download/{filename}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == filename
    assert "sas_url" in data
    assert data["sas_url"].startswith("https://")


def test_download_file_not_found(test_client):
    """Test download of non-existent file returns HTTP 404."""
    client, mock_azure, mock_metadata = test_client
    
    # Setup mocks - file doesn't exist
    mock_metadata.get_metadata = AsyncMock(return_value=None)
    
    # Send download request
    response = client.get("/download/nonexistent.txt")
    
    # Verify response
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Blob Not Found"


def test_health_check():
    """Test health check endpoint."""
    # Set environment variables
    os.environ['AZURE_STORAGE_CONNECTION_STRING'] = 'test'
    os.environ['AZURE_CONTAINER_NAME'] = 'test'
    
    with patch('app.main.AzureStorageClient'), \
         patch('app.main.MetadataStore') as mock_metadata_class:
        
        mock_metadata = MagicMock()
        mock_metadata_class.return_value = mock_metadata
        mock_metadata.initialize = AsyncMock()
        
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
