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
    fallAlert?: WorkspaceFallAlert;
  };
  AddWorkspace: {
    accessToken: string;
    userEmail: string;
    userName?: string;
  };
  EditWorkspace: {
    accessToken: string;
    userEmail: string;
    userName?: string;
    workspace: WorkspaceResponse;
  };
  CameraLiveView: {
    cameraName: string;
    protocol: 'hls' | 'local-webview';
    url: string;
  };
};

export type WorkspaceFallAlert = {
  active?: boolean;
  occurredAt?: string;
  roomName?: string;
  ambulancePhoneNumber?: string;
};
