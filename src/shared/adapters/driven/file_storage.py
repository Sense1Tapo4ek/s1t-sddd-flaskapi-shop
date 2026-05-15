import os
import uuid
from dataclasses import dataclass

from shared.helpers.media_validation import validate_media_upload


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalFileStorage:
    _upload_dir: str

    def __post_init__(self) -> None:
        os.makedirs(self._upload_dir, exist_ok=True)

    def save(self, filename: str, data: bytes) -> str:
        ext = validate_media_upload(filename, data)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(self._upload_dir, unique_name)
        with open(file_path, "wb") as f:
            f.write(data)
        return f"/media/products/{unique_name}"

    def delete(self, file_path: str) -> bool:
        relative = file_path.lstrip("/")
        full_path = os.path.realpath(os.path.join(os.getcwd(), relative))
        allowed_dir = os.path.realpath(self._upload_dir)
        if not full_path.startswith(allowed_dir + os.sep):
            return False
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
