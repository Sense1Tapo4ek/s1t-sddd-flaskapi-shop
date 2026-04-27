from dishka import Provider, Scope, provide

from access.app import (
    ChangePasswordUseCase,
    IAdminRepo,
    LoginUseCase,
    ResetPasswordUseCase,
    GenerateRecoveryCodeUseCase,
    VerifyRecoveryCodeUseCase,
)
from access.app.runtime_permissions import RuntimePermissionProvider
from access.config import AccessConfig
from access.ports.driven.sql_user_repo import SqlUserRepo
from access.ports.driving import AccessFacade
from system.app.interfaces.i_settings_repo import ISettingsRepo


class AccessProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AccessConfig:
        return AccessConfig()

    # Driven
    user_repo = provide(SqlUserRepo, provides=IAdminRepo)

    # Use Cases
    @provide
    def login_uc(self, repo: IAdminRepo, config: AccessConfig) -> LoginUseCase:
        return LoginUseCase(_repo=repo, _config=config)

    change_pw_uc = provide(ChangePasswordUseCase)
    reset_pd_uc = provide(ResetPasswordUseCase)
    generate_code_uc = provide(GenerateRecoveryCodeUseCase)
    @provide
    def runtime_permission_provider(
        self,
        settings_repo: ISettingsRepo,
    ) -> RuntimePermissionProvider:
        return RuntimePermissionProvider(_settings_repo=settings_repo)

    @provide
    def verify_code_uc(self, repo: IAdminRepo, config: AccessConfig) -> VerifyRecoveryCodeUseCase:
        return VerifyRecoveryCodeUseCase(_repo=repo, _config=config)

    # Facade
    facade = provide(AccessFacade)
