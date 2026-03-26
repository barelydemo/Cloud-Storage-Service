"""
Pydantic models for API request and response validation.
"""

from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Response model for successful file upload.
    
    Attributes:
        filename: Name of the uploaded file
        size: File size in bytes
        upload_timestamp: ISO 8601 formatted timestamp of upload completion
    """
    filename: str
    size: int
    upload_timestamp: datetime


class DownloadResponse(BaseModel):
    """Response model for successful file download request.
    
    Attributes:
        filename: Name of the requested file
        sas_url: Time-limited Shared Access Signature URL for direct blob access
    """
    filename: str
    sas_url: str


class ErrorResponse(BaseModel):
    """Response model for error conditions.
    
    Attributes:
        error: Descriptive error message
    """
    error: str


@dataclass
class FileMetadata:
    """Dataclass representing file metadata stored in the metadata store.
    
    Attributes:
        filename: Name of the file
        size: File size in bytes
        upload_timestamp: Timestamp when the file was uploaded
    """
    filename: str
    size: int
    upload_timestamp: datetime
