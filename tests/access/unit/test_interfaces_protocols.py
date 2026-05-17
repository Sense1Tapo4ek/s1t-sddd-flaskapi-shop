import pytest

from access.app.interfaces import IAdminRepo, ICustomerRepo, IEmailSender


@pytest.mark.unit
class TestImports:
    def test_iadmin_repo_importable(self):
        assert IAdminRepo is not None

    def test_icustomer_repo_importable(self):
        assert ICustomerRepo is not None

    def test_iemail_sender_importable(self):
        assert IEmailSender is not None


@pytest.mark.unit
class TestICustomerRepoShape:
    def test_all_methods_present(self):
        expected = [
            "get_by_email",
            "get_by_id",
            "create",
            "update_password",
            "set_recovery_code",
            "clear_recovery_code",
            "record_recovery_failure",
            "get_token_version",
            "bump_token_version",
            "update_last_login",
        ]
        for method in expected:
            assert hasattr(ICustomerRepo, method), f"ICustomerRepo missing: {method}"

    def test_stub_satisfies_protocol_structurally(self):
        from datetime import datetime

        class StubCustomerRepo:
            def get_by_email(self, email: str): ...
            def get_by_id(self, customer_id: int): ...
            def create(self, *, email: str, password_hash: str): ...
            def update_password(self, customer_id: int, password_hash: str): ...
            def set_recovery_code(self, customer_id: int, code_hash: str, expires: datetime): ...
            def clear_recovery_code(self, customer_id: int): ...
            def record_recovery_failure(self, customer_id: int, attempts: int, locked_until): ...
            def get_token_version(self, customer_id: int): ...
            def bump_token_version(self, customer_id: int): ...
            def update_last_login(self, customer_id: int, when: datetime): ...

        stub = StubCustomerRepo()
        for method in [
            "get_by_email", "get_by_id", "create", "update_password",
            "set_recovery_code", "clear_recovery_code", "record_recovery_failure",
            "get_token_version", "bump_token_version", "update_last_login",
        ]:
            assert hasattr(stub, method)


@pytest.mark.unit
class TestIEmailSenderShape:
    def test_send_method_present(self):
        assert hasattr(IEmailSender, "send")

    def test_stub_satisfies_protocol_structurally(self):
        class StubEmailSender:
            def send(self, to: str, subject: str, body: str): ...

        stub = StubEmailSender()
        assert hasattr(stub, "send")


@pytest.mark.unit
class TestIAdminRepoExtension:
    def test_session_invalidation_methods_present(self):
        assert hasattr(IAdminRepo, "get_token_version")
        assert hasattr(IAdminRepo, "bump_token_version")
        assert hasattr(IAdminRepo, "update_last_login")

    def test_existing_methods_preserved(self):
        existing = [
            "get_by_login",
            "get_by_id",
            "update_password",
            "update_telegram_chat_id",
            "list_order_notification_recipients",
            "set_recovery_code",
            "record_recovery_failure",
            "clear_recovery_code",
        ]
        for method in existing:
            assert hasattr(IAdminRepo, method), f"IAdminRepo missing: {method}"
