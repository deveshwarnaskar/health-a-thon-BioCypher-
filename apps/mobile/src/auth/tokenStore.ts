export type TokenStore = {
  getAccessToken(): Promise<string | null>;
  getRefreshToken(): Promise<string | null>;
  getIdToken(): Promise<string | null>;
  saveTokens(tokens: {
    accessToken: string;
    refreshToken?: string;
    idToken?: string;
  }): Promise<void>;
  clear(): Promise<void>;
};

export class InMemoryTokenStore implements TokenStore {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private idToken: string | null = null;

  async getAccessToken(): Promise<string | null> {
    return this.accessToken;
  }

  async getRefreshToken(): Promise<string | null> {
    return this.refreshToken;
  }

  async getIdToken(): Promise<string | null> {
    return this.idToken;
  }

  async saveTokens(tokens: {
    accessToken: string;
    refreshToken?: string;
    idToken?: string;
  }): Promise<void> {
    this.accessToken = tokens.accessToken;
    if (tokens.refreshToken !== undefined) this.refreshToken = tokens.refreshToken;
    if (tokens.idToken !== undefined) this.idToken = tokens.idToken;
  }

  async clear(): Promise<void> {
    this.accessToken = null;
    this.refreshToken = null;
    this.idToken = null;
  }
}
