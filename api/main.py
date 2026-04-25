from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.core.config import get_settings
from api.routers import auth, camera_streams, cameras, invites, notifications, users, workspaces
from api.services.camera_streams import STREAMS_ROOT

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.mount("/streams", StaticFiles(directory=STREAMS_ROOT), name="streams")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(camera_streams.router)
app.include_router(users.router)
app.include_router(workspaces.router)
app.include_router(cameras.router)
app.include_router(invites.router)
app.include_router(notifications.router)
