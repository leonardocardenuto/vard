import { NativeModules, Platform, TurboModuleRegistry } from 'react-native';

let isInitialized = false;
let initializationPromise: Promise<void> | null = null;
const SUBSCRIPTION_RETRY_COUNT = 8;
const SUBSCRIPTION_RETRY_DELAY_MS = 1000;

type OneSignalModule = typeof import('react-native-onesignal');

async function loadOneSignal(): Promise<OneSignalModule | null> {
  if (Platform.OS === 'web') {
    return null;
  }

  const nativeModule = NativeModules.OneSignal ?? TurboModuleRegistry.get('OneSignal');
  if (!nativeModule) {
    console.warn('OneSignal native module unavailable in this build.');
    return null;
  }

  try {
    return require('react-native-onesignal') as typeof import('react-native-onesignal');
  } catch (error) {
    console.warn('OneSignal native module unavailable in this build.', error);
    return null;
  }
}

function hasServerAssignedSubscriptionId(subscriptionId: string | null | undefined) {
  return Boolean(subscriptionId?.trim() && !subscriptionId.startsWith('local-'));
}

export function initializeOneSignal() {
  if (initializationPromise) {
    return initializationPromise;
  }

  initializationPromise = initializeOneSignalSdk();
  return initializationPromise;
}

async function initializeOneSignalSdk() {
  const appId = process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID?.trim();
  if (!appId || isInitialized) {
    return;
  }

  const oneSignalModule = await loadOneSignal();
  if (!oneSignalModule) {
    return;
  }

  oneSignalModule.OneSignal.initialize(appId);
  void oneSignalModule.OneSignal.Notifications.requestPermission(true);
  isInitialized = true;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

async function waitForOneSignalSubscriptionId(oneSignalModule: OneSignalModule | null) {
  if (!oneSignalModule) {
    return null;
  }

  for (let attempt = 0; attempt < SUBSCRIPTION_RETRY_COUNT; attempt += 1) {
    const subscriptionId = await oneSignalModule.OneSignal.User.pushSubscription.getIdAsync();
    if (hasServerAssignedSubscriptionId(subscriptionId)) {
      return subscriptionId;
    }

    await wait(SUBSCRIPTION_RETRY_DELAY_MS);
  }

  return null;
}

export async function getOneSignalSubscriptionId() {
  await initializeOneSignal();
  if (!isInitialized) {
    return null;
  }

  const oneSignalModule = await loadOneSignal();
  return waitForOneSignalSubscriptionId(oneSignalModule);
}

export async function identifyOneSignalUser(userId: string) {
  await initializeOneSignal();
  if (!isInitialized) {
    return null;
  }

  const oneSignalModule = await loadOneSignal();
  if (!oneSignalModule) {
    return null;
  }

  oneSignalModule.OneSignal.login(userId);
  return waitForOneSignalSubscriptionId(oneSignalModule);
}

export async function logoutOneSignalUser() {
  await initializeOneSignal();
  if (!isInitialized) {
    return;
  }

  const oneSignalModule = await loadOneSignal();
  oneSignalModule?.OneSignal.logout();
}

export async function addOneSignalEmail(email: string) {
  const oneSignalModule = await getInitializedOneSignalModule();
  oneSignalModule?.OneSignal.User.addEmail(email);
}

export async function addOneSignalSms(phoneNumber: string) {
  const oneSignalModule = await getInitializedOneSignalModule();
  oneSignalModule?.OneSignal.User.addSms(phoneNumber);
}

export async function addOneSignalTag(key: string, value: string) {
  const oneSignalModule = await getInitializedOneSignalModule();
  oneSignalModule?.OneSignal.User.addTag(key, value);
}

export async function setOneSignalLogLevel(level: import('react-native-onesignal').LogLevel) {
  const oneSignalModule = await getInitializedOneSignalModule();
  oneSignalModule?.OneSignal.Debug.setLogLevel(level);
}

async function getInitializedOneSignalModule() {
  await initializeOneSignal();
  return isInitialized ? loadOneSignal() : null;
}
