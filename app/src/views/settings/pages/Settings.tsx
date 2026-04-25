import { RouteProp, useRoute } from '@react-navigation/native';

import { LayoutWithNavbar } from '../../../components/LayoutWithNavbar';
import { AppTabParamList } from '../../../navigation/types';
import { CameraSettingsPanel } from '../components/CameraSettingsPanel';

type SettingsRoute = RouteProp<AppTabParamList, 'Settings'>;

export function Settings() {
  const route = useRoute<SettingsRoute>();
  const accessToken = route.params?.accessToken ?? '';
  const userEmail = route.params?.userEmail ?? '';
  const userName = route.params?.userName ?? 'usuário';

  return (
    <LayoutWithNavbar>
      <CameraSettingsPanel
        accessToken={accessToken}
        userEmail={userEmail}
        userName={userName}
      />
    </LayoutWithNavbar>
  );
}
