from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.core.security import verify_password
from api.models import AppUser, PasswordResetCode, UserCredential
from tests.api.helpers import DEFAULT_PASSWORD, auth_headers, register_user


def test_healthcheck_is_public(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_login_and_me_persist_credentials(client, db_session: Session):
    token = register_user(client, "Owner@Example.com", full_name="Owner Test")

    me = client.get("/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"
    assert me.json()["full_name"] == "Owner Test"

    user = db_session.scalar(
        select(AppUser).where(func.lower(AppUser.email) == "owner@example.com")
    )
    assert user is not None
    credential = db_session.get(UserCredential, user.id)
    assert credential is not None
    assert credential.password_hash != DEFAULT_PASSWORD
    assert verify_password(DEFAULT_PASSWORD, credential.password_hash)

    duplicate = client.post(
        "/auth/register",
        json={"email": "OWNER@example.com", "password": DEFAULT_PASSWORD},
    )
    assert duplicate.status_code == 409

    wrong_password = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "WrongPassword123!"},
    )
    assert wrong_password.status_code == 401

    login = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": DEFAULT_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_protected_endpoint_rejects_missing_and_invalid_tokens(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth_headers("not-a-jwt")).status_code == 401


def test_me_profile_update_persists_profile_fields(client, db_session: Session):
    token = register_user(client, "profile@example.com", full_name="Profile Test")

    response = client.patch(
        "/auth/me",
        headers=auth_headers(token),
        json={
            "full_name": "Perfil Atualizado",
            "phone": "+55 11 99999-9999",
            "avatar_url": "data:image/png;base64,ZmFrZS1pbWFnZQ==",
            "birth_date": "1990-01-15",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Perfil Atualizado"
    assert body["phone"] == "+55 11 99999-9999"
    assert body["avatar_url"].startswith("data:image/png;base64,")
    assert body["birth_date"] == "1990-01-15"

    user = db_session.scalar(select(AppUser).where(AppUser.email == "profile@example.com"))
    assert user is not None
    assert user.full_name == "Perfil Atualizado"
    assert user.phone == "+55 11 99999-9999"
    assert user.avatar_url == "data:image/png;base64,ZmFrZS1pbWFnZQ=="


def test_me_password_change_requires_current_password_and_updates_login(client, db_session: Session):
    token = register_user(client, "password-change@example.com", full_name="Password Test")
    user = db_session.scalar(select(AppUser).where(AppUser.email == "password-change@example.com"))
    assert user is not None

    invalid = client.post(
        "/auth/me/password",
        headers=auth_headers(token),
        json={"current_password": "WrongPassword123!", "new_password": "NewPassword123!"},
    )
    assert invalid.status_code == 400

    response = client.post(
        "/auth/me/password",
        headers=auth_headers(token),
        json={"current_password": DEFAULT_PASSWORD, "new_password": "NewPassword123!"},
    )
    assert response.status_code == 200, response.text

    old_login = client.post(
        "/auth/login",
        json={"email": "password-change@example.com", "password": DEFAULT_PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": "password-change@example.com", "password": "NewPassword123!"},
    )
    assert new_login.status_code == 200


def test_delete_me_removes_user_and_invalidates_token(client, db_session: Session):
    token = register_user(client, "delete-me@example.com", full_name="Delete Me")

    response = client.delete("/auth/me", headers=auth_headers(token))
    assert response.status_code == 200, response.text

    me = client.get("/auth/me", headers=auth_headers(token))
    assert me.status_code == 401

    assert db_session.scalar(select(AppUser).where(AppUser.email == "delete-me@example.com")) is None


def test_password_reset_changes_credentials_without_disclosing_unknown_emails(
    client,
    db_session: Session,
    monkeypatch,
):
    email = "reset@example.com"
    new_password = "NewPassword123!"
    register_user(client, email)

    delivered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "api.routers.auth.send_reset_code",
        lambda recipient, code: delivered.append((recipient, code)),
    )

    unknown = client.post("/auth/forgot-password", json={"email": "unknown@example.com"})
    requested = client.post("/auth/forgot-password", json={"email": email})

    assert unknown.status_code == 200
    assert requested.status_code == 200
    assert delivered and delivered[0][0] == email

    code = delivered[0][1]
    invalid = client.post(
        "/auth/reset-password",
        json={"email": email, "code": "000000", "new_password": new_password},
    )
    assert invalid.status_code == 400

    reset = client.post(
        "/auth/reset-password",
        json={"email": email, "code": code, "new_password": new_password},
    )
    assert reset.status_code == 200

    login = client.post(
        "/auth/login",
        json={"email": email, "password": new_password},
    )
    assert login.status_code == 200

    user = db_session.scalar(select(AppUser).where(AppUser.email == email))
    assert user is not None
    assert db_session.scalar(
        select(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
    ) is None
