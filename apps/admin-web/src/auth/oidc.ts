import { createPkcePair } from "./pkce";

export interface OidcConfig {
  keycloakUrl: string;
  realm: string;
  clientId: string;
  redirectUri: string;
  scope: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  refresh_expires_in?: number;
  token_type: string;
}

export function getOidcConfig(): OidcConfig {
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
  return {
    keycloakUrl: import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8080",
    realm: import.meta.env.VITE_KEYCLOAK_REALM || "thali",
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "thali-admin-web",
    redirectUri: import.meta.env.VITE_OIDC_REDIRECT_URI || `${origin}/auth/callback`,
    scope: import.meta.env.VITE_OIDC_SCOPE || "openid profile email",
  };
}

const PKCE_VERIFIER_KEY = "thali_admin_pkce_verifier";
const OIDC_STATE_KEY = "thali_admin_oidc_state";

export async function buildAuthorizeUrl(config?: OidcConfig): Promise<string> {
  const cfg = config ?? getOidcConfig();
  const { codeVerifier, codeChallenge } = await createPkcePair();
  const state = window.crypto.randomUUID();

  sessionStorage.setItem(PKCE_VERIFIER_KEY, codeVerifier);
  sessionStorage.setItem(OIDC_STATE_KEY, state);

  const authUrl = new URL(
    `${cfg.keycloakUrl}/realms/${cfg.realm}/protocol/openid-connect/auth`,
  );
  authUrl.searchParams.set("client_id", cfg.clientId);
  authUrl.searchParams.set("redirect_uri", cfg.redirectUri);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", cfg.scope);
  authUrl.searchParams.set("state", state);
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");

  return authUrl.toString();
}

export async function exchangeCodeForTokens(
  code: string,
  returnedState: string,
  config?: OidcConfig,
): Promise<TokenResponse> {
  const cfg = config ?? getOidcConfig();
  const savedState = sessionStorage.getItem(OIDC_STATE_KEY);
  const codeVerifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);

  if (!savedState || savedState !== returnedState) {
    throw new Error("Invalid OIDC state parameter. Possible CSRF detected.");
  }
  if (!codeVerifier) {
    throw new Error("Missing PKCE code verifier in session storage.");
  }

  const tokenUrl = `${cfg.keycloakUrl}/realms/${cfg.realm}/protocol/openid-connect/token`;
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: cfg.clientId,
    code,
    redirect_uri: cfg.redirectUri,
    code_verifier: codeVerifier,
  });

  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  // Clean up verifier & state regardless of result
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(OIDC_STATE_KEY);

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Token exchange failed (${response.status}): ${errText}`);
  }

  return response.json();
}

export async function refreshAccessToken(
  refreshToken: string,
  config?: OidcConfig,
): Promise<TokenResponse> {
  const cfg = config ?? getOidcConfig();
  const tokenUrl = `${cfg.keycloakUrl}/realms/${cfg.realm}/protocol/openid-connect/token`;
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: cfg.clientId,
    refresh_token: refreshToken,
  });

  const response = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Token refresh failed (${response.status}): ${errText}`);
  }

  return response.json();
}

export function buildLogoutUrl(config?: OidcConfig): string {
  const cfg = config ?? getOidcConfig();
  const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
  const logoutUrl = new URL(
    `${cfg.keycloakUrl}/realms/${cfg.realm}/protocol/openid-connect/logout`,
  );
  logoutUrl.searchParams.set("client_id", cfg.clientId);
  logoutUrl.searchParams.set("post_logout_redirect_uri", `${origin}/login`);
  return logoutUrl.toString();
}
