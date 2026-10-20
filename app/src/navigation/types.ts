import type { WorkspaceStackParamList } from '../views/workspace/types/workspace';

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
        screen?: keyof AppTabParamList;
        params?: AppTabParamList['Alerts'] | AppTabParamList['Workspace'];
        userAvatarUrl?: string | null;
        userEmail: string;
        userPhone?: string | null;
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
        userPhone?: string | null;
        userName?: string;
      }
    | undefined;
  Home:
    | {
        accessToken: string;
        userAvatarUrl?: string | null;
        userEmail: string;
        userPhone?: string | null;
        userName?: string;
      }
    | undefined;
  Workspace:
    | {
        accessToken: string;
        screen?: keyof WorkspaceStackParamList;
        params?: WorkspaceStackParamList['CameraOccurrences'] | WorkspaceStackParamList['WorkspaceOccurrences'];
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
        userPhone?: string | null;
        userName?: string;
      }
    | undefined;
};
