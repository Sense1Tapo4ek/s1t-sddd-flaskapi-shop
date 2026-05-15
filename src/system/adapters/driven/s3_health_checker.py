import logging
from dataclasses import dataclass

from botocore.exceptions import BotoCoreError, ClientError

from system.adapters.driven.s3_client_factory import build_s3_client
from system.app import S3ConnectionError
from system.app.interfaces import IS3HealthChecker
from system.domain import StorageSettings


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class S3HealthChecker(IS3HealthChecker):
    """
    Verifies that the bucket described by `StorageSettings` is reachable
    with the supplied credentials by issuing a HEAD on the bucket.
    """

    def check(self, settings: StorageSettings) -> None:
        if not settings.is_s3:
            return
        client = build_s3_client(settings)
        try:
            client.head_bucket(Bucket=settings.bucket)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code") or "Unknown"
            message = error.get("Message") or str(exc)
            logger.warning(
                "s3 health check failed bucket=%s code=%s",
                settings.bucket,
                code,
            )
            raise S3ConnectionError(detail=f"{code}: {message}") from exc
        except BotoCoreError as exc:
            logger.warning(
                "s3 health check transport failure bucket=%s err=%s",
                settings.bucket,
                exc,
            )
            raise S3ConnectionError(detail=str(exc)) from exc
