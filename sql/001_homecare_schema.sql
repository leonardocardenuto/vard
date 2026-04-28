BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Family members / users
CREATE TABLE IF NOT EXISTS app_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    full_name text,
    phone text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT app_users_email_at CHECK (position('@' in email) > 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_app_users_email_lower
ON app_users (lower(email));

-- One workspace per family/home, with many members and many cameras
CREATE TABLE IF NOT EXISTS workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    timezone text NOT NULL DEFAULT 'UTC',
    created_by_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'caregiver', 'viewer')),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending', 'removed')),
    invited_by_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    joined_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user_id
ON workspace_members (user_id);

-- Email invites to join a workspace
CREATE TABLE IF NOT EXISTS workspace_invites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email text NOT NULL,
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'caregiver', 'viewer')),
    invited_by_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    token text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired', 'revoked')),
    expires_at timestamptz NOT NULL,
    accepted_by_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    accepted_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspace_invites_workspace_status
ON workspace_invites (workspace_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_invites_pending_email
ON workspace_invites (workspace_id, lower(email))
WHERE status = 'pending';

-- IP cameras (many cameras per workspace)
CREATE TABLE IF NOT EXISTS cameras (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name text NOT NULL,
    external_id text,
    connection_type text NOT NULL DEFAULT 'rtsp' CHECK (connection_type IN ('rtsp', 'onvif', 'hls', 'webrtc', 'other')),
    stream_url text NOT NULL,
    status text NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'error', 'disabled')),
    is_active boolean NOT NULL DEFAULT true,
    last_seen_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name),
    UNIQUE (workspace_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_cameras_workspace_status
ON cameras (workspace_id, status);

-- Notification channels per member
CREATE TABLE IF NOT EXISTS notification_channels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    channel_type text NOT NULL CHECK (channel_type IN ('email', 'sms', 'push', 'webhook')),
    target text NOT NULL,
    is_verified boolean NOT NULL DEFAULT false,
    is_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id, channel_type, target)
);

CREATE INDEX IF NOT EXISTS idx_notification_channels_user
ON notification_channels (user_id);

-- Notification events (ex: fall detected)
CREATE TABLE IF NOT EXISTS notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    camera_id uuid REFERENCES cameras(id) ON DELETE SET NULL,
    notification_type text NOT NULL,
    severity text NOT NULL DEFAULT 'high' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    title text NOT NULL,
    body text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text NOT NULL DEFAULT 'system',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_workspace_created_at
ON notifications (workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_camera_created_at
ON notifications (camera_id, created_at DESC);

-- Delivery status of each notification by channel/user
CREATE TABLE IF NOT EXISTS notification_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id uuid NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
    user_id uuid REFERENCES app_users(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'failed', 'read')),
    error_message text,
    sent_at timestamptz,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (notification_id, channel_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_notification_deliveries_status_created_at
ON notification_deliveries (status, created_at DESC);

COMMIT;
