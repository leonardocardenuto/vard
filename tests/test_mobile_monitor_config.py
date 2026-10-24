import pytest
from pydantic import ValidationError

from api.mobile_monitor_config import MobileMonitorConfig


@pytest.mark.parametrize('change', [
    {'impact_g': 0}, {'impact_g': float('inf')}, {'free_fall_g': 1},
    {'free_fall_window_ms': -1}, {'stillness_duration_ms': 8000},
    {'confirmation_timeout_ms': 0}, {'posture_angle_degrees': 181},
    {'gravity_alpha': 1}, {'gravity_max_g': 2.5},
])
def test_invalid_detector_parameters_are_rejected(change):
    with pytest.raises(ValidationError):
        MobileMonitorConfig(**change)
