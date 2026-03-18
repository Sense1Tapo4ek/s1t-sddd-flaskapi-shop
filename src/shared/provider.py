from typing import Callable
from dishka import Provider, Scope, provide
from sqlalchemy.orm import Session

from shared.adapters.driven import create_session_factory
from shared.config import InfraConfig


class InfraProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> InfraConfig:
        return InfraConfig()

    @provide
    def session_factory(self, config: InfraConfig) -> Callable[[], Session]:
        return create_session_factory(config.database_url)
