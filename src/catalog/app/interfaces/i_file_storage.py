from typing import Protocol, runtime_checkable


@runtime_checkable
class IFileStorage(Protocol):
    def save(self, filename: str, data: bytes) -> str: ...
    def delete(self, file_path: str) -> bool: ...
