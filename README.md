# Cloud Storage Service

A FastAPI-based REST API service for secure file upload and retrieval using Azure Blob Storage.

## Features

- Asynchronous file upload with streaming to Azure Blob Storage
- Secure download via SAS URLs (10-minute expiry)
- SQLite-based metadata tracking
- File size validation
- Comprehensive error handling
- Docker containerization

## API Endpoints

### POST /upload
Upload a file via multipart/form-data.

**Request:**
- Content-Type: multipart/form-data
- Field: `file` (the file to upload)

**Response (201 Created):**
```json
{
  "filename": "example.txt",
  "size": 1024,
  "upload_timestamp": "2023-10-01T12:00:00Z"
}
```

**Error Responses:**
- 413 Payload Too Large: File exceeds maximum size
- 502 Bad Gateway: Azure service error
- 504 Gateway Timeout: Azure connection timeout

### GET /download/{filename}
Download a file by generating a SAS URL.

**Response (200 OK):**
```json
{
  "filename": "example.txt",
  "sas_url": "https://..."
}
```

**Error Responses:**
- 404 Not Found: File not found
- 502 Bad Gateway: Azure service error

## Environment Variables

Create a `.env` file with the following variables:

- `AZURE_STORAGE_CONNECTION_STRING`: Azure Storage account connection string
- `AZURE_CONTAINER_NAME`: Name of the Azure Blob container
- `MAX_FILE_SIZE_MB`: Maximum file size in MB (default: 100)
- `SAS_URL_EXPIRY_MINUTES`: SAS URL expiry time in minutes (default: 10)
- `DATABASE_PATH`: Path to SQLite database file (default: metadata.db)

## Local Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables in `.env` file
6. Run the application: `uvicorn app.main:app --reload`

## Docker Setup

### Build the Image
```bash
docker build -t cloud-storage-service .
```

### Run the Container
```bash
docker run -p 8000:8000 --env-file .env cloud-storage-service
```

The API will be available at `http://localhost:8000`.

### Health Check
The application includes automatic OpenAPI documentation at `/docs`.

## Requirements

- Python 3.8+
- Azure Storage Account
- Docker (optional)

## Testing

Run tests with:
```bash
pytest
```

## License

[Add license information here]