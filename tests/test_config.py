"""Unit tests for configuration management."""

import pytest
from pydantic import ValidationError
from config.settings import Settings


class TestSettings:
    """Test suite for Settings class configuration validation."""
    
    def test_missing_azure_connection_string_fails(self, monkeypatch):
        """Test that missing AZURE_STORAGE_CONNECTION_STRING causes validation error.
        
        Validates: Requirements 7.4 - Missing required environment variables should
        trigger startup failure.
        """
        # Clear all Azure-related environment variables
        monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        # Verify the error is about the missing field
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("azure_storage_connection_string",) 
            and error["type"] == "missing"
            for error in errors
        )
    
    def test_missing_azure_container_name_fails(self, monkeypatch):
        """Test that missing AZURE_CONTAINER_NAME causes validation error.
        
        Validates: Requirements 7.4 - Missing required environment variables should
        trigger startup failure.
        """
        # Clear all Azure-related environment variables
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.delenv("AZURE_CONTAINER_NAME", raising=False)
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        # Verify the error is about the missing field
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("azure_container_name",) 
            and error["type"] == "missing"
            for error in errors
        )
    
    def test_missing_all_required_fields_fails(self, monkeypatch):
        """Test that missing all required environment variables causes validation error.
        
        Validates: Requirements 7.4 - Missing required environment variables should
        trigger startup failure.
        """
        # Clear all Azure-related environment variables
        monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_CONTAINER_NAME", raising=False)
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        # Verify both required fields are reported as missing
        errors = exc_info.value.errors()
        missing_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert "azure_storage_connection_string" in missing_fields
        assert "azure_container_name" in missing_fields
    
    def test_default_max_file_size_mb(self, monkeypatch):
        """Test that max_file_size_mb has default value of 100.
        
        Validates: Requirements 7.4 - Optional settings should have correct default values.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        monkeypatch.delenv("MAX_FILE_SIZE_MB", raising=False)
        
        settings = Settings()
        
        assert settings.max_file_size_mb == 100
    
    def test_default_sas_url_expiry_minutes(self, monkeypatch):
        """Test that sas_url_expiry_minutes has default value of 10.
        
        Validates: Requirements 7.4 - Optional settings should have correct default values.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        monkeypatch.delenv("SAS_URL_EXPIRY_MINUTES", raising=False)
        
        settings = Settings()
        
        assert settings.sas_url_expiry_minutes == 10
    
    def test_default_database_path(self, monkeypatch):
        """Test that database_path has default value of 'metadata.db'.
        
        Validates: Requirements 7.4 - Optional settings should have correct default values.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        
        settings = Settings()
        
        assert settings.database_path == "metadata.db"
    
    def test_all_default_values_together(self, monkeypatch):
        """Test that all optional settings have correct defaults when not provided.
        
        Validates: Requirements 7.4 - Optional settings should have correct default values.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        monkeypatch.delenv("MAX_FILE_SIZE_MB", raising=False)
        monkeypatch.delenv("SAS_URL_EXPIRY_MINUTES", raising=False)
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        
        settings = Settings()
        
        assert settings.max_file_size_mb == 100
        assert settings.sas_url_expiry_minutes == 10
        assert settings.database_path == "metadata.db"
    
    def test_custom_optional_values_override_defaults(self, monkeypatch):
        """Test that custom values for optional settings override defaults.
        
        Validates: Requirements 7.4 - Optional settings can be customized via environment.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "200")
        monkeypatch.setenv("SAS_URL_EXPIRY_MINUTES", "15")
        monkeypatch.setenv("DATABASE_PATH", "custom.db")
        
        settings = Settings()
        
        assert settings.max_file_size_mb == 200
        assert settings.sas_url_expiry_minutes == 15
        assert settings.database_path == "custom.db"
    
    def test_successful_initialization_with_required_fields(self, monkeypatch):
        """Test that Settings initializes successfully with all required fields.
        
        Validates: Requirements 7.1, 7.2 - Service should read Azure configuration
        from environment variables.
        """
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=test")
        monkeypatch.setenv("AZURE_CONTAINER_NAME", "test-container")
        
        settings = Settings()
        
        assert settings.azure_storage_connection_string == "DefaultEndpointsProtocol=https;AccountName=test"
        assert settings.azure_container_name == "test-container"
