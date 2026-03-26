"""
Main FastAPI application for Cloud Storage Service.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import logging

from app.models import UploadResponse, DownloadResponse, ErrorResponse
from app.azure_client import AzureStorageClient, AzureConnectionError, AzureServiceError, BlobNotFoundError
from app.metadata_store import MetadataStore
from config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables (will be set in lifespan)
settings: Settings = None
azure_client: AzureStorageClient = None
metadata_store: MetadataStore = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global azure_client, metadata_store, settings
    
    # Startup
    logger.info("Starting Cloud Storage Service...")
    
    # Load settings
    settings = Settings()
    
    # Validate required environment variables
    try:
        if not settings.azure_storage_connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is required")
        if not settings.azure_container_name:
            raise ValueError("AZURE_CONTAINER_NAME is required")
    except Exception as e:
        logger.error(f"Configuration error: {str(e)}")
        raise
    
    # Initialize Azure client
    azure_client = AzureStorageClient(
        connection_string=settings.azure_storage_connection_string,
        container_name=settings.azure_container_name
    )
    logger.info("Azure Storage client initialized")
    
    # Initialize metadata store
    metadata_store = MetadataStore(db_path=settings.database_path)
    await metadata_store.initialize()
    logger.info(f"Metadata store initialized at {settings.database_path}")
    
    logger.info("Cloud Storage Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Cloud Storage Service...")


# Create FastAPI application
app = FastAPI(
    title="Cloud Storage Service",
    description="REST API for secure file upload and retrieval using Azure Blob Storage",
    version="1.0.0",
    lifespan=lifespan
)


@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        413: {"model": ErrorResponse, "description": "File too large"},
        502: {"model": ErrorResponse, "description": "Azure service error"},
        504: {"model": ErrorResponse, "description": "Azure connection timeout"}
    }
)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to Azure Blob Storage.
    
    Accepts multipart/form-data with a file field. Validates file size,
    streams the file to Azure, and records metadata on success.
    
    Args:
        file: The file to upload (multipart/form-data)
        
    Returns:
        UploadResponse with filename, size, and upload timestamp
        
    Raises:
        HTTPException 413: File exceeds maximum size limit
        HTTPException 502: Azure service error
        HTTPException 504: Azure connection timeout
    """
    try:
        # Read file content to check size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        max_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            logger.warning(f"File too large: {file.filename} ({file_size} bytes)")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large"
            )
        
        # Stream file to Azure
        from io import BytesIO
        file_data = BytesIO(file_content)
        
        logger.info(f"Uploading file: {file.filename} ({file_size} bytes)")
        await azure_client.upload_blob(file.filename, file_data)
        
        # Record metadata
        upload_timestamp = datetime.utcnow()
        await metadata_store.record_upload(file.filename, file_size, upload_timestamp)
        
        logger.info(f"Successfully uploaded: {file.filename}")
        
        return UploadResponse(
            filename=file.filename,
            size=file_size,
            upload_timestamp=upload_timestamp
        )
        
    except HTTPException:
        raise
        
    except AzureConnectionError as e:
        logger.error(f"Azure connection timeout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Azure Connection Timeout"
        )
        
    except AzureServiceError as e:
        logger.error(f"Azure service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure service error: {str(e)}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get(
    "/download/{filename}",
    response_model=DownloadResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Blob not found"},
        502: {"model": ErrorResponse, "description": "Azure service error"}
    }
)
async def download_file(filename: str):
    """
    Generate a secure time-limited SAS URL for file download.
    
    Verifies the file exists in both metadata store and Azure Blob Storage,
    then generates a SAS URL with read-only permissions valid for 10 minutes.
    
    Args:
        filename: Name of the file to download
        
    Returns:
        DownloadResponse with filename and SAS URL
        
    Raises:
        HTTPException 404: File not found
        HTTPException 502: Azure service error
    """
    try:
        # Check if file exists in metadata store
        metadata = await metadata_store.get_metadata(filename)
        if not metadata:
            logger.warning(f"File not found in metadata: {filename}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blob Not Found"
            )
        
        # Verify blob exists in Azure
        blob_exists = await azure_client.blob_exists(filename)
        if not blob_exists:
            logger.warning(f"File not found in Azure: {filename}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blob Not Found"
            )
        
        # Generate SAS URL
        logger.info(f"Generating SAS URL for: {filename}")
        sas_url = await azure_client.generate_sas_url(
            filename,
            expiry_minutes=settings.sas_url_expiry_minutes
        )
        
        logger.info(f"Successfully generated SAS URL for: {filename}")
        
        return DownloadResponse(
            filename=filename,
            sas_url=sas_url
        )
        
    except HTTPException:
        raise
        
    except BlobNotFoundError as e:
        logger.warning(f"Blob not found: {filename}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blob Not Found"
        )
        
    except AzureServiceError as e:
        logger.error(f"Azure service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure service error: {str(e)}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
