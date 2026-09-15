export type SettingsStackParamList = {
  SettingsHome: {
    accessToken: string;
    userEmail: string;
    userName: string;
  };
  CameraConnectionForm: {
    accessToken: string;
    userEmail: string;
    userName: string;
  };
  CameraLiveView: {
    cameraName: string;
    protocol: 'agent-mjpeg' | 'hls' | 'local-webview';
    url: string;
    accessToken?: string;
    cameraId?: string;
    workspaceId?: string;
  };
};
