"""Configuration settings for the Cloud Storage Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All settings can be configured via environment variables or a .env file.
    Required fields will cause startup failure if not provided.
    """
    
    # Required Azure configuration
    azure_storage_connection_string: str
    azure_container_name: str
    
    # Optional configuration with defaults
    max_file_size_mb: int = 100
    sas_url_expiry_minutes: int = 10
    database_path: str = "metadata.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
