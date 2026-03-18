import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    os.makedirs("media", exist_ok=True)
    engine = create_engine(database_url, echo=False)
    return sessionmaker(engine, expire_on_commit=False)
