import {
  ApiRequestError,
  WorkspaceResponse,
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
  const workspace = workspaces[0];

  if (!workspace) {
    throw new ApiRequestError('Crie um workspace antes de adicionar cameras.');
  }

  return workspace;
}
