import { RouteProp, useRoute } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { AppTabParamList } from "../../../navigation/types";
import { CameraSettingsPanel } from "../components/CameraSettingsPanel";
import { CameraConnectionFormScreen } from "./CameraConnectionFormScreen";
import { CameraLiveViewScreen } from "./CameraLiveViewScreen";
import { SettingsStackParamList } from "../types";
import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';

type SettingsRoute = RouteProp<AppTabParamList, "Settings">;
const Stack = createNativeStackNavigator<SettingsStackParamList>();

export function Settings() {
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
