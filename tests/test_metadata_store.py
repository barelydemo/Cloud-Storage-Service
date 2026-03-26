"""
Unit tests for MetadataStore SQLite backend.
"""

import pytest
import os
import tempfile
from datetime import datetime
from app.metadata_store import MetadataStore
from app.models import FileMetadata


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.mark.asyncio
async def test_initialize_creates_schema(temp_db):
    """Test that initialize() creates the database schema."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    # Verify the database file was created
    assert os.path.exists(temp_db)


@pytest.mark.asyncio
async def test_record_upload_stores_metadata(temp_db):
    """Test that record_upload() stores metadata correctly."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    await store.record_upload("test.txt", 1024, timestamp)
    
    # Verify metadata was stored
    metadata = await store.get_metadata("test.txt")
    assert metadata is not None
    assert metadata.filename == "test.txt"
    assert metadata.size == 1024
    assert metadata.upload_timestamp == timestamp


@pytest.mark.asyncio
async def test_get_metadata_returns_none_for_nonexistent_file(temp_db):
    """Test that get_metadata() returns None for files that don't exist."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    metadata = await store.get_metadata("nonexistent.txt")
    assert metadata is None


@pytest.mark.asyncio
async def test_metadata_persistence_across_connections(temp_db):
    """Test that metadata persists across different store instances."""
    # First connection - store data
    store1 = MetadataStore(temp_db)
    await store1.initialize()
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    await store1.record_upload("persistent.txt", 2048, timestamp)
    
    # Second connection - retrieve data
    store2 = MetadataStore(temp_db)
    metadata = await store2.get_metadata("persistent.txt")
    
    assert metadata is not None
    assert metadata.filename == "persistent.txt"
    assert metadata.size == 2048
    assert metadata.upload_timestamp == timestamp


@pytest.mark.asyncio
async def test_record_upload_replaces_existing_metadata(temp_db):
    """Test that record_upload() replaces existing metadata for the same filename."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    # First upload
    timestamp1 = datetime(2024, 1, 15, 10, 30, 0)
    await store.record_upload("test.txt", 1024, timestamp1)
    
    # Second upload with same filename
    timestamp2 = datetime(2024, 1, 15, 11, 30, 0)
    await store.record_upload("test.txt", 2048, timestamp2)
    
    # Verify only the latest metadata exists
    metadata = await store.get_metadata("test.txt")
    assert metadata.size == 2048
    assert metadata.upload_timestamp == timestamp2


@pytest.mark.asyncio
async def test_multiple_files_stored_independently(temp_db):
    """Test that multiple files can be stored and retrieved independently."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    timestamp1 = datetime(2024, 1, 15, 10, 30, 0)
    timestamp2 = datetime(2024, 1, 15, 11, 30, 0)
    
    await store.record_upload("file1.txt", 1024, timestamp1)
    await store.record_upload("file2.txt", 2048, timestamp2)
    
    # Verify both files exist independently
    metadata1 = await store.get_metadata("file1.txt")
    metadata2 = await store.get_metadata("file2.txt")
    
    assert metadata1.filename == "file1.txt"
    assert metadata1.size == 1024
    assert metadata2.filename == "file2.txt"
    assert metadata2.size == 2048


@pytest.mark.asyncio
async def test_timestamp_iso_format_roundtrip(temp_db):
    """Test that timestamps are correctly stored and retrieved in ISO format."""
    store = MetadataStore(temp_db)
    await store.initialize()
    
    # Use a timestamp with microseconds
    timestamp = datetime(2024, 1, 15, 10, 30, 45, 123456)
    await store.record_upload("test.txt", 1024, timestamp)
    
    metadata = await store.get_metadata("test.txt")
    assert metadata.upload_timestamp == timestamp


# Property-based tests using Hypothesis

from hypothesis import given, settings, strategies as st


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
timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
)


@pytest.fixture
def temp_db_property():
    """Create a temporary database for property-based testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@settings(max_examples=100)
@given(
    filename=filename_strategy,
    size=file_size_strategy,
    upload_timestamp=timestamp_strategy
)
@pytest.mark.asyncio
async def test_property_10_metadata_recording_on_upload(filename, size, upload_timestamp):
    """
    Feature: cloud-storage-service, Property 10: Metadata Recording on Upload
    
    **Validates: Requirements 4.1**
    
    For any successfully uploaded file, the metadata store should contain a record 
    with the exact filename, file size in bytes, and upload timestamp.
    """
    # Create a temporary database for this test
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Initialize metadata store
        store = MetadataStore(db_path)
        await store.initialize()
        
        # Record upload metadata (simulating a successful upload)
        await store.record_upload(filename, size, upload_timestamp)
        
        # Retrieve the metadata
        metadata = await store.get_metadata(filename)
        
        # Verify metadata was recorded
        assert metadata is not None, f"Metadata must be recorded for uploaded file '{filename}'"
        
        # Verify exact filename preservation
        assert metadata.filename == filename, \
            f"Stored filename must exactly match uploaded filename: expected '{filename}', got '{metadata.filename}'"
        
        # Verify exact file size in bytes
        assert metadata.size == size, \
            f"Stored size must exactly match uploaded file size: expected {size} bytes, got {metadata.size} bytes"
        assert isinstance(metadata.size, int), "File size must be stored as an integer"
        assert metadata.size > 0, "File size must be positive"
        
        # Verify exact timestamp preservation
        assert metadata.upload_timestamp == upload_timestamp, \
            f"Stored timestamp must exactly match upload timestamp: expected {upload_timestamp}, got {metadata.upload_timestamp}"
        assert isinstance(metadata.upload_timestamp, datetime), "Upload timestamp must be a datetime object"
        
        # Verify metadata persists (can be retrieved again)
        metadata_again = await store.get_metadata(filename)
        assert metadata_again is not None, "Metadata must persist and be retrievable multiple times"
        assert metadata_again.filename == filename, "Persisted metadata must maintain exact filename"
        assert metadata_again.size == size, "Persisted metadata must maintain exact size"
        assert metadata_again.upload_timestamp == upload_timestamp, "Persisted metadata must maintain exact timestamp"
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
