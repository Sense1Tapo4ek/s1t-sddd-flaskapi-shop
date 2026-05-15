import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import InfraConfig


def create_db_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    pool_recycle: int = 3600,
    pool_pre_ping: bool = True,
) -> Engine:
    """Create a SQLAlchemy engine tuned for MySQL on shared hosting.

    pool_pre_ping is mandatory on CPanel — shared hosts drop idle
    connections silently and SQLAlchemy then hands out dead handles.
    pool_recycle bounds connection age below MySQL's wait_timeout.
    """
    return create_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        future=True,
    )


def create_db_engine_from_config(config: InfraConfig) -> Engine:
    return create_db_engine(
        config.database_url,
        pool_size=config.db_pool_size,
        pool_recycle=config.db_pool_recycle,
        pool_pre_ping=config.db_pool_pre_ping,
    )


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    os.makedirs("media", exist_ok=True)
    engine = create_db_engine(database_url)
    return create_session_factory_for_engine(engine)


def create_session_factory_for_engine(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
