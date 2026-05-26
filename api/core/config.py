from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Vard API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    app_base_url: str = "http://localhost:8000"
    cors_allow_origins: str = Field(
        "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006,http://127.0.0.1:19006",
        alias="CORS_ALLOW_ORIGINS",
    )
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")

    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expires_minutes: int = Field(30, alias="JWT_ACCESS_TOKEN_EXPIRES_MINUTES")

    sendgrid_api_key: str | None = Field(default=None, alias="SENDGRID_API_KEY")
    sendgrid_from_email: str | None = Field(default=None, alias="SENDGRID_FROM_EMAIL")

    onesignal_app_id: str | None = Field(default=None, alias="ONESIGNAL_APP_ID")
    onesignal_api_key: str | None = Field(default=None, alias="ONESIGNAL_API_KEY")

    fall_monitor_enabled: bool = Field(False, alias="FALL_MONITOR_ENABLED")
    fall_monitor_checkpoint: str = Field(
        "fall_detection/models/vard_fall_window_production.pkl",
        alias="FALL_MONITOR_CHECKPOINT",
    )
    fall_monitor_device: str | None = Field(default=None, alias="FALL_MONITOR_DEVICE")
    fall_monitor_reload_seconds: float = Field(15.0, alias="FALL_MONITOR_RELOAD_SECONDS")
    fall_monitor_num_frames: int = Field(16, alias="FALL_MONITOR_NUM_FRAMES")
    fall_monitor_sample_fps: float = Field(6.0, alias="FALL_MONITOR_SAMPLE_FPS")
    fall_monitor_capture_fps: float = Field(0.0, alias="FALL_MONITOR_CAPTURE_FPS")
    fall_monitor_stride_seconds: float = Field(1.0, alias="FALL_MONITOR_STRIDE_SECONDS")
    fall_monitor_threshold: float = Field(0.75, alias="FALL_MONITOR_THRESHOLD")
    fall_monitor_smoothing_window: int = Field(5, alias="FALL_MONITOR_SMOOTHING_WINDOW")
    fall_monitor_min_consecutive_hits: int = Field(2, alias="FALL_MONITOR_MIN_CONSECUTIVE_HITS")
    fall_monitor_buffer_seconds: float = Field(8.0, alias="FALL_MONITOR_BUFFER_SECONDS")
    fall_monitor_freeze_seconds: float = Field(300.0, alias="FALL_MONITOR_FREEZE_SECONDS")
    fall_monitor_show_preview: bool = Field(False, alias="FALL_MONITOR_SHOW_PREVIEW")
    fall_monitor_alert_cooldown_seconds: float = Field(60.0, alias="FALL_MONITOR_ALERT_COOLDOWN_SECONDS")
    fall_monitor_restart_backoff_seconds: float = Field(30.0, alias="FALL_MONITOR_RESTART_BACKOFF_SECONDS")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
