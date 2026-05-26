import { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useFonts } from 'expo-font';
import { Text, TextInput } from 'react-native';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { BottomNavigationBar } from './src/components/BottomNavigationBar';
import { SplashScreen } from './src/components/SplashScreen';
import { AppTabParamList, RootStackParamList } from './src/navigation/types';
import { AuthScreen } from './src/views/auth/pages/AuthScreen';
import { Home } from './src/views/home/pages/Home.tsx';
import { Insights } from './src/views/insights/pages/Insights';
import { Settings } from './src/views/settings/pages/Settings';
import Workspaces from './src/views/workspace/pages/workspaces';
import { Header } from './src/components/Header';
import { initializeOneSignal } from './src/lib/onesignal';
import { Alerts } from './src/views/alerts/pages/Alerts';

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tabs = createBottomTabNavigator<AppTabParamList>();
let defaultFontsApplied = false;

type AppTabsProps = NativeStackScreenProps<RootStackParamList, 'AppTabs'>;

function AppTabs({ navigation: stackNavigation, route }: AppTabsProps) {
  const userName = route.params?.userName;
  const accessToken = route.params?.accessToken ?? '';
  const userAvatarUrl = route.params?.userAvatarUrl;
  const userEmail = route.params?.userEmail ?? '';
  const handleLogout = () => {
    stackNavigation.reset({
      index: 0,
      routes: [{ name: 'Auth' }],
    });
  };

  return (
    <Tabs.Navigator
      screenOptions={{
        headerShown: true,
        animation: 'none',
        header: ({ navigation: tabNavigation }) => (
          <Header
            avatarUrl={userAvatarUrl}
            notificationFunction={() => {
              tabNavigation.navigate('Alerts', {
                accessToken,
                params: { accessToken },
                screen: 'AlertsList',
                userAvatarUrl,
                userEmail,
                userName,
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
        initialParams={{ accessToken, userAvatarUrl, userEmail, userName }}
      >
        {() => <Settings onLogout={handleLogout} />}
      </Tabs.Screen>
    </Tabs.Navigator>
  );
}

export default function App() {
  const [isSplashVisible, setIsSplashVisible] = useState(true);
  const [fontsLoaded] = useFonts({
    'Poppins-Regular': require('./assets/fonts/Poppins-Regular.ttf'),
    'Poppins-Medium': require('./assets/fonts/Poppins-Medium.ttf'),
    'Poppins-SemiBold': require('./assets/fonts/Poppins-SemiBold.ttf'),
    'Poppins-Bold': require('./assets/fonts/Poppins-Bold.ttf'),
    'Poppins-ExtraBold': require('./assets/fonts/Poppins-ExtraBold.ttf'),
    'Poppins-Black': require('./assets/fonts/Poppins-Black.ttf'),
  });

  useEffect(() => {
    initializeOneSignal();

    const timeout = setTimeout(() => {
      setIsSplashVisible(false);
    }, 1600);

    return () => clearTimeout(timeout);
  }, []);

  if (isSplashVisible) {
    return <SplashScreen />;
  }

  if (!fontsLoaded) {
    return null;
  }

  applyDefaultPoppinsFont();

  return (
    <SafeAreaProvider>
      <PaperProvider>
        <NavigationContainer>
          <Stack.Navigator screenOptions={{ headerShown: false, animation: 'none' }}>
            <Stack.Screen name="Auth" component={AuthScreen} />
            <Stack.Screen name="AppTabs" component={AppTabs} />
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
