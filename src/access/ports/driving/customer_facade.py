from dataclasses import dataclass

from access.app import (
    ICustomerRepo,
    RegisterCustomerUseCase,
    SendCustomerRecoveryCodeUseCase,
    VerifyCustomerRecoveryUseCase,
)
from access.domain import Customer, CustomerNotFoundError

from .schemas import (
    CustomerRecoverIn,
    CustomerRegisterIn,
    CustomerVerifyIn,
    LoginOut,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CustomerFacade:
    _repo: ICustomerRepo
    _register_uc: RegisterCustomerUseCase
    _send_code_uc: SendCustomerRecoveryCodeUseCase
    _verify_uc: VerifyCustomerRecoveryUseCase

    def register(
        self,
        schema: CustomerRegisterIn,
        *,
        csrf_token: str | None = None,
    ) -> LoginOut:
        token = self._register_uc(schema.to_command(csrf_token=csrf_token))
        return LoginOut(token=token)

    def send_recovery_code(self, schema: CustomerRecoverIn) -> None:
        self._send_code_uc(schema.to_command())

    def verify_and_reset(
        self,
        schema: CustomerVerifyIn,
        *,
        csrf_token: str | None = None,
    ) -> LoginOut:
        token = self._verify_uc(schema.to_command(csrf_token=csrf_token))
        return LoginOut(token=token)

    def get_customer(self, customer_id: int) -> Customer:
        customer = self._repo.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer
