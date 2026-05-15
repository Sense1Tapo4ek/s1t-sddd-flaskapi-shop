from typing import Any

import boto3
from botocore.config import Config

from system.domain import StorageSettings


def build_s3_client(settings: StorageSettings) -> Any:
    """
    Build a boto3 S3 client from a StorageSettings snapshot.
    Caller MUST guarantee `settings.is_s3` and that required fields are set.
    """
    config = Config(
        s3={"addressing_style": "path" if settings.force_path_style else "auto"},
        signature_version="s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )
    kwargs: dict[str, Any] = {
        "service_name": "s3",
        "aws_access_key_id": settings.access_key_id,
        "aws_secret_access_key": settings.secret_access_key,
        "config": config,
    }
    if settings.endpoint_url:
        kwargs["endpoint_url"] = settings.endpoint_url
    if settings.region:
        kwargs["region_name"] = settings.region
    return boto3.client(**kwargs)
