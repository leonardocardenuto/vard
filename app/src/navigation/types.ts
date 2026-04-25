export type RootStackParamList = {
  Auth: undefined;
  AppTabs:
    | {
        accessToken: string;
        userEmail: string;
        userName?: string;
      }
    | undefined;
};

export type AppTabParamList = {
  Home:
    | {
        accessToken: string;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Workspace:
    | {
        accessToken: string;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Insights:
    | {
        accessToken: string;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Settings:
    | {
        accessToken: string;
        userEmail: string;
        userName?: string;
      }
    | undefined;
};
