const ACCESS_TOKEN_KEY = "thali_admin_access_token";
const REFRESH_TOKEN_KEY = "thali_admin_refresh_token";
const EXPIRES_AT_KEY = "thali_admin_expires_at";

export interface StoredTokens {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
}

export const tokenStorage = {
  getAccessToken(): string | null {
    return sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken(): string | null {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  },

  getExpiresAt(): number | null {
    const val = sessionStorage.getItem(EXPIRES_AT_KEY);
    return val ? Number(val) : null;
  },

  setTokens(tokens: StoredTokens): void {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
    if (tokens.refreshToken) {
      sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
    }
    if (tokens.expiresAt) {
      sessionStorage.setItem(EXPIRES_AT_KEY, String(tokens.expiresAt));
    }
  },

  clearTokens(): void {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    sessionStorage.removeItem(EXPIRES_AT_KEY);
  },

  hasTokens(): boolean {
    return !!sessionStorage.getItem(ACCESS_TOKEN_KEY);
  },

  isExpired(): boolean {
    const expiresAt = this.getExpiresAt();
    if (!expiresAt) return false;
    // Buffer by 30 seconds
    return Date.now() >= expiresAt - 30_000;
  },
};
