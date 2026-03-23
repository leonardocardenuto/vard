# Vard FastAPI

API base com autenticacao JWT simples, CRUDs e convites por SendGrid.

## Setup

1. Crie e ative um ambiente virtual.
2. Instale dependências:

```bash
pip install -r requirements-api.txt
```

3. Configure o `.env`:

```bash
cp .env.example .env
```

4. Rode migrations SQL:

```bash
python -m scripts.migrate
```

5. Suba a API:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET/PATCH/DELETE /users/{user_id}`
- `GET/POST /workspaces`
- `GET/PATCH/DELETE /workspaces/{workspace_id}`
- `GET/POST /cameras`
- `GET/PATCH/DELETE /cameras/{camera_id}`
- `GET/POST /invites`
- `GET /invites/{invite_id}`
- `POST /invites/accept`
- `POST /invites/{invite_id}/revoke`
- `GET/POST /notifications`
- `GET/PATCH/DELETE /notifications/{notification_id}`

Swagger: `http://localhost:8000/docs`
