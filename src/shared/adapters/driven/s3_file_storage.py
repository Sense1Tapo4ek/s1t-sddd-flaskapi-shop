import logging
import mimetypes
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from botocore.exceptions import BotoCoreError, ClientError

from shared.generics.errors import DrivenAdapterError
from shared.helpers.media_validation import validate_media_upload


logger = logging.getLogger(__name__)


_OBJECT_PREFIX = "products/"


@dataclass(frozen=True, slots=True, kw_only=True)
class S3FileStorage:
    """
    Stores media in an S3-compatible public bucket.

    `save()` uploads a uniquely named object under `products/` and returns
    its public URL composed from `public_base_url`. The bucket MUST be
    publicly readable; private buckets with presigned URLs are out of MVP scope.
    """

    _client: Any  # boto3 S3 client
    _bucket: str
    _public_base_url: str  # without trailing slash

    def save(self, filename: str, data: bytes) -> str:
        ext = validate_media_upload(filename, data)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        key = f"{_OBJECT_PREFIX}{unique_name}"

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.exception(
                "s3 upload failed bucket=%s key=%s", self._bucket, key
            )
            raise DrivenAdapterError(
                message="Не удалось загрузить файл в S3",
                code="S3_UPLOAD_FAILED",
            ) from exc

        return f"{self._public_base_url}/{key}"

    def delete(self, file_path: str) -> bool:
        """
        Accepts either a full URL produced by `save()` or a bare object key.
        Returns True on successful deletion attempt, False if the URL is foreign
        (does not belong to this bucket's public_base_url).
        """
        key = self._extract_key(file_path)
        if key is None:
            return False
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            return True
        except (ClientError, BotoCoreError) as exc:
            logger.exception(
                "s3 delete failed bucket=%s key=%s", self._bucket, key
            )
            raise DrivenAdapterError(
                message="Не удалось удалить файл из S3",
                code="S3_DELETE_FAILED",
            ) from exc

    def _extract_key(self, file_path: str) -> str | None:
        if not file_path:
            return None
        if file_path.startswith(_OBJECT_PREFIX):
            return file_path
        parsed = urlparse(file_path)
        if not parsed.scheme:
            # Bare key like "products/abc.jpg"
            return file_path.lstrip("/")
        base_parsed = urlparse(self._public_base_url)
        if (parsed.scheme, parsed.netloc) != (base_parsed.scheme, base_parsed.netloc):
            return None
        base_path = base_parsed.path.rstrip("/")
        path = parsed.path
        if base_path and path.startswith(base_path + "/"):
            path = path[len(base_path) + 1 :]
        return path.lstrip("/") or None
