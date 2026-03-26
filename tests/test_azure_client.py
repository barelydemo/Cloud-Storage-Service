"""
Unit tests for AzureStorageClient with mocked Azure SDK.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from io import BytesIO
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError, HttpResponseError
from app.azure_client import (
    AzureStorageClient,
    AzureConnectionError,
    AzureServiceError,
    BlobNotFoundError
)


@pytest.fixture
def azure_client():
    """Create an AzureStorageClient instance with mocked Azure SDK."""
    with patch('app.azure_client.BlobServiceClient') as mock_client_class:
        mock_service_client = MagicMock()
        mock_container_client = MagicMock()
        
        mock_client_class.from_connection_string.return_value = mock_service_client
        mock_service_client.get_container_client.return_value = mock_container_client
        
        connection_string = "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net"
        container_name = "test-container"
        
        client = AzureStorageClient(connection_string, container_name, timeout=30)
        
        # Store mocks on the client for test access
        client._mock_service_client = mock_service_client
        client._mock_container_client = mock_container_client
        
        yield client


@pytest.mark.asyncio
async def test_upload_blob_success(azure_client):
    """Test successful blob upload with mocked Azure SDK.
    
    Validates: Requirements 1.2 - Stream file directly to Azure Blob Storage
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.upload_blob = AsyncMock()
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Test data
    filename = "test.txt"
    file_data = BytesIO(b"test content")
    
    # Execute
    await azure_client.upload_blob(filename, file_data)
    
    # Verify
    azure_client._mock_container_client.get_blob_client.assert_called_once_with(filename)
    mock_blob_client.upload_blob.assert_called_once()
    call_args = mock_blob_client.upload_blob.call_args
    assert call_args[0][0] == file_data  # First positional arg is file_data
    assert call_args[1]['overwrite'] is True
    assert call_args[1]['timeout'] == 30


@pytest.mark.asyncio
async def test_upload_blob_connection_timeout(azure_client):
    """Test upload_blob raises AzureConnectionError on timeout.
    
    Validates: Requirements 5.1 - Map ServiceRequestError to AzureConnectionError
    """
    # Setup mock to raise ServiceRequestError
    mock_blob_client = MagicMock()
    mock_blob_client.upload_blob = AsyncMock(
        side_effect=ServiceRequestError("Connection timeout")
    )
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Test data
    filename = "test.txt"
    file_data = BytesIO(b"test content")
    
    # Execute and verify
    with pytest.raises(AzureConnectionError) as exc_info:
        await azure_client.upload_blob(filename, file_data)
    
    assert "Azure Connection Timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_blob_service_error(azure_client):
    """Test upload_blob raises AzureServiceError on Azure service errors.
    
    Validates: Requirements 5.2 - Map HttpResponseError to AzureServiceError
    """
    # Setup mock to raise HttpResponseError
    mock_blob_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_blob_client.upload_blob = AsyncMock(
        side_effect=HttpResponseError(message="Service unavailable", response=mock_response)
    )
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Test data
    filename = "test.txt"
    file_data = BytesIO(b"test content")
    
    # Execute and verify
    with pytest.raises(AzureServiceError) as exc_info:
        await azure_client.upload_blob(filename, file_data)
    
    assert "Azure service error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_blob_generic_exception(azure_client):
    """Test upload_blob raises AzureServiceError on unexpected exceptions.
    
    Validates: Requirements 5.2 - Handle unexpected errors gracefully
    """
    # Setup mock to raise generic exception
    mock_blob_client = MagicMock()
    mock_blob_client.upload_blob = AsyncMock(
        side_effect=Exception("Unexpected error")
    )
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Test data
    filename = "test.txt"
    file_data = BytesIO(b"test content")
    
    # Execute and verify
    with pytest.raises(AzureServiceError) as exc_info:
        await azure_client.upload_blob(filename, file_data)
    
    assert "Unexpected Azure error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_sas_url_success(azure_client):
    """Test successful SAS URL generation returns valid URL format.
    
    Validates: Requirements 3.2 - Generate SAS URL with read permissions
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://testaccount.blob.core.windows.net/test-container/test.txt"
    mock_blob_client.exists = AsyncMock(return_value=True)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Mock generate_blob_sas
    with patch('app.azure_client.generate_blob_sas') as mock_generate_sas:
        mock_generate_sas.return_value = "sv=2021-08-06&sr=b&sig=test_signature"
        
        # Execute
        filename = "test.txt"
        sas_url = await azure_client.generate_sas_url(filename, expiry_minutes=10)
        
        # Verify URL format
        assert sas_url.startswith("https://")
        assert "testaccount.blob.core.windows.net" in sas_url
        assert "test-container" in sas_url
        assert "test.txt" in sas_url
        assert "?" in sas_url  # SAS token separator
        assert "sv=" in sas_url  # SAS version parameter
        
        # Verify generate_blob_sas was called with correct parameters
        mock_generate_sas.assert_called_once()
        call_kwargs = mock_generate_sas.call_args[1]
        assert call_kwargs['account_name'] == 'testaccount'
        assert call_kwargs['container_name'] == 'test-container'
        assert call_kwargs['blob_name'] == filename
        assert call_kwargs['account_key'] == 'dGVzdGtleQ=='
        assert call_kwargs['permission'].read is True
        
        # Verify expiry is approximately 10 minutes from now
        expiry = call_kwargs['expiry']
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(minutes=10)
        # Allow 5 second tolerance for test execution time
        assert abs((expiry - expected_expiry).total_seconds()) < 5


@pytest.mark.asyncio
async def test_generate_sas_url_blob_not_found(azure_client):
    """Test generate_sas_url raises BlobNotFoundError when blob doesn't exist.
    
    Validates: Requirements 5.1 - Map ResourceNotFoundError to BlobNotFoundError
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(return_value=False)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Execute and verify
    filename = "nonexistent.txt"
    with pytest.raises(BlobNotFoundError) as exc_info:
        await azure_client.generate_sas_url(filename)
    
    assert "Blob not found" in str(exc_info.value)
    assert filename in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_sas_url_resource_not_found_exception(azure_client):
    """Test generate_sas_url handles ResourceNotFoundError from Azure SDK.
    
    Validates: Requirements 5.1 - Map ResourceNotFoundError to BlobNotFoundError
    """
    # Setup mock to raise ResourceNotFoundError
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(side_effect=ResourceNotFoundError("Blob not found"))
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Execute and verify
    filename = "test.txt"
    with pytest.raises(BlobNotFoundError):
        await azure_client.generate_sas_url(filename)


@pytest.mark.asyncio
async def test_generate_sas_url_service_error(azure_client):
    """Test generate_sas_url raises AzureServiceError on Azure service errors.
    
    Validates: Requirements 5.2 - Map HttpResponseError to AzureServiceError
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(return_value=True)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Mock generate_blob_sas to raise HttpResponseError
    with patch('app.azure_client.generate_blob_sas') as mock_generate_sas:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_generate_sas.side_effect = HttpResponseError(
            message="Service error",
            response=mock_response
        )
        
        # Execute and verify
        filename = "test.txt"
        with pytest.raises(AzureServiceError) as exc_info:
            await azure_client.generate_sas_url(filename)
        
        assert "Azure service error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_sas_url_custom_expiry(azure_client):
    """Test generate_sas_url respects custom expiry_minutes parameter.
    
    Validates: Requirements 3.2 - SAS URL expiry configuration
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://testaccount.blob.core.windows.net/test-container/test.txt"
    mock_blob_client.exists = AsyncMock(return_value=True)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Mock generate_blob_sas
    with patch('app.azure_client.generate_blob_sas') as mock_generate_sas:
        mock_generate_sas.return_value = "sv=2021-08-06&sr=b&sig=test_signature"
        
        # Execute with custom expiry
        filename = "test.txt"
        custom_expiry = 30
        await azure_client.generate_sas_url(filename, expiry_minutes=custom_expiry)
        
        # Verify expiry is approximately 30 minutes from now
        call_kwargs = mock_generate_sas.call_args[1]
        expiry = call_kwargs['expiry']
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(minutes=custom_expiry)
        # Allow 5 second tolerance for test execution time
        assert abs((expiry - expected_expiry).total_seconds()) < 5


@pytest.mark.asyncio
async def test_blob_exists_returns_true_when_blob_exists(azure_client):
    """Test blob_exists returns True when blob exists in Azure.
    
    Validates: Requirements 3.2 - Verify blob existence before operations
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(return_value=True)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Execute
    filename = "existing.txt"
    result = await azure_client.blob_exists(filename)
    
    # Verify
    assert result is True
    azure_client._mock_container_client.get_blob_client.assert_called_once_with(filename)
    mock_blob_client.exists.assert_called_once()


@pytest.mark.asyncio
async def test_blob_exists_returns_false_when_blob_not_exists(azure_client):
    """Test blob_exists returns False when blob doesn't exist in Azure.
    
    Validates: Requirements 3.2 - Verify blob existence before operations
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(return_value=False)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Execute
    filename = "nonexistent.txt"
    result = await azure_client.blob_exists(filename)
    
    # Verify
    assert result is False


@pytest.mark.asyncio
async def test_blob_exists_returns_false_on_exception(azure_client):
    """Test blob_exists returns False when Azure SDK raises exception.
    
    Validates: Requirements 5.2 - Graceful error handling for existence checks
    """
    # Setup mock to raise exception
    mock_blob_client = MagicMock()
    mock_blob_client.exists = AsyncMock(side_effect=Exception("Network error"))
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Execute
    filename = "test.txt"
    result = await azure_client.blob_exists(filename)
    
    # Verify - should return False instead of raising exception
    assert result is False


@pytest.mark.asyncio
async def test_azure_client_initialization():
    """Test AzureStorageClient initializes with correct parameters.
    
    Validates: Requirements 1.2 - Azure client initialization with configuration
    """
    with patch('app.azure_client.BlobServiceClient'):
        connection_string = "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey"
        container_name = "my-container"
        timeout = 60
        
        client = AzureStorageClient(connection_string, container_name, timeout)
        
        assert client.connection_string == connection_string
        assert client.container_name == container_name
        assert client.timeout == timeout


@pytest.mark.asyncio
async def test_azure_client_default_timeout():
    """Test AzureStorageClient uses default timeout when not specified.
    
    Validates: Requirements 5.1 - Default timeout configuration
    """
    with patch('app.azure_client.BlobServiceClient'):
        connection_string = "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey"
        container_name = "my-container"
        
        client = AzureStorageClient(connection_string, container_name)
        
        assert client.timeout == 30  # Default timeout


@pytest.mark.asyncio
async def test_upload_blob_with_different_file_types(azure_client):
    """Test upload_blob handles different file-like objects.
    
    Validates: Requirements 1.2 - Stream various file types to Azure
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.upload_blob = AsyncMock()
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Test with BytesIO
    file_data = BytesIO(b"binary content")
    await azure_client.upload_blob("test.bin", file_data)
    assert mock_blob_client.upload_blob.call_count == 1
    
    # Test with different BytesIO
    file_data2 = BytesIO(b"another file")
    await azure_client.upload_blob("test2.txt", file_data2)
    assert mock_blob_client.upload_blob.call_count == 2


@pytest.mark.asyncio
async def test_generate_sas_url_read_only_permissions(azure_client):
    """Test generate_sas_url creates SAS token with read-only permissions.
    
    Validates: Requirements 3.5 - SAS URL should grant read-only access
    """
    # Setup mock
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://testaccount.blob.core.windows.net/test-container/test.txt"
    mock_blob_client.exists = AsyncMock(return_value=True)
    azure_client._mock_container_client.get_blob_client.return_value = mock_blob_client
    
    # Mock generate_blob_sas
    with patch('app.azure_client.generate_blob_sas') as mock_generate_sas:
        mock_generate_sas.return_value = "sv=2021-08-06&sr=b&sig=test_signature"
        
        # Execute
        await azure_client.generate_sas_url("test.txt")
        
        # Verify permissions
        call_kwargs = mock_generate_sas.call_args[1]
        permissions = call_kwargs['permission']
        
        # Should have read permission
        assert permissions.read is True
        
        # Should NOT have write, delete, or other permissions
        assert not hasattr(permissions, 'write') or not permissions.write
        assert not hasattr(permissions, 'delete') or not permissions.delete
        assert not hasattr(permissions, 'add') or not permissions.add
        assert not hasattr(permissions, 'create') or not permissions.create
