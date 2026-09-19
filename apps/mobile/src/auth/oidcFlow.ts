import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { parseTokenResponse, type TokenResponse } from "./tokenResponse";
import {
  TokenEndpointError,
  TokenNetworkError,
} from "./tokenEndpoint";
import type { OidcDiscovery } from "./discovery";
import type { OidcConfig } from "./oidcConfig";
import { authLog } from "./authLog";

WebBrowser.maybeCompleteAuthSession();

export type OidcAuthorizationResult =
  | { status: "success"; code: string; codeVerifier: string }
  | { status: "error"; message: string }
  | { status: "cancel" }
  | { status: "dismiss" };

export type OidcFlow = {
  authorize(
    config: OidcConfig,
    discovery: OidcDiscovery,
    preferEphemeral?: boolean
  ): Promise<OidcAuthorizationResult>;

  exchangeCode(
    config: OidcConfig,
    discovery: OidcDiscovery,
    code: string,
    codeVerifier: string
  ): Promise<TokenResponse>;

  refresh(
    discovery: OidcDiscovery,
    refreshToken: string,
    clientId: string,
    scopes: string[]
  ): Promise<TokenResponse>;

  endSession(
    discovery: OidcDiscovery,
    idTokenHint: string,
    postLogoutRedirectUri: string
  ): Promise<void>;

  recoverPassword?(
    config: OidcConfig,
    discovery: OidcDiscovery
  ): Promise<void>;
};

function authorizationEndpoint(
  discovery: OidcDiscovery
): AuthSession.AuthDiscoveryDocument {
  return { authorizationEndpoint: discovery.authorizationEndpoint };
}

async function tokenPost(
  fetchImpl: typeof globalThis.fetch,
  tokenEndpoint: string,
  body: URLSearchParams
): Promise<unknown> {
  let raw: Response;
  try {
    raw = await fetchImpl(tokenEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
      body,
    });
  } catch (cause) {
    throw new TokenNetworkError(cause);
  }

  let json: unknown;
  try {
    json = await raw.json();
  } catch {
    throw new TokenEndpointError(
      "The OIDC token endpoint returned a non-JSON response.",
      raw.status
    );
  }

  if (!raw.ok) {
    const errorCode =
      typeof json === "object" && json !== null
        ? ((json as { error?: string }).error ?? undefined)
        : undefined;
    throw new TokenEndpointError(
      `The OIDC token endpoint rejected the request (${raw.status}).`,
      raw.status,
      errorCode
    );
  }

  return json;
}

export function createOidcFlow(
  fetchImpl: typeof globalThis.fetch = globalThis.fetch
): OidcFlow {
  return {
    async authorize(config, discovery, preferEphemeral = true) {
      const request = new AuthSession.AuthRequest({
        clientId: config.clientId,
        scopes: config.scopes,
        redirectUri: config.redirectUri,
        usePKCE: true,
        extraParams: {
          response_type: "code",
        },
      });

      const result = await request.promptAsync(authorizationEndpoint(discovery), {
        preferEphemeralSession: preferEphemeral,
      });

      if (result.type === "success") {
        const code = result.params.code;
        if (!code) {
          return { status: "error", message: "The authorization server returned no authorization code." };
        }
        return {
          status: "success",
          code,
          codeVerifier: request.codeVerifier ?? "",
        };
      }

      if (result.type === "error") {
        authLog({
          event: "oidc_authorize_error",
          status: result.error?.message ?? "unknown",
        });
        return {
          status: "error",
          message: result.error?.message ?? "Authorization error.",
        };
      }

      if (result.type === "cancel") return { status: "cancel" };
      return { status: "dismiss" };
    },

    async exchangeCode(config, discovery, code, codeVerifier) {
      const body = new URLSearchParams({
        grant_type: "authorization_code",
        code,
        client_id: config.clientId,
        redirect_uri: config.redirectUri,
        code_verifier: codeVerifier,
      });

      const json = await tokenPost(fetchImpl, discovery.tokenEndpoint, body);
      return parseTokenResponse(json);
    },

    async refresh(discovery, refreshToken, clientId, scopes) {
      const body = new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: clientId,
        scope: scopes.join(" "),
      });

      const json = await tokenPost(fetchImpl, discovery.tokenEndpoint, body);
      return parseTokenResponse(json);
    },

    async endSession(discovery, idTokenHint, postLogoutRedirectUri) {
      if (!discovery.endSessionEndpoint) return;

      const logoutUrl =
        discovery.endSessionEndpoint +
        `?id_token_hint=${encodeURIComponent(idTokenHint)}` +
        `&post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUri)}`;

      try {
        await WebBrowser.openAuthSessionAsync(logoutUrl, postLogoutRedirectUri, {
          preferEphemeralSession: true,
        });
      } catch {
        authLog({ event: "oidc_end_session_failed", status: "non_fatal" });
      }
    },

    async recoverPassword(config, discovery) {
      const resetUrl =
        `${discovery.issuer}/login-actions/reset-credentials?client_id=${encodeURIComponent(config.clientId)}`;
      try {
        await WebBrowser.openBrowserAsync(resetUrl);
      } catch (cause) {
        authLog({
          event: "oidc_recover_password_failed",
          status: cause instanceof Error ? cause.message : "unknown",
        });
      }
    },
  };
}