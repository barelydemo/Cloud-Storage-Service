"""
Metadata store for tracking file upload information using SQLite.
"""

import aiosqlite
from datetime import datetime
from typing import Optional
from app.models import FileMetadata


class MetadataStore:
    """SQLite-based metadata store for file tracking.
    
    Manages persistent storage of file metadata including filename, size,
    and upload timestamp. Uses aiosqlite for async database operations.
    
    Attributes:
        db_path: Path to the SQLite database file
    """
    
    def __init__(self, db_path: str = "metadata.db"):
        """Initialize the metadata store.
        
        Args:
            db_path: Path to the SQLite database file (default: "metadata.db")
        """
        self.db_path = db_path
    
    async def initialize(self) -> None:
        """Initialize the database schema if it doesn't exist.
        
        Creates the files table with columns for filename (primary key),
        size, and upload_timestamp.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    filename TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    upload_timestamp TEXT NOT NULL
                )
            """)
            await db.commit()
    
    async def record_upload(self, filename: str, size: int, timestamp: datetime) -> None:
        """Record successful file upload metadata.
        
        Args:
            filename: Name of the uploaded file
            size: File size in bytes
            timestamp: Upload completion timestamp
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO files (filename, size, upload_timestamp) VALUES (?, ?, ?)",
                (filename, size, timestamp.isoformat())
            )
            await db.commit()
    
    async def get_metadata(self, filename: str) -> Optional[FileMetadata]:
        """Retrieve metadata for a specific file.
        
        Args:
            filename: Name of the file to look up
            
        Returns:
            FileMetadata object if found, None otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT filename, size, upload_timestamp FROM files WHERE filename = ?",
                (filename,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return FileMetadata(
                        filename=row[0],
                        size=row[1],
                        upload_timestamp=datetime.fromisoformat(row[2])
                    )
                return None
