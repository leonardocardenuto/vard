import { Platform } from 'react-native';

let isInitialized = false;

const SUBSCRIPTION_RETRY_COUNT = 8;
const SUBSCRIPTION_RETRY_DELAY_MS = 1000;

async function loadOneSignal() {
  if (Platform.OS === 'web') {
    return null;
  }

  try {
    return await import('react-native-onesignal');
  } catch {
    return null;
  }
}

export async function initializeOneSignal() {
  const appId = process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID?.trim();
  if (!appId || isInitialized) {
    return;
  }

  const oneSignalModule = await loadOneSignal();
  if (!oneSignalModule) {
    return;
  }

  oneSignalModule.OneSignal.initialize(appId);
  await oneSignalModule.OneSignal.Notifications.requestPermission(true);
  isInitialized = true;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

async function waitForOneSignalSubscriptionId(oneSignalModule: Awaited<ReturnType<typeof loadOneSignal>>) {
  if (!oneSignalModule) {
    return null;
  }

  for (let attempt = 0; attempt < SUBSCRIPTION_RETRY_COUNT; attempt += 1) {
    const subscriptionId = await oneSignalModule.OneSignal.User.pushSubscription.getIdAsync();
    if (subscriptionId) {
      return subscriptionId;
    }

    await wait(SUBSCRIPTION_RETRY_DELAY_MS);
  }

  return null;
}

export async function getOneSignalSubscriptionId() {
  await initializeOneSignal();

  const oneSignalModule = await loadOneSignal();
  return waitForOneSignalSubscriptionId(oneSignalModule);
}

export async function identifyOneSignalUser(userId: string) {
  await initializeOneSignal();

  const oneSignalModule = await loadOneSignal();
  if (!oneSignalModule) {
    return null;
  }

  oneSignalModule.OneSignal.login(userId);
  return waitForOneSignalSubscriptionId(oneSignalModule);
}
