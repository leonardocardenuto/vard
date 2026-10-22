import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { logoutOneSignalUser } from "./onesignal";
import { stopMobileFallMonitor } from './mobileFallMonitor';

const TOKEN_KEY = "vard_access_token";

function getWebStorage() {
  if (Platform.OS !== "web" || typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export async function saveToken(token: string) {
  const webStorage = getWebStorage();

  if (webStorage) {
    webStorage.setItem(TOKEN_KEY, token);
    return;
  }

  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function loadToken() {
  const webStorage = getWebStorage();

  if (webStorage) {
    return webStorage.getItem(TOKEN_KEY);
  }

  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function clearSession() {
  await stopMobileFallMonitor();
  const webStorage = getWebStorage();

  if (webStorage) {
    webStorage.removeItem(TOKEN_KEY);
    await logoutOneSignalUser();
    return;
  }

  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await logoutOneSignalUser();
}
