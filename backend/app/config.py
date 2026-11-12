"""Application settings."""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

_DEFAULT_JWT_SECRET = "lexsecure-local-development-jwt-secret-change-me"
_DEFAULT_DOCUMENT_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
_ENV_FILES = [
    ".env",
    os.path.join(_BACKEND_DIR, ".env"),
    os.path.join(_PROJECT_DIR, ".env"),
]


def env_file_status() -> List[dict]:
    return [
        {"path": p, "exists": os.path.exists(p)}
        for p in _ENV_FILES
    ]


class Settings(BaseSettings):
    PROJECT_NAME: str = "LEXSECURE - Secure Digital Document Management System"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    DOCUMENT_ENCRYPTION_KEY: str = os.getenv(
        "DOCUMENT_ENCRYPTION_KEY",
        _DEFAULT_DOCUMENT_KEY
    )
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        _DEFAULT_JWT_SECRET
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    MFA_ISSUER: str = os.getenv("MFA_ISSUER", "LexSecure NCRB")
    MFA_TOTP_WINDOW: int = int(os.getenv("MFA_TOTP_WINDOW", "1"))
    MFA_BACKUP_CODE_COUNT: int = int(os.getenv("MFA_BACKUP_CODE_COUNT", "10"))
    MFA_ENROLLMENT_TOKEN_MINUTES: int = int(os.getenv("MFA_ENROLLMENT_TOKEN_MINUTES", "10"))

    INTEGRITY_CHECK_INTERVAL_SECONDS: int = int(os.getenv("INTEGRITY_CHECK_INTERVAL_SECONDS", "300"))

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "none")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODELS: str = os.getenv("GEMINI_MODELS", "")

    NARA_API_KEY: str = os.getenv("NARA_API_KEY", "")
    NARA_BASE_URL: str = os.getenv("NARA_BASE_URL", "https://router.bynara.id/v1")
    NARA_MODELS: str = os.getenv("NARA_MODELS", "")
    NARA_EMBEDDING_MODEL: str = os.getenv("NARA_EMBEDDING_MODEL", "")
    LLM_THINKING_BUDGET: int = int(os.getenv("LLM_THINKING_BUDGET", "0"))

    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '../../lexsecure.db'))}"
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE_SECONDS: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))

    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "vault")
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "lexsecure-documents")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").strip().lower() in ("1", "true", "yes", "on")
    LOCAL_STORAGE_VAULT_DIR: str = os.getenv(
        "LOCAL_STORAGE_VAULT_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../storage/vault"))
    )

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ]

    @model_validator(mode="after")
    def _enforce_production_security(self):
        if self.ENVIRONMENT.strip().lower() == "production":
            insecure = []
            if self.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
                insecure.append("JWT_SECRET_KEY")
            if self.DOCUMENT_ENCRYPTION_KEY == _DEFAULT_DOCUMENT_KEY:
                insecure.append("DOCUMENT_ENCRYPTION_KEY")
            if insecure:
                raise RuntimeError(
                    "Refusing to start in production with prototype-default secrets: "
                    + ", ".join(insecure)
                    + ". Source them from a KMS/secret manager or a .env file."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        case_sensitive=True,
    )

settings = Settings()
