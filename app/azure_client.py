"""
Azure Blob Storage client for file operations.
"""

from typing import BinaryIO
from datetime import datetime, timedelta, timezone
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError, HttpResponseError
import logging

logger = logging.getLogger(__name__)


class AzureConnectionError(Exception):
    """Raised when Azure connection times out or fails."""
    pass


class AzureServiceError(Exception):
    """Raised when Azure service returns an error."""
    pass


class BlobNotFoundError(Exception):
    """Raised when requested blob does not exist."""
    pass


class AzureStorageClient:
    """Client for Azure Blob Storage operations.
    
    Handles blob uploads, SAS URL generation, and blob existence checks
    with comprehensive error handling and timeout configuration.
    
    Attributes:
        connection_string: Azure Storage connection string
        container_name: Name of the blob container
        timeout: Connection timeout in seconds
    """
    
    def __init__(self, connection_string: str, container_name: str, timeout: int = 30):
        """Initialize Azure Storage client.
        
        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the blob container to use
            timeout: Connection timeout in seconds (default: 30)
        """
        self.connection_string = connection_string
        self.container_name = container_name
        self.timeout = timeout
        
        # Initialize BlobServiceClient
        self.blob_service_client = BlobServiceClient.from_connection_string(
            connection_string,
            connection_timeout=timeout,
            read_timeout=timeout
        )
        self.container_client = self.blob_service_client.get_container_client(container_name)
    
    async def upload_blob(self, filename: str, file_data: BinaryIO) -> None:
        """Stream file data to Azure Blob Storage.
        
        Uploads file content as a blob without buffering entire file in memory.
        
        Args:
            filename: Name to store the blob under
            file_data: File-like object to stream
            
        Raises:
            AzureConnectionError: On timeout or connection failure
            AzureServiceError: On Azure service errors
        """
        try:
            blob_client = self.container_client.get_blob_client(filename)
            await blob_client.upload_blob(
                file_data,
                overwrite=True,
                timeout=self.timeout
            )
            logger.info(f"Successfully uploaded blob: {filename}")
            
        except ServiceRequestError as e:
            logger.error(f"Azure connection timeout for {filename}: {str(e)}")
            raise AzureConnectionError(f"Azure Connection Timeout: {str(e)}")
            
        except HttpResponseError as e:
            logger.error(f"Azure service error for {filename}: {str(e)}")
            raise AzureServiceError(f"Azure service error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error uploading {filename}: {str(e)}")
            raise AzureServiceError(f"Unexpected Azure error: {str(e)}")
    
    async def generate_sas_url(self, filename: str, expiry_minutes: int = 10) -> str:
        """Generate time-limited SAS URL for blob access.
        
        Creates a Shared Access Signature URL with read-only permissions
        valid for the specified duration.
        
        Args:
            filename: Name of the blob
            expiry_minutes: URL validity duration in minutes (default: 10)
            
        Returns:
            Complete SAS URL with read permissions
            
        Raises:
            BlobNotFoundError: If blob doesn't exist
            AzureServiceError: On Azure service errors
        """
        try:
            blob_client = self.container_client.get_blob_client(filename)
            
            # Check if blob exists
            if not await blob_client.exists():
                logger.warning(f"Blob not found: {filename}")
                raise BlobNotFoundError(f"Blob not found: {filename}")
            
            # Extract account name and key from connection string
            account_name = None
            account_key = None
            for part in self.connection_string.split(';'):
                if part.startswith('AccountName='):
                    account_name = part.split('=', 1)[1]
                elif part.startswith('AccountKey='):
                    account_key = part.split('=', 1)[1]
            
            if not account_name or not account_key:
                raise AzureServiceError("Could not extract account credentials from connection string")
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self.container_name,
                blob_name=filename,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
            )
            
            # Construct full SAS URL
            sas_url = f"{blob_client.url}?{sas_token}"
            logger.info(f"Generated SAS URL for {filename} with {expiry_minutes} minute expiry")
            return sas_url
            
        except BlobNotFoundError:
            raise
            
        except ResourceNotFoundError as e:
            logger.error(f"Blob not found: {filename}")
            raise BlobNotFoundError(f"Blob not found: {filename}")
            
        except HttpResponseError as e:
            logger.error(f"Azure service error generating SAS URL for {filename}: {str(e)}")
            raise AzureServiceError(f"Azure service error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error generating SAS URL for {filename}: {str(e)}")
            raise AzureServiceError(f"Unexpected Azure error: {str(e)}")
    
    async def blob_exists(self, filename: str) -> bool:
        """Check if blob exists in Azure storage.
        
        Args:
            filename: Name of the blob to check
            
        Returns:
            True if blob exists, False otherwise
        """
        try:
            blob_client = self.container_client.get_blob_client(filename)
            exists = await blob_client.exists()
            logger.debug(f"Blob existence check for {filename}: {exists}")
            return exists
            
        except Exception as e:
            logger.error(f"Error checking blob existence for {filename}: {str(e)}")
            return False
