"""
Configuration settings for the Gauntlet Pipeline backend.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres@localhost:5432/gauntlet_pipeline"

    # JWT Authentication
    # WARNING: JWT_SECRET_KEY must be set via environment variable in production
    # Using a default only for local development - NEVER use in production
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"  # Only for local dev
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # External Services
    REPLICATE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = ""
    AWS_REGION: str = "us-east-2"

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Server Config
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = True
    
    # Video Processing API URL (used by frontend)
    VIDEO_PROCESSING_API_URL: Optional[str] = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
