import {
  WorkspaceResponse,
  buildDefaultWorkspaceSlug,
  createWorkspace,
  listWorkspaces,
} from '../../../lib/api';

type ResolveWorkspaceParams = {
  accessToken: string;
  userEmail: string;
  userName: string;
};

export async function resolvePrimaryWorkspace({
  accessToken,
  userEmail,
  userName,
}: ResolveWorkspaceParams): Promise<WorkspaceResponse> {
  const workspaces = await listWorkspaces(accessToken);

  return (
    workspaces[0] ??
    createWorkspace(accessToken, {
      name: `Casa de ${userName}`,
      slug: buildDefaultWorkspaceSlug(userEmail || userName),
      timezone: 'America/Sao_Paulo',
    })
  );
}
