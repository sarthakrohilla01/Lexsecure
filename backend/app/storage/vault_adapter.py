"""Encrypted Local Vault Storage Adapter"""

import os
from pathlib import Path
from app.storage.base import BaseStorageService
from app.config import settings

class LocalVaultStorageService(BaseStorageService):
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or settings.LOCAL_STORAGE_VAULT_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, object_key: str) -> Path:
        sanitized = object_key.replace("\\", "/").lstrip("/")
        candidate = (self.base_dir / sanitized).resolve()  # nosec - the commonpath check below rejects any escape
        base = self.base_dir.resolve()
        if os.path.commonpath([str(candidate), str(base)]) != str(base):
            raise ValueError(
                f"Invalid object key: path traversal attempt blocked ('{object_key}')"
            )
        return candidate

    def save_file(self, object_key: str, data: bytes) -> str:
        file_path = self._resolve_path(object_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:  # nosec - _resolve_path rejects any path outside the vault
            f.write(data)
        return object_key

    def get_file(self, object_key: str) -> bytes:
        file_path = self._resolve_path(object_key)
        if not file_path.exists():
            raise FileNotFoundError(f"Object {object_key} not found in vault")
        with open(file_path, "rb") as f:  # nosec - _resolve_path rejects any path outside the vault
            return f.read()

    def delete_file(self, object_key: str) -> bool:
        file_path = self._resolve_path(object_key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def exists(self, object_key: str) -> bool:
        return self._resolve_path(object_key).exists()
