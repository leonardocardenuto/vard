import { WorkspaceResponse } from '../../../lib/api';

export type WorkspaceStackParamList = {
  WorkspacesList: {
    accessToken: string;
    userEmail: string;
    userName?: string;
  };
  WorkspaceDetails: {
    accessToken: string;
    workspace: WorkspaceResponse;
  };
  AddWorkspace: {
    accessToken: string;
    userEmail: string;
    userName?: string;
  };
};
