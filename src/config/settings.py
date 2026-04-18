"""Configuration settings for the FMC MCP Server."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: str = Field(
        default="postgresql://mcp_user:changeme@localhost:5432/fmc_mcp",
        description="PostgreSQL database connection URL",
    )

    # FMC Connection Configuration
    fmc_host_url: str = Field(
        default="https://192.168.1.1",
        description="Cisco FMC base URL (e.g. https://fmc.example.com)",
    )
    fmc_username: str = Field(
        default="admin",
        description="FMC username",
    )
    fmc_password: str = Field(
        default="",
        description="FMC password",
    )
    fmc_verify_ssl: bool = Field(
        default=False,
        description="Verify SSL certificates for FMC connections",
    )
    fmc_domain_uuid: Optional[str] = Field(
        default=None,
        description=(
            "Override the default domain UUID returned by FMC at login. "
            "Leave empty to use the domain returned by the FMC auth token."
        ),
    )

    # Security Configuration
    edit_mode_enabled: bool = Field(
        default=False,
        description="Enable write operations (POST/PUT/DELETE)",
    )
    encryption_key: Optional[str] = Field(
        default=None,
        description="Fernet encryption key for credential storage",
    )
    session_secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for session management",
    )
    session_timeout_minutes: int = Field(
        default=30,
        description="Session timeout in minutes",
    )

    # Server Configuration
    mcp_server_host: str = Field(
        default="0.0.0.0",
        description="MCP server bind host",
    )
    mcp_server_port: int = Field(
        default=8080,
        description="MCP server port",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # API Configuration
    api_timeout: int = Field(
        default=30,
        description="FMC API request timeout in seconds",
    )
    api_retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed API requests",
    )

    @property
    def is_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").lower() == "production"

    def get_encryption_key(self) -> bytes:
        if self.encryption_key:
            return self.encryption_key.encode()

        if not self.is_production:
            from cryptography.fernet import Fernet
            return Fernet.generate_key()

        raise ValueError(
            "ENCRYPTION_KEY must be set in production. "
            "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
