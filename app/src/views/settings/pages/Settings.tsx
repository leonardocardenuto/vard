import { RouteProp, useRoute } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { AppTabParamList } from "../../../navigation/types";
import { CameraSettingsPanel } from "../components/CameraSettingsPanel";
import { CameraConnectionFormScreen } from "./CameraConnectionFormScreen.tsx";
import { CameraLiveViewScreen } from "./CameraLiveViewScreen.tsx";
import { SettingsStackParamList } from "../types";
import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';

type SettingsRoute = RouteProp<AppTabParamList, "Settings">;
type SettingsProps = {
  onLogout: () => void;
};
const Stack = createNativeStackNavigator<SettingsStackParamList>();

export function Settings({ onLogout }: SettingsProps) {
  const route = useRoute<SettingsRoute>();
  const accessToken = route.params?.accessToken ?? "";
  const userEmail = route.params?.userEmail ?? "";
  const userName = route.params?.userName ?? "usuário";

  return (
    <Stack.Navigator
      screenOptions={{ headerShown: false, animation: "slide_from_right" }}
    >
      <Stack.Screen
        name="SettingsHome"
        initialParams={{ accessToken, userEmail, userName }}
      >
        {() => (
          <LayoutWithNavbar>
            <CameraSettingsPanel
              accessToken={accessToken}
              onLogout={onLogout}
              userEmail={userEmail}
              userName={userName}
            />
          </LayoutWithNavbar>
        )}
      </Stack.Screen>
      <Stack.Screen
        name="CameraConnectionForm"
        component={CameraConnectionFormScreen}
        initialParams={{ accessToken, userEmail, userName }}
      />
      <Stack.Screen name="CameraLiveView" component={CameraLiveViewScreen} />
    </Stack.Navigator>
  );
}
