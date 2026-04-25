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
    protocol: 'hls' | 'local-webview';
    url: string;
  };
};
