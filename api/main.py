from fastapi import FastAPI

from api.core.config import get_settings
from api.routers import auth, cameras, invites, notifications, users, workspaces

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(workspaces.router)
app.include_router(cameras.router)
app.include_router(invites.router)
app.include_router(notifications.router)
