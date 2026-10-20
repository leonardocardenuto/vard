-- Execute esta migration antes de habilitar o histórico de disponibilidade.
-- O histórico começa nas primeiras verificações; dados passados não são estimados.
CREATE TABLE IF NOT EXISTS camera_availability_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id uuid NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('online', 'offline')),
    checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_camera_availability_checks_camera_time
    ON camera_availability_checks (camera_id, checked_at);
