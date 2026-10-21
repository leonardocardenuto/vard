import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const TOKEN_KEY = 'vard_access_token';
function webStorage() {
  return Platform.OS === 'web' && typeof window !== 'undefined' ? window.localStorage : null;
}
export async function saveToken(token: string) {
  const storage = webStorage();
  if (storage) storage.setItem(TOKEN_KEY, token);
  else await SecureStore.setItemAsync(TOKEN_KEY, token);
}
export async function loadToken() {
  const storage = webStorage();
  return storage ? storage.getItem(TOKEN_KEY) : SecureStore.getItemAsync(TOKEN_KEY);
}
export async function deleteToken() {
  const storage = webStorage();
  if (storage) storage.removeItem(TOKEN_KEY);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}
