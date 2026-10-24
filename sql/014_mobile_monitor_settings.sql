-- Apply before deploying the API/mobile app. Values preserve existing detector behavior.
CREATE TABLE IF NOT EXISTS mobile_monitor_settings (
    id integer PRIMARY KEY CHECK (id = 1),
    parameters jsonb NOT NULL
);
INSERT INTO mobile_monitor_settings (id, parameters) VALUES (1, '{"impact_g": 2.5, "free_fall_g": 0.6, "free_fall_window_ms": 1500, "impact_window_ms": 8000, "stillness_tolerance_g": 0.18, "stillness_duration_ms": 2500, "posture_angle_degrees": 35, "rearm_delay_ms": 10000, "confirmation_timeout_ms": 20000, "gravity_min_g": 0.7, "gravity_max_g": 1.3, "gravity_alpha": 0.9}'::jsonb) ON CONFLICT (id) DO NOTHING;
