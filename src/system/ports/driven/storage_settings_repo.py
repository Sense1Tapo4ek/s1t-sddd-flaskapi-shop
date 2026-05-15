from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.adapters.driven.secret_cipher import SecretCipher
from shared.helpers.db import handle_db_errors
from system.adapters.driven.db.models import StorageSettingsModel
from system.app.interfaces import IStorageSettingsRepo
from system.domain import StorageSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class SqlStorageSettingsRepo(IStorageSettingsRepo):
    """
    Persists StorageSettings as a singleton row (id=1).
    `secret_access_key` is encrypted at rest via Fernet.
    """

    _session_factory: Callable[[], Session]
    _cipher: SecretCipher

    def _to_domain(self, model: StorageSettingsModel) -> StorageSettings:
        return StorageSettings(
            id=model.id,
            backend=model.backend,  # type: ignore[arg-type]
            endpoint_url=model.endpoint_url,
            region=model.region,
            bucket=model.bucket,
            access_key_id=model.access_key_id,
            secret_access_key=self._cipher.decrypt(model.secret_access_key_enc),
            public_base_url=model.public_base_url,
            force_path_style=bool(model.force_path_style),
        )

    @handle_db_errors("load storage settings")
    def get(self) -> StorageSettings | None:
        with self._session_factory() as session:
            model = session.execute(
                select(StorageSettingsModel).where(StorageSettingsModel.id == 1)
            ).scalar_one_or_none()
            return self._to_domain(model) if model else None

    @handle_db_errors("save storage settings")
    def save(self, settings: StorageSettings) -> None:
        with self._session_factory() as session:
            model = session.execute(
                select(StorageSettingsModel).where(StorageSettingsModel.id == 1)
            ).scalar_one_or_none()
            if model is None:
                model = StorageSettingsModel(id=1)
                session.add(model)
            model.backend = settings.backend
            model.endpoint_url = settings.endpoint_url
            model.region = settings.region
            model.bucket = settings.bucket
            model.access_key_id = settings.access_key_id
            model.secret_access_key_enc = self._cipher.encrypt(settings.secret_access_key)
            model.public_base_url = settings.public_base_url
            model.force_path_style = settings.force_path_style
            session.commit()
