import { logoutOneSignalUser } from "./onesignal";
import { stopMobileFallMonitor } from './mobileFallMonitor';
import { revokeCurrentPushRegistration } from './pushNotifications';

import { deleteToken } from './sessionToken';
export { loadToken, saveToken } from './sessionToken';

export async function clearSession() {
  await revokeCurrentPushRegistration();
  await stopMobileFallMonitor();
  await deleteToken();
  await logoutOneSignalUser();
}
