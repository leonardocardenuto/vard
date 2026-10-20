import { useCallback, useEffect, useRef, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import * as NativeSplashScreen from 'expo-splash-screen';
import { ActivityIndicator, AppState, DeviceEventEmitter, Pressable, Text, TextInput, View } from 'react-native';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { BottomNavigationBar } from './src/components/BottomNavigationBar';
import { AppTabParamList, RootStackParamList } from './src/navigation/types';
import { AuthScreen } from './src/views/auth/pages/AuthScreen';
import { Home } from './src/views/home/pages/Home.tsx';
import { Insights } from './src/views/insights/pages/Insights';
import { Settings } from './src/views/settings/pages/Settings';
import Workspaces from './src/views/workspace/pages/workspaces';
import { Header } from './src/components/Header';
import { initializeOneSignal } from './src/lib/onesignal';
import { Alerts } from './src/views/alerts/pages/Alerts';
import { AcceptInviteScreen } from './src/views/invites/AcceptInviteScreen';
import { getMobileMonitorProfile, MobileMonitorProfile } from './src/lib/api';
import { ElderlyMonitorScreen } from './src/views/elderly/ElderlyMonitorScreen';
import { clearSession } from './src/lib/session';
import { monitorStatus, stopMobileFallMonitor } from './src/lib/mobileFallMonitor';
import { VARD_NAVIGATION_THEME, VARD_PAPER_THEME } from './src/theme/vardTheme';

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tabs = createBottomTabNavigator<AppTabParamList>();
let defaultFontsApplied = false;

type AppTabsProps = NativeStackScreenProps<RootStackParamList, 'AppTabs'>;

function AppTabs({ navigation: stackNavigation, route }: AppTabsProps) {
  const [monitorProfile, setMonitorProfile] = useState<MobileMonitorProfile | null>(null);
  const [profileError, setProfileError] = useState('');
  const profileRequestVersion = useRef(0);
  const userName = route.params?.userName;
  const accessToken = route.params?.accessToken ?? '';
  const userAvatarUrl = route.params?.userAvatarUrl;
  const userEmail = route.params?.userEmail ?? '';
  const userPhone = route.params?.userPhone ?? null;
  const refreshProfile = useCallback(async () => {
    const version = ++profileRequestVersion.current;
    try {
      const profile = await getMobileMonitorProfile(accessToken);
      if (version !== profileRequestVersion.current) return;
      if (!profile.restricted) {
        const monitor = await monitorStatus();
        if (monitor?.enabled || monitor?.running) await stopMobileFallMonitor();
      }
      if (version !== profileRequestVersion.current) return;
      setMonitorProfile(profile);
      setProfileError('');
    } catch {
      if (version !== profileRequestVersion.current) return;
      setProfileError('Não foi possível verificar seu perfil. Entre novamente se a sessão expirou.');
    }
  }, [accessToken]);
  useEffect(() => {
    void refreshProfile();
    const membershipListener = DeviceEventEmitter.addListener('vard.membership.changed', () => void refreshProfile());
    const appListener = AppState.addEventListener('change', (state) => { if (state === 'active') void refreshProfile(); });
    return () => { profileRequestVersion.current += 1; membershipListener.remove(); appListener.remove(); };
  }, [refreshProfile]);
  const handleLogout = () => {
    stackNavigation.reset({
      index: 0,
      routes: [{ name: 'Auth' }],
    });
  };

  if (!monitorProfile) {
    return <View style={{ flex: 1, justifyContent: 'center', padding: 24, gap: 20 }}>
      {profileError ? <>
        <Text>{profileError}</Text>
        <Pressable onPress={() => void refreshProfile()}><Text>Tentar novamente</Text></Pressable>
        <Pressable onPress={() => void clearSession().then(handleLogout)}><Text>Sair da conta</Text></Pressable>
      </> : <ActivityIndicator color="#00B9BB" />}
    </View>;
  }
  if (monitorProfile.restricted) {
    return <ElderlyMonitorScreen accessToken={accessToken} profile={monitorProfile} onLogout={handleLogout} />;
  }

  return (
    <Tabs.Navigator
      screenOptions={{
        headerShown: true,
        animation: 'none',
        header: ({ navigation: tabNavigation }) => (
          <Header
            avatarUrl={userAvatarUrl}
            profileFunction={() => {
              tabNavigation.navigate('Settings', {
                accessToken, userAvatarUrl, userEmail, userName, userPhone,
              });
            }}
          />
        ),
      }}
      tabBar={(props) => <BottomNavigationBar {...props} />}
    >
      <Tabs.Screen
        name="Home"
        component={Home}
        initialParams={{ accessToken, userAvatarUrl, userEmail, userName }}
      />
      <Tabs.Screen
        name="Alerts"
        component={Alerts}
        initialParams={{ accessToken, userAvatarUrl, userEmail, userName }}
      />
      <Tabs.Screen
        name="Workspace"
        component={Workspaces}
        initialParams={{ accessToken, userAvatarUrl, userEmail, userName }}
      />
      <Tabs.Screen
        name="Insights"
        component={Insights}
        initialParams={{ accessToken, userAvatarUrl, userEmail, userName }}
      />
      <Tabs.Screen
        name="Settings"
        initialParams={{ accessToken, userAvatarUrl, userEmail, userPhone, userName }}
      >
        {() => <Settings onLogout={handleLogout} />}
      </Tabs.Screen>
    </Tabs.Navigator>
  );
}

void NativeSplashScreen.preventAutoHideAsync().catch(() => {});

export default function App() {
  const [fontsLoaded, fontError] = useFonts({
    'Poppins-Regular': require('./assets/fonts/Poppins-Regular.ttf'),
    'Poppins-Medium': require('./assets/fonts/Poppins-Medium.ttf'),
    'Poppins-SemiBold': require('./assets/fonts/Poppins-SemiBold.ttf'),
    'Poppins-Bold': require('./assets/fonts/Poppins-Bold.ttf'),
    'Poppins-ExtraBold': require('./assets/fonts/Poppins-ExtraBold.ttf'),
    'Poppins-Black': require('./assets/fonts/Poppins-Black.ttf'),
  });

  useEffect(() => {
    void initializeOneSignal();

  }, []);

  useEffect(() => {
    if (fontsLoaded || fontError) void NativeSplashScreen.hideAsync();
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) {
    return null;
  }

  applyDefaultPoppinsFont();

  return (
    <SafeAreaProvider>
      <PaperProvider theme={VARD_PAPER_THEME}>
        <NavigationContainer theme={VARD_NAVIGATION_THEME}>
          <Stack.Navigator screenOptions={{ headerShown: false, animation: 'none' }}>
            <Stack.Screen name="Auth" component={AuthScreen} />
            <Stack.Screen name="AppTabs" component={AppTabs} />
            <Stack.Screen name="AcceptInvite" component={AcceptInviteScreen} />
          </Stack.Navigator>
        </NavigationContainer>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

function applyDefaultPoppinsFont() {
  if (defaultFontsApplied) {
    return;
  }

  defaultFontsApplied = true;
  const textWithDefaults = Text as typeof Text & { defaultProps?: { style?: unknown } };
  const inputWithDefaults = TextInput as typeof TextInput & { defaultProps?: { style?: unknown } };

  textWithDefaults.defaultProps = textWithDefaults.defaultProps ?? {};
  inputWithDefaults.defaultProps = inputWithDefaults.defaultProps ?? {};
  textWithDefaults.defaultProps.style = [{ fontFamily: 'Poppins-Regular' }, textWithDefaults.defaultProps.style];
  inputWithDefaults.defaultProps.style = [
    { fontFamily: 'Poppins-Regular' },
    inputWithDefaults.defaultProps.style,
  ];
}
