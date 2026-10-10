export type RootStackParamList = {
  Auth:
    | {
        initialStep?: 'landing' | 'email' | 'password' | 'signup';
        pendingInviteToken?: string;
      }
    | undefined;
  AcceptInvite: { token: string };
  AppTabs:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
};

export type AppTabParamList = {
  Alerts:
    | {
        accessToken: string;
        params?: unknown;
        screen?: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Home:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Workspace:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Insights:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
  Settings:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userName?: string;
      }
    | undefined;
};
