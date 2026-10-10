from __future__ import annotations

from fastapi.testclient import TestClient


DEFAULT_PASSWORD = "StrongPassword123!"


def register_user(
    client: TestClient,
    email: str,
    *,
    full_name: str | None = None,
    password: str = DEFAULT_PASSWORD,
) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_workspace(
    client: TestClient,
    token: str,
    *,
    name: str = "Casa Teste",
    slug: str = "casa-teste",
) -> dict:
    response = client.post(
        "/workspaces",
        headers=auth_headers(token),
        json={"name": name, "slug": slug, "timezone": "America/Sao_Paulo"},
    )
    assert response.status_code == 201, response.text
    return response.json()
