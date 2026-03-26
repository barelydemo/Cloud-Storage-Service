"""
Property-based tests for API response models using Hypothesis.

Feature: cloud-storage-service
"""

from datetime import datetime, timezone
import pytest
from hypothesis import given, settings, strategies as st
from app.models import UploadResponse, DownloadResponse


# Strategy for generating valid filenames
# Exclude control characters and path separators
filename_strategy = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        blacklist_categories=('Cc', 'Cs'),  # Control and surrogate characters
        blacklist_characters='/\\:*?"<>|'  # Path separators and invalid chars
    )
).filter(lambda x: x.strip())  # Ensure not just whitespace


# Strategy for generating file sizes (1 byte to 1GB)
file_size_strategy = st.integers(min_value=1, max_value=1024*1024*1024)


# Strategy for generating timestamps
# Note: datetimes() requires naive datetimes for min/max values
timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
)


# Strategy for generating SAS URLs
# Azure Blob Storage URL format with SAS token
sas_url_strategy = st.builds(
    lambda account, container, filename, token: (
        f"https://{account}.blob.core.windows.net/{container}/{filename}?{token}"
    ),
    account=st.text(min_size=3, max_size=24, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))),
    container=st.text(min_size=3, max_size=63, alphabet=st.characters(whitelist_categories=('Ll', 'Nd'))),
    filename=filename_strategy,
    token=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P')))
)


@settings(max_examples=100)
@given(
    filename=filename_strategy,
    size=file_size_strategy,
    upload_timestamp=timestamp_strategy
)
def test_property_2_successful_upload_response_structure(filename, size, upload_timestamp):
    """
    Feature: cloud-storage-service, Property 2: Successful Upload Response Structure
    
    **Validates: Requirements 1.3, 10.3**
    
    For any file successfully uploaded, the HTTP 201 response should contain a JSON object 
    with fields for filename (matching the uploaded file), size (in bytes), and 
    upload_timestamp (ISO 8601 format).
    """
    # Create UploadResponse with randomized inputs
    response = UploadResponse(
        filename=filename,
        size=size,
        upload_timestamp=upload_timestamp
    )
    
    # Verify the response has all required fields
    assert hasattr(response, 'filename'), "UploadResponse must have 'filename' field"
    assert hasattr(response, 'size'), "UploadResponse must have 'size' field"
    assert hasattr(response, 'upload_timestamp'), "UploadResponse must have 'upload_timestamp' field"
    
    # Verify field values match input
    assert response.filename == filename, "Filename must match the uploaded file"
    assert response.size == size, "Size must be in bytes"
    assert response.upload_timestamp == upload_timestamp, "Upload timestamp must be preserved"
    
    # Verify JSON serialization works
    json_data = response.model_dump()
    assert 'filename' in json_data, "JSON must contain 'filename' field"
    assert 'size' in json_data, "JSON must contain 'size' field"
    assert 'upload_timestamp' in json_data, "JSON must contain 'upload_timestamp' field"
    
    # Verify JSON values match
    assert json_data['filename'] == filename
    assert json_data['size'] == size
    assert json_data['upload_timestamp'] == upload_timestamp
    
    # Verify size is a positive integer
    assert isinstance(response.size, int), "Size must be an integer"
    assert response.size > 0, "Size must be positive"
    
    # Verify timestamp is a datetime object
    assert isinstance(response.upload_timestamp, datetime), "Upload timestamp must be a datetime object"


@settings(max_examples=100)
@given(
    filename=filename_strategy,
    sas_url=sas_url_strategy
)
def test_property_7_successful_download_response_structure(filename, sas_url):
    """
    Feature: cloud-storage-service, Property 7: Successful Download Response Structure
    
    **Validates: Requirements 3.3, 10.4**
    
    For any successful download request, the HTTP 200 response should contain a JSON object 
    with fields for filename and sas_url (a valid Azure Blob Storage URL with SAS token).
    """
    # Create DownloadResponse with randomized inputs
    response = DownloadResponse(
        filename=filename,
        sas_url=sas_url
    )
    
    # Verify the response has all required fields
    assert hasattr(response, 'filename'), "DownloadResponse must have 'filename' field"
    assert hasattr(response, 'sas_url'), "DownloadResponse must have 'sas_url' field"
    
    # Verify field values match input
    assert response.filename == filename, "Filename must match the requested file"
    assert response.sas_url == sas_url, "SAS URL must be preserved"
    
    # Verify JSON serialization works
    json_data = response.model_dump()
    assert 'filename' in json_data, "JSON must contain 'filename' field"
    assert 'sas_url' in json_data, "JSON must contain 'sas_url' field"
    
    # Verify JSON values match
    assert json_data['filename'] == filename
    assert json_data['sas_url'] == sas_url
    
    # Verify SAS URL is a valid Azure Blob Storage URL format
    assert isinstance(response.sas_url, str), "SAS URL must be a string"
    assert response.sas_url.startswith('https://'), "SAS URL must use HTTPS protocol"
    assert '.blob.core.windows.net/' in response.sas_url, "SAS URL must be an Azure Blob Storage URL"
    assert '?' in response.sas_url, "SAS URL must contain a query string (SAS token)"
