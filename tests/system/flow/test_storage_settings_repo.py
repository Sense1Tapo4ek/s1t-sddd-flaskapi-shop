import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from shared.adapters.driven import Base, SecretCipher
from system.adapters.driven.db.models import StorageSettingsModel
from system.domain import StorageSettings
from system.ports.driven import SqlStorageSettingsRepo


pytestmark = pytest.mark.flow


@pytest.fixture
def repo_and_session(mysql_test_db):
    engine = create_engine(mysql_test_db, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    cipher = SecretCipher(_key=Fernet.generate_key().decode())
    repo = SqlStorageSettingsRepo(_session_factory=session_factory, _cipher=cipher)
    return repo, session_factory


class TestSqlStorageSettingsRepo:
    def test_save_and_load_roundtrip(self, repo_and_session):
        """
        Given an s3 configuration,
        When saving and loading it back,
        Then all fields are preserved including the secret.
        """
        # Arrange
        repo, _ = repo_and_session
        original = StorageSettings(
            id=1,
            backend="s3",
            endpoint_url="https://s3.amazonaws.com",
            region="us-east-1",
            bucket="my-bucket",
            access_key_id="AKIA",
            secret_access_key="super-secret",
            public_base_url="https://my-bucket.s3.amazonaws.com",
            force_path_style=True,
        )

        # Act
        repo.save(original)
        loaded = repo.get()

        # Assert
        assert loaded is not None
        assert loaded.backend == "s3"
        assert loaded.bucket == "my-bucket"
        assert loaded.access_key_id == "AKIA"
        assert loaded.secret_access_key == "super-secret"
        assert loaded.public_base_url == "https://my-bucket.s3.amazonaws.com"
        assert loaded.force_path_style is True

    def test_secret_is_encrypted_at_rest(self, repo_and_session):
        """
        Given a secret is saved,
        When inspecting the raw column value,
        Then the plaintext is NOT present and a Fernet token is stored instead.
        """
        # Arrange
        repo, session_factory = repo_and_session
        plaintext = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        repo.save(StorageSettings(id=1, backend="local", secret_access_key=plaintext))

        # Act
        with session_factory() as session:
            row = session.execute(
                select(StorageSettingsModel).where(StorageSettingsModel.id == 1)
            ).scalar_one()

        # Assert
        assert row.secret_access_key_enc != plaintext
        assert plaintext not in row.secret_access_key_enc
        assert len(row.secret_access_key_enc) > 0  # Fernet token

    def test_empty_secret_stays_empty_in_storage(self, repo_and_session):
        """
        Given an empty secret,
        When saving,
        Then the encrypted column stores an empty string (cipher short-circuits).
        """
        # Arrange
        repo, session_factory = repo_and_session
        repo.save(StorageSettings(id=1, backend="local", secret_access_key=""))

        # Act
        with session_factory() as session:
            row = session.execute(
                select(StorageSettingsModel).where(StorageSettingsModel.id == 1)
            ).scalar_one()

        # Assert
        assert row.secret_access_key_enc == ""

    def test_get_returns_none_when_no_row(self, repo_and_session):
        """
        Given an empty storage_settings table,
        When calling get(),
        Then the result is None (use case will translate to NotFound).
        """
        # Arrange
        repo, _ = repo_and_session

        # Act
        result = repo.get()

        # Assert
        assert result is None

    def test_save_is_idempotent_singleton(self, repo_and_session):
        """
        Given multiple saves,
        When inspecting the table,
        Then exactly one row exists (id=1 singleton).
        """
        # Arrange
        repo, session_factory = repo_and_session

        # Act
        repo.save(StorageSettings(id=1, backend="local"))
        repo.save(StorageSettings(id=1, backend="s3", bucket="b"))

        # Assert
        with session_factory() as session:
            rows = session.execute(select(StorageSettingsModel)).all()
        assert len(rows) == 1
