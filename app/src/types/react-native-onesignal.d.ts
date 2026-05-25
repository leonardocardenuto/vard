declare module 'react-native-onesignal' {
  export const OneSignal: {
    initialize: (appId: string) => void;
    login: (userId: string) => void;
    Notifications: {
      requestPermission: (fallbackToSettings?: boolean) => Promise<boolean>;
    };
    User: {
      pushSubscription: {
        getIdAsync: () => Promise<string | null>;
      };
    };
  };
}
