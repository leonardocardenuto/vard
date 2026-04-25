import { useEffect, useState } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { SplashScreen } from './src/components/SplashScreen';
import { RootStackParamList } from './src/navigation/types';
import { AuthScreen } from './src/views/auth/pages/AuthScreen';
import { Home } from './src/views/home/pages/Home';
import { Insights } from './src/views/insights/pages/Insights';
import { Settings } from './src/views/settings/pages/Settings';
import { Workspace } from './src/views/workspace/pages/Workspace';

const Stack = createNativeStackNavigator<RootStackParamList>();

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
          <Stack.Screen name="Home" component={Home} />
          <Stack.Screen name="Workspace" component={Workspace} />
          <Stack.Screen name="Insights" component={Insights} />
          <Stack.Screen name="Settings" component={Settings} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
