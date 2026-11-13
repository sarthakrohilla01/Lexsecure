"""MinIO S3 Object Storage Adapter"""

import io
from minio import Minio
from app.storage.base import BaseStorageService
from app.config import settings

class MinioStorageService(BaseStorageService):
    def __init__(self):
        self.bucket = settings.MINIO_BUCKET
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as exc:
            import logging
            logging.getLogger("lexsecure.storage").warning(
                "Could not verify or create the MinIO bucket %r: %s", self.bucket, exc
            )

    def save_file(self, object_key: str, data: bytes) -> str:
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=stream,
            length=len(data)
        )
        return object_key

    def get_file(self, object_key: str) -> bytes:
        response = None
        try:
            response = self.client.get_object(self.bucket, object_key)
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    def delete_file(self, object_key: str) -> bool:
        try:
            self.client.remove_object(self.bucket, object_key)
            return True
        except Exception:
            return False

    def exists(self, object_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except Exception:
            return False
