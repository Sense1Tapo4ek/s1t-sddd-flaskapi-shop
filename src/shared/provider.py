from typing import Callable
from dishka import Provider, Scope, provide
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from shared.adapters.driven.db.connection import (
    create_db_engine,
    create_session_factory_for_engine,
)
from shared.config import InfraConfig


class InfraProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> InfraConfig:
        return InfraConfig()

    @provide
    def engine(self, config: InfraConfig) -> Engine:
        return create_db_engine(config.database_url)

    @provide
    def session_factory(self, engine: Engine) -> Callable[[], Session]:
        return create_session_factory_for_engine(engine)
