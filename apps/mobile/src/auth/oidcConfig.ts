import { z } from "zod";

export type OidcConfig = {
  issuerUrl: string;
  realm: string;
  clientId: string;
  redirectUri: string;
  scopes: string[];
};

export const DEFAULT_SCOPES = ["openid", "profile", "email", "offline_access"];

export function parseOidcScopes(raw: string | undefined): string[] {
  if (!raw) return DEFAULT_SCOPES;
  const trimmed = raw.trim();
  if (!trimmed) return DEFAULT_SCOPES;
  return [...new Set(trimmed.split(/\s+/))].filter(Boolean);
}

export function readOidcConfig(
  env: Record<string, string | undefined> = process.env
): OidcConfig {
  return {
    issuerUrl: env.EXPO_PUBLIC_KEYCLOAK_ISSUER_URL ?? "",
    realm: env.EXPO_PUBLIC_KEYCLOAK_REALM ?? "",
    clientId: env.EXPO_PUBLIC_KEYCLOAK_CLIENT_ID ?? "",
    redirectUri: env.EXPO_PUBLIC_KEYCLOAK_REDIRECT_URI ?? "",
    scopes: parseOidcScopes(env.EXPO_PUBLIC_KEYCLOAK_SCOPES),
  };
}

export class OidcConfigError extends Error {
  constructor(missing: string) {
    super(
      `${missing} is not configured. Set EXPO_PUBLIC_KEYCLOAK_${missing} in apps/mobile/.env.`
    );
    this.name = "OidcConfigError";
  }
}

export function requireOidcConfigured(config: OidcConfig): OidcConfig {
  if (!config.issuerUrl) throw new OidcConfigError("ISSUER_URL");
  if (!config.realm) throw new OidcConfigError("REALM");
  if (!config.clientId) throw new OidcConfigError("CLIENT_ID");
  if (!config.redirectUri) throw new OidcConfigError("REDIRECT_URI");
  return config;
}

export function buildDiscoveryUrl(issuerUrl: string): string {
  const base = issuerUrl.replace(/\/+$/, "");
  return `${base}/.well-known/openid-configuration`;
}

export const oidcConfigSchema = z
  .object({
    issuerUrl: z.string().min(1),
    realm: z.string().min(1),
    clientId: z.string().min(1),
    redirectUri: z.string().min(1),
    scopes: z.array(z.string().min(1)).min(1),
  })
  .strict();
