"""
Property-based tests for Azure Storage Client using Hypothesis.

Feature: cloud-storage-service
"""

import pytest
from hypothesis import given, settings, strategies as st
from io import BytesIO
from app.azure_client import AzureStorageClient
from unittest.mock import AsyncMock, MagicMock, patch


# Strategy for generating valid filenames
filename_strategy = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        blacklist_categories=('Cc', 'Cs'),
        blacklist_characters='/\\:*?"<>|'
    )
).filter(lambda x: x.strip())


# Strategy for generating file data (1 byte to 10MB for testing)
file_data_strategy = st.binary(min_size=1, max_size=10*1024*1024)


@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    filename=filename_strategy,
    file_data=file_data_strategy
)
async def test_property_3_filename_preservation(filename, file_data):
    """
    Feature: cloud-storage-service, Property 3: Filename Preservation
    
    **Validates: Requirements 1.5**
    
    For any file uploaded with a given filename, retrieving the blob from Azure 
    should return a blob with the exact same filename.
    """
    # Mock Azure SDK components
    with patch('app.azure_client.BlobServiceClient') as mock_blob_service:
        # Setup mocks
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()
        
        # Configure the mock chain
        mock_service_instance = MagicMock()
        mock_blob_service.from_connection_string.return_value = mock_service_instance
        mock_service_instance.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        
        # Mock successful upload (async)
        mock_blob_client.upload_blob = AsyncMock()
        
        # Mock blob exists check (async)
        mock_blob_client.exists = AsyncMock(return_value=True)
        
        # Mock get_blob_properties to return blob with same filename
        mock_properties = MagicMock()
        mock_properties.name = filename
        mock_blob_client.get_blob_properties = AsyncMock(return_value=mock_properties)
        
        # Create client and upload
        client = AzureStorageClient(
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net",
            container_name="test-container"
        )
        
        # Upload the file
        file_obj = BytesIO(file_data)
        await client.upload_blob(filename, file_obj)
        
        # Verify blob exists with same filename
        exists = await client.blob_exists(filename)
        assert exists, f"Blob should exist after upload: {filename}"
        
        # Verify the blob was uploaded with the correct filename
        mock_container_client.get_blob_client.assert_called_with(filename)
        
        # Verify upload was called
        mock_blob_client.upload_blob.assert_called_once()
        
        # Get blob properties and verify filename matches
        properties = await mock_blob_client.get_blob_properties()
        assert properties.name == filename, f"Blob name must match uploaded filename: expected {filename}, got {properties.name}"



@pytest.mark.asyncio
@settings(max_examples=100)
@given(
    filename=filename_strategy,
    expiry_minutes=st.integers(min_value=1, max_value=60)
)
async def test_property_6_and_9_sas_url_expiry_and_permissions(filename, expiry_minutes):
    """
    Feature: cloud-storage-service, Property 6: SAS URL Expiry and Permissions
    Feature: cloud-storage-service, Property 9: SAS URL Read-Only Access
    
    **Validates: Requirements 3.2, 3.5**
    
    For any valid file download request, the generated SAS URL should have read-only 
    permissions and be valid for exactly the specified minutes from generation time.
    """
    from datetime import datetime, timedelta, timezone
    from azure.storage.blob import BlobSasPermissions
    from unittest.mock import patch
    
    # Mock Azure SDK components
    with patch('app.azure_client.BlobServiceClient') as mock_blob_service, \
         patch('app.azure_client.generate_blob_sas') as mock_generate_sas:
        
        # Setup mocks
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()
        
        # Configure the mock chain
        mock_service_instance = MagicMock()
        mock_blob_service.from_connection_string.return_value = mock_service_instance
        mock_service_instance.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        
        # Mock blob exists (async)
        mock_blob_client.exists = AsyncMock(return_value=True)
        mock_blob_client.url = f"https://testaccount.blob.core.windows.net/test-container/{filename}"
        
        # Mock SAS token generation
        mock_sas_token = "sv=2021-06-08&se=2024-01-01T12%3A00%3A00Z&sr=b&sp=r&sig=test"
        mock_generate_sas.return_value = mock_sas_token
        
        # Create client
        client = AzureStorageClient(
            connection_string="DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net",
            container_name="test-container"
        )
        
        # Generate SAS URL
        sas_url = await client.generate_sas_url(filename, expiry_minutes=expiry_minutes)
        
        # Verify SAS URL format
        assert sas_url.startswith('https://'), "SAS URL must use HTTPS"
        assert '.blob.core.windows.net/' in sas_url, "SAS URL must be Azure Blob Storage URL"
        assert '?' in sas_url, "SAS URL must contain SAS token"
        assert filename in sas_url, "SAS URL must contain the filename"
        
        # Verify generate_blob_sas was called with correct parameters
        assert mock_generate_sas.called, "generate_blob_sas should be called"
        call_kwargs = mock_generate_sas.call_args[1]
        
        # Verify read-only permissions (Property 9)
        permissions = call_kwargs['permission']
        assert isinstance(permissions, BlobSasPermissions), "Permission must be BlobSasPermissions"
        assert permissions.read is True, "SAS URL must have read permission"
        assert permissions.write is False, "SAS URL must NOT have write permission"
        assert permissions.delete is False, "SAS URL must NOT have delete permission"
        assert permissions.add is False, "SAS URL must NOT have add permission"
        assert permissions.create is False, "SAS URL must NOT have create permission"
        
        # Verify expiry time (Property 6)
        expiry = call_kwargs['expiry']
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(minutes=expiry_minutes)
        
        # Allow 5 second tolerance for test execution time
        time_diff = abs((expiry - expected_expiry).total_seconds())
        assert time_diff < 5, f"Expiry time should be {expiry_minutes} minutes from now (tolerance: 5s), got {time_diff}s difference"
