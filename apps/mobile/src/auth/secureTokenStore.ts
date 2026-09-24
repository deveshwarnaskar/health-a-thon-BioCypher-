import * as SecureStore from "expo-secure-store";
import type { TokenStore } from "./tokenStore";

const ACCESS_TOKEN_KEY = "thali.auth.access_token";
const REFRESH_TOKEN_KEY = "thali.auth.refresh_token";
const ID_TOKEN_KEY = "thali.auth.id_token";

const DEFAULT_OPTIONS: SecureStore.SecureStoreOptions = {};

/**
 * expo-secure-store backed token persistence.  Tokens are stored in the
 * iOS Keychain / Android Keystore and are never written to disk, logs,
 * Zustand, or AsyncStorage (Gate 10C §Secure Storage).
 */
export class SecureStoreTokenStore implements TokenStore {
  async getAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(ACCESS_TOKEN_KEY, DEFAULT_OPTIONS);
  }

  async getRefreshToken(): Promise<string | null> {
    return SecureStore.getItemAsync(REFRESH_TOKEN_KEY, DEFAULT_OPTIONS);
  }

  async getIdToken(): Promise<string | null> {
    return SecureStore.getItemAsync(ID_TOKEN_KEY, DEFAULT_OPTIONS);
  }

  async saveTokens(tokens: {
    accessToken: string;
    refreshToken?: string;
    idToken?: string;
  }): Promise<void> {
    await SecureStore.setItemAsync(
      ACCESS_TOKEN_KEY,
      tokens.accessToken,
      DEFAULT_OPTIONS
    );

    if (tokens.refreshToken !== undefined) {
      await SecureStore.setItemAsync(
        REFRESH_TOKEN_KEY,
        tokens.refreshToken,
        DEFAULT_OPTIONS
      );
    }

    if (tokens.idToken !== undefined) {
      await SecureStore.setItemAsync(ID_TOKEN_KEY, tokens.idToken, DEFAULT_OPTIONS);
    }
  }

  async clear(): Promise<void> {
    await Promise.all([
      SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY, DEFAULT_OPTIONS).catch(() => {}),
      SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY, DEFAULT_OPTIONS).catch(() => {}),
      SecureStore.deleteItemAsync(ID_TOKEN_KEY, DEFAULT_OPTIONS).catch(() => {}),
    ]);
  }
}
