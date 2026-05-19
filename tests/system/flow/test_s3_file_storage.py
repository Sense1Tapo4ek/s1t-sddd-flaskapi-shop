import pytest
from botocore.exceptions import ClientError

from shared.adapters.driven import S3FileStorage
from shared.generics.errors import ApplicationError, DrivenAdapterError


pytestmark = pytest.mark.flow


class _StubClient:
    def __init__(self, raise_with: Exception | None = None) -> None:
        self.put_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self._raise = raise_with

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self._raise is not None:
            raise self._raise

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)
        if self._raise is not None:
            raise self._raise


def _client_error(code: str = "AccessDenied") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "Access denied for bucket"}},
        operation_name="PutObject",
    )


def _make_storage(client, base_url: str = "https://cdn.example.com") -> S3FileStorage:
    return S3FileStorage(_client=client, _bucket="my-bucket", _public_base_url=base_url)


class TestS3FileStorageSave:
    def test_save_uploads_under_products_prefix_and_returns_public_url(self):
        """
        Given a stubbed S3 client,
        When saving a JPG,
        Then the object is uploaded under products/<uuid>.jpg and the public URL is returned.
        """
        # Arrange
        client = _StubClient()
        storage = _make_storage(client)

        # Act
        url = storage.save("photo.JPG", b"\x00\x01\x02")

        # Assert
        assert len(client.put_calls) == 1
        call = client.put_calls[0]
        assert call["Bucket"] == "my-bucket"
        assert call["Key"].startswith("products/")
        assert call["Key"].endswith(".jpg")
        assert call["ContentType"] == "image/jpeg"
        assert url == f"https://cdn.example.com/{call['Key']}"

    def test_invalid_extension_is_rejected_before_any_upload(self):
        """
        Given a file with disallowed extension,
        When saving,
        Then ApplicationError is raised and S3 is NOT called.
        """
        # Arrange
        client = _StubClient()
        storage = _make_storage(client)

        # Act / Assert
        with pytest.raises(ApplicationError):
            storage.save("evil.exe", b"data")
        assert client.put_calls == []

    def test_client_error_is_wrapped_without_leaking_raw_message(self):
        """
        Given S3 raises ClientError with infra details,
        When saving,
        Then a DrivenAdapterError is raised with a fixed user-facing message
        (no bucket name, no AWS error code).
        """
        # Arrange
        client = _StubClient(raise_with=_client_error())
        storage = _make_storage(client)

        # Act / Assert
        with pytest.raises(DrivenAdapterError) as exc_info:
            storage.save("photo.png", b"\x00")
        assert exc_info.value.code == "S3_UPLOAD_FAILED"
        assert "AccessDenied" not in exc_info.value.message
        assert "my-bucket" not in exc_info.value.message
        assert "Access denied" not in exc_info.value.message


class TestS3FileStorageDelete:
    def test_delete_extracts_key_from_full_url(self):
        """
        Given a URL produced by save(),
        When deleting,
        Then the bucket-relative key is sent to S3.
        """
        # Arrange
        client = _StubClient()
        storage = _make_storage(client)

        # Act
        result = storage.delete("https://cdn.example.com/products/abc.jpg")

        # Assert
        assert result is True
        assert client.delete_calls == [{"Bucket": "my-bucket", "Key": "products/abc.jpg"}]

    def test_delete_accepts_bare_key(self):
        """
        Given a bare object key,
        When deleting,
        Then S3 is called with the same key.
        """
        # Arrange
        client = _StubClient()
        storage = _make_storage(client)

        # Act
        result = storage.delete("products/abc.jpg")

        # Assert
        assert result is True
        assert client.delete_calls[-1]["Key"] == "products/abc.jpg"

    def test_delete_rejects_foreign_url_without_calling_s3(self):
        """
        Given a URL pointing to a different host,
        When deleting,
        Then S3 is NOT called and the result is False.
        """
        # Arrange
        client = _StubClient()
        storage = _make_storage(client)

        # Act
        result = storage.delete("https://other-host.example.com/products/abc.jpg")

        # Assert
        assert result is False
        assert client.delete_calls == []

    def test_delete_wraps_client_error(self):
        """
        Given S3 raises on delete,
        When deleting,
        Then DrivenAdapterError is raised with a fixed message.
        """
        # Arrange
        client = _StubClient(raise_with=_client_error())
        storage = _make_storage(client)

        # Act / Assert
        with pytest.raises(DrivenAdapterError) as exc_info:
            storage.delete("products/abc.jpg")
        assert exc_info.value.code == "S3_DELETE_FAILED"
        assert "AccessDenied" not in exc_info.value.message
