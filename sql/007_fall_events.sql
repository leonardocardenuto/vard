-- O instante exato de uma queda fica somente no campo cifrado. Não adicione
-- uma coluna de data em texto claro a esta tabela.
CREATE TABLE IF NOT EXISTS fall_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    camera_id UUID REFERENCES cameras(id) ON DELETE SET NULL,
    notification_id UUID UNIQUE REFERENCES notifications(id) ON DELETE SET NULL,
    occurred_at_encrypted TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fall_events_workspace ON fall_events(workspace_id);
