"""Storage Service Abstract Base Class"""

from abc import ABC, abstractmethod

class BaseStorageService(ABC):
    @abstractmethod
    def save_file(self, object_key: str, data: bytes) -> str:
        """Stores binary payload under object_key. Returns object_key or URI."""
        pass

    @abstractmethod
    def get_file(self, object_key: str) -> bytes:
        """Retrieves raw binary payload from storage."""
        pass

    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        """Deletes object from storage."""
        pass

    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """Checks if object exists in storage."""
        pass
