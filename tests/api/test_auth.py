from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.core.security import verify_password
from api.models import AppUser, UserCredential
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
