from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


DEFAULT_TEST_DATABASE_URL = "postgresql://vard_test:vard_test@127.0.0.1:55433/vard_test"

TEST_NAMES = {
    "test_healthcheck_is_public": "Healthcheck público",
    "test_register_login_and_me_persist_credentials": "Cadastro, login e persistência de credenciais",
    "test_protected_endpoint_rejects_missing_and_invalid_tokens": "Proteção contra tokens ausentes ou inválidos",
    "test_password_reset_changes_credentials_without_disclosing_unknown_emails": "Recuperação e redefinição de senha",
    "test_workspace_creation_creates_owner_membership_and_isolates_access": "Criação e isolamento de workspaces",
    "test_camera_permissions_and_crud_persist_in_database": "Permissões e persistência de câmeras",
    "test_invite_can_only_be_accepted_by_recipient": "Segurança no aceite de convites",
    "test_notification_creation_lists_for_members_and_persists": "Criação e persistência de notificações",
    "test_deleting_workspace_cascades_related_database_rows": "Exclusão em cascata no banco",
}


def database_label(database_url: str) -> str:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "host desconhecido"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "banco desconhecido"
    return f"{host}{port}/{database}"


def check_database(database_url: str) -> bool:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()


@dataclass
class PortugueseReporter:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)

    @staticmethod
    def test_name(nodeid: str) -> str:
        function_name = nodeid.rsplit("::", 1)[-1]
        return TEST_NAMES.get(function_name, function_name.replace("_", " ").capitalize())

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "setup" and report.skipped:
            self.skipped += 1
            print(f"  IGNORADO  {self.test_name(report.nodeid)}")
            return
        if report.when == "setup" and report.failed:
            self.failed += 1
            self.failures.append(report.longreprtext)
            print(f"  FALHOU    {self.test_name(report.nodeid)}")
            return
        if report.when != "call":
            return

        duration = f"{report.duration * 1000:.0f} ms"
        if report.passed:
            self.passed += 1
            print(f"  OK        {self.test_name(report.nodeid)} ({duration})")
        elif report.failed:
            self.failed += 1
            self.failures.append(report.longreprtext)
            print(f"  FALHOU    {self.test_name(report.nodeid)} ({duration})")


def main() -> int:
    database_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    os.environ["TEST_DATABASE_URL"] = database_url
    os.environ["APP_ENV"] = "test"
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

    print("\nTESTES DE INTEGRAÇÃO DA API VARD")
    print("=" * 36)
    print(f"Banco de teste: {database_label(database_url)}")

    if not check_database(database_url):
        print("Status: não foi possível conectar ao banco de teste.")
        print("Inicie o container PostgreSQL de testes e tente novamente.")
        return 2

    print("Status: banco conectado\n")
    reporter = PortugueseReporter()
    exit_code = pytest.main(
        ["tests/api", "-p", "no:terminal"],
        plugins=[reporter],
    )

    if reporter.failures:
        print("\nDETALHES DAS FALHAS")
        print("=" * 36)
        print("\n\n".join(reporter.failures))

    print("\n" + "=" * 36)
    if exit_code == pytest.ExitCode.OK:
        print(f"RESULTADO: {reporter.passed} TESTES APROVADOS")
    else:
        print(
            "RESULTADO: "
            f"{reporter.passed} aprovados, {reporter.failed} falharam, "
            f"{reporter.skipped} ignorados"
        )
    print("=" * 36)
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
