from dishka import Provider, Scope, provide

from access.app import (
    ChangePasswordUseCase,
    IAdminRepo,
    ICustomerRepo,
    IEmailSender,
    LoginUseCase,
    RegisterCustomerUseCase,
    ResetPasswordUseCase,
    GenerateRecoveryCodeUseCase,
    SendCustomerRecoveryCodeUseCase,
    VerifyCustomerRecoveryUseCase,
    VerifyRecoveryCodeUseCase,
)
from access.app.runtime_permissions import RuntimePermissionProvider
from access.app.services.session_cache import SessionCache
from access.config import AccessConfig
from access.ports.driven.sql_customer_repo import SqlCustomerRepo
from access.ports.driven.sql_user_repo import SqlUserRepo
from access.ports.driving import AccessFacade, AdminFacade, CustomerFacade
from shared.adapters.driven.email.logging_email_sender import LoggingEmailSender
from shared.config import EmailConfig
from system.app.interfaces.i_settings_repo import ISettingsRepo


class AccessProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AccessConfig:
        return AccessConfig()

    @provide
    def email_config(self) -> EmailConfig:
        return EmailConfig()

    # Driven
    user_repo = provide(SqlUserRepo, provides=IAdminRepo)
    customer_repo = provide(SqlCustomerRepo, provides=ICustomerRepo)

    @provide
    def email_sender(self, email_config: EmailConfig) -> IEmailSender:
        # Phase 10 will wire SMTP; for now use logging sender
        return LoggingEmailSender(_app_env="dev")

    @provide
    def session_cache(self) -> SessionCache:
        return SessionCache()

    # Use Cases
    @provide
    def login_uc(
        self,
        admin_repo: IAdminRepo,
        customer_repo: ICustomerRepo,
        config: AccessConfig,
    ) -> LoginUseCase:
        return LoginUseCase(
            _admin_repo=admin_repo,
            _customer_repo=customer_repo,
            _config=config,
        )

    change_pw_uc = provide(ChangePasswordUseCase)
    reset_pd_uc = provide(ResetPasswordUseCase)
    generate_code_uc = provide(GenerateRecoveryCodeUseCase)

    @provide
    def verify_code_uc(
        self,
        repo: IAdminRepo,
        config: AccessConfig,
    ) -> VerifyRecoveryCodeUseCase:
        return VerifyRecoveryCodeUseCase(_repo=repo, _config=config)

    @provide
    def register_customer_uc(
        self,
        repo: ICustomerRepo,
        config: AccessConfig,
    ) -> RegisterCustomerUseCase:
        return RegisterCustomerUseCase(_repo=repo, _config=config)

    @provide
    def send_recovery_code_uc(
        self,
        repo: ICustomerRepo,
        email_sender: IEmailSender,
        config: AccessConfig,
    ) -> SendCustomerRecoveryCodeUseCase:
        return SendCustomerRecoveryCodeUseCase(
            _repo=repo,
            _email_sender=email_sender,
            _config=config,
        )

    @provide
    def verify_customer_recovery_uc(
        self,
        repo: ICustomerRepo,
        config: AccessConfig,
        cache: SessionCache,
    ) -> VerifyCustomerRecoveryUseCase:
        return VerifyCustomerRecoveryUseCase(
            _repo=repo,
            _config=config,
            _cache=cache,
        )

    @provide
    def runtime_permission_provider(
        self,
        settings_repo: ISettingsRepo,
    ) -> RuntimePermissionProvider:
        return RuntimePermissionProvider(_settings_repo=settings_repo)

    # Facades
    @provide
    def access_facade(self, login_uc: LoginUseCase) -> AccessFacade:
        return AccessFacade(_login_uc=login_uc)

    @provide
    def admin_facade(
        self,
        repo: IAdminRepo,
        change_pw_uc: ChangePasswordUseCase,
        reset_pd_uc: ResetPasswordUseCase,
        generate_code_uc: GenerateRecoveryCodeUseCase,
        verify_code_uc: VerifyRecoveryCodeUseCase,
    ) -> AdminFacade:
        return AdminFacade(
            _repo=repo,
            _change_password_uc=change_pw_uc,
            _reset_password_uc=reset_pd_uc,
            _generate_code_uc=generate_code_uc,
            _verify_code_uc=verify_code_uc,
        )

    @provide
    def customer_facade(
        self,
        repo: ICustomerRepo,
        register_uc: RegisterCustomerUseCase,
        send_code_uc: SendCustomerRecoveryCodeUseCase,
        verify_uc: VerifyCustomerRecoveryUseCase,
    ) -> CustomerFacade:
        return CustomerFacade(
            _repo=repo,
            _register_uc=register_uc,
            _send_code_uc=send_code_uc,
            _verify_uc=verify_uc,
        )
