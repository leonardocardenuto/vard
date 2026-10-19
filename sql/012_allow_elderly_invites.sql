ALTER TABLE workspace_invites DROP CONSTRAINT IF EXISTS workspace_invites_role_check;
ALTER TABLE workspace_invites ADD CONSTRAINT workspace_invites_role_check
CHECK (role IN ('owner', 'admin', 'member', 'caregiver', 'viewer', 'elderly'));
