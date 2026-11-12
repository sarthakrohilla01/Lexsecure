"""Storage Service Factory"""

from app.config import settings
from app.storage.base import BaseStorageService
from app.storage.vault_adapter import LocalVaultStorageService

_storage_instance = None

def get_storage_service() -> BaseStorageService:
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    if settings.STORAGE_TYPE.lower() == "minio":
        try:
            from app.storage.minio_adapter import MinioStorageService
            service = MinioStorageService()
            _storage_instance = service
            return _storage_instance
        except Exception:
            pass

    _storage_instance = LocalVaultStorageService()
    return _storage_instance
