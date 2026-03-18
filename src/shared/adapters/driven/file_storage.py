import os
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalFileStorage:
    _upload_dir: str

    def __post_init__(self) -> None:
        os.makedirs(self._upload_dir, exist_ok=True)

    def save(self, filename: str, data: bytes) -> str:
        ext = os.path.splitext(filename)[1] or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(self._upload_dir, unique_name)
        with open(file_path, "wb") as f:
            f.write(data)
        return f"/media/products/{unique_name}"

    def delete(self, file_path: str) -> bool:
        relative = file_path.lstrip("/")
        full_path = os.path.join(os.getcwd(), relative)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
