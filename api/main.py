from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.cache.model_hooks import register_cache_invalidation_hooks
from api.core.config import get_settings
from api.routers import auth, camera_streams, cameras, invites, notifications, users, workspaces
from api.services.camera_streams import STREAMS_ROOT

settings = get_settings()
register_cache_invalidation_hooks()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
