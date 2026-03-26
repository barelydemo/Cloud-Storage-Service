"""
Unit tests for Pydantic API response models.
"""

from datetime import datetime
import pytest
from app.models import UploadResponse, DownloadResponse, ErrorResponse, FileMetadata


def test_upload_response_creation():
    """Test UploadResponse model can be created with valid data."""
    timestamp = datetime.now()
    response = UploadResponse(
        filename="test.txt",
        size=1024,
        upload_timestamp=timestamp
    )
    
    assert response.filename == "test.txt"
    assert response.size == 1024
    assert response.upload_timestamp == timestamp


def test_upload_response_json_serialization():
    """Test UploadResponse serializes to JSON correctly."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    response = UploadResponse(
        filename="document.pdf",
        size=1048576,
        upload_timestamp=timestamp
    )
    
    json_data = response.model_dump()
    assert json_data["filename"] == "document.pdf"
    assert json_data["size"] == 1048576
    assert json_data["upload_timestamp"] == timestamp


def test_download_response_creation():
    """Test DownloadResponse model can be created with valid data."""
    response = DownloadResponse(
        filename="test.txt",
        sas_url="https://account.blob.core.windows.net/container/test.txt?sas_token"
    )
    
    assert response.filename == "test.txt"
    assert "sas_token" in response.sas_url


def test_download_response_json_serialization():
    """Test DownloadResponse serializes to JSON correctly."""
    response = DownloadResponse(
        filename="document.pdf",
        sas_url="https://storage.blob.core.windows.net/files/document.pdf?sv=2021-06-08"
    )
    
    json_data = response.model_dump()
    assert json_data["filename"] == "document.pdf"
    assert json_data["sas_url"].startswith("https://")


def test_error_response_creation():
    """Test ErrorResponse model can be created with valid data."""
    response = ErrorResponse(error="File too large")
    
    assert response.error == "File too large"


def test_error_response_json_serialization():
    """Test ErrorResponse serializes to JSON correctly."""
    response = ErrorResponse(error="Blob Not Found")
    
    json_data = response.model_dump()
    assert json_data["error"] == "Blob Not Found"


def test_upload_response_validation():
    """Test UploadResponse validates required fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        UploadResponse(filename="test.txt")  # Missing size and upload_timestamp


def test_download_response_validation():
    """Test DownloadResponse validates required fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        DownloadResponse(filename="test.txt")  # Missing sas_url


def test_error_response_validation():
    """Test ErrorResponse validates required fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        ErrorResponse()  # Missing error field


def test_file_metadata_creation():
    """Test FileMetadata dataclass can be created with valid data."""
    timestamp = datetime.now()
    metadata = FileMetadata(
        filename="test.txt",
        size=2048,
        upload_timestamp=timestamp
    )
    
    assert metadata.filename == "test.txt"
    assert metadata.size == 2048
    assert metadata.upload_timestamp == timestamp


def test_file_metadata_equality():
    """Test FileMetadata dataclass equality comparison."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    metadata1 = FileMetadata(
        filename="document.pdf",
        size=1048576,
        upload_timestamp=timestamp
    )
    metadata2 = FileMetadata(
        filename="document.pdf",
        size=1048576,
        upload_timestamp=timestamp
    )
    
    assert metadata1 == metadata2


def test_file_metadata_fields():
    """Test FileMetadata dataclass has correct field types."""
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    metadata = FileMetadata(
        filename="data.json",
        size=512,
        upload_timestamp=timestamp
    )
    
    assert isinstance(metadata.filename, str)
    assert isinstance(metadata.size, int)
    assert isinstance(metadata.upload_timestamp, datetime)
