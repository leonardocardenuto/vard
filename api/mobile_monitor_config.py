"""Validated detector parameters stored in mobile_monitor_settings (singleton row 1)."""
from pydantic import BaseModel, Field, model_validator


class MobileMonitorConfig(BaseModel):
    impact_g: float = Field(2.5, ge=1, le=20, allow_inf_nan=False)
    free_fall_g: float = Field(0.6, gt=0, lt=1, allow_inf_nan=False)
    free_fall_window_ms: int = Field(1500, ge=100, le=10000)
    impact_window_ms: int = Field(8000, ge=1000, le=30000)
    stillness_tolerance_g: float = Field(0.18, gt=0, lt=1, allow_inf_nan=False)
    stillness_duration_ms: int = Field(2500, ge=100, le=20000)
    posture_angle_degrees: float = Field(35, gt=0, le=180, allow_inf_nan=False)
    rearm_delay_ms: int = Field(10000, ge=1000, le=60000)
    confirmation_timeout_ms: int = Field(20000, ge=15000, le=120000)
    gravity_min_g: float = Field(0.7, gt=0, lt=1, allow_inf_nan=False)
    gravity_max_g: float = Field(1.3, gt=1, le=3, allow_inf_nan=False)
    gravity_alpha: float = Field(0.9, gt=0, lt=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_windows(self):
        if self.stillness_duration_ms >= self.impact_window_ms:
            raise ValueError("stillness_duration_ms must be shorter than impact_window_ms")
        if self.impact_g <= self.gravity_max_g:
            raise ValueError("impact_g must exceed gravity_max_g")
        return self
