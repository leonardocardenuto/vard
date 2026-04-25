import { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { BottomNavigationBar } from './src/components/BottomNavigationBar';
import { SplashScreen } from './src/components/SplashScreen';
import { AppTabParamList, RootStackParamList } from './src/navigation/types';
import { AuthScreen } from './src/views/auth/pages/AuthScreen';
import { Home } from './src/views/home/pages/Home';
import { Insights } from './src/views/insights/pages/Insights';
import { Settings } from './src/views/settings/pages/Settings';
import { Workspace } from './src/views/workspace/pages/Workspace';

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tabs = createBottomTabNavigator<AppTabParamList>();

type AppTabsProps = NativeStackScreenProps<RootStackParamList, 'AppTabs'>;

function AppTabs({ route }: AppTabsProps) {
  const userName = route.params?.userName;
  const accessToken = route.params?.accessToken ?? '';
  const userEmail = route.params?.userEmail ?? '';

  return (
    <Tabs.Navigator
      screenOptions={{ headerShown: false, animation: 'none' }}
      tabBar={(props) => <BottomNavigationBar {...props} />}
    >
      <Tabs.Screen
        name="Home"
        component={Home}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Tabs.Screen
        name="Workspace"
        component={Workspace}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Tabs.Screen
        name="Insights"
        component={Insights}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Tabs.Screen
        name="Settings"
        component={Settings}
        initialParams={{ accessToken, userEmail, userName }}
      />
    </Tabs.Navigator>
  );
}

export default function App() {
  const [isSplashVisible, setIsSplashVisible] = useState(true);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsSplashVisible(false);
    }, 1600);

    return () => clearTimeout(timeout);
  }, []);

  if (isSplashVisible) {
    return <SplashScreen />;
  }

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Stack.Navigator screenOptions={{ headerShown: false, animation: 'none' }}>
          <Stack.Screen name="Auth" component={AuthScreen} />
          <Stack.Screen name="AppTabs" component={AppTabs} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
