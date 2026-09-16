import { z } from "zod";

export type OidcDiscovery = {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  endSessionEndpoint?: string;
  revocationEndpoint?: string;
  issuer: string;
};

const discoverySchema = z
  .object({
    issuer: z.string().min(1),
    authorization_endpoint: z.string().url(),
    token_endpoint: z.string().url(),
    end_session_endpoint: z.string().url().optional(),
    revocation_endpoint: z.string().url().optional(),
  })
  .strict();

export type OidcDiscoveryError = {
  kind: "OIDC_DISCOVERY_ERROR";
  httpStatus: number;
  message: string;
  cause?: unknown;
};

export function isOidcDiscoveryError(
  error: unknown
): error is OidcDiscoveryError {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as OidcDiscoveryError).kind === "OIDC_DISCOVERY_ERROR"
  );
}

export function buildDiscoveryUrl(issuerUrl: string): string {
  const base = issuerUrl.replace(/\/+$/, "");
  return `${base}/.well-known/openid-configuration`;
}

let cachedDiscovery: Map<string, OidcDiscovery> | null = null;

function getCache(): Map<string, OidcDiscovery> {
  if (!cachedDiscovery) cachedDiscovery = new Map();
  return cachedDiscovery;
}

export function resetDiscoveryCache(): void {
  cachedDiscovery = null;
}

export async function discoverOidc(
  issuerUrl: string,
  fetchImpl: typeof globalThis.fetch = globalThis.fetch
): Promise<OidcDiscovery> {
  const cache = getCache();
  const cached = cache.get(issuerUrl);
  if (cached) return cached;

  const url = buildDiscoveryUrl(issuerUrl);

  let raw: Response;
  try {
    raw = await fetchImpl(url, {
      headers: { Accept: "application/json" },
    });
  } catch (cause) {
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: 0,
      message: "OIDC discovery request failed (network error).",
      cause,
    } satisfies OidcDiscoveryError;
  }

  let body: unknown;
  try {
    body = await raw.json();
  } catch {
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: raw.status,
      message: "OIDC discovery returned invalid JSON.",
    } satisfies OidcDiscoveryError;
  }

  const parsed = discoverySchema.safeParse(body);
  if (!parsed.success) {
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: raw.status,
      message: "OIDC discovery document is missing required endpoints.",
      cause: parsed.error,
    } satisfies OidcDiscoveryError;
  }

  const discovery: OidcDiscovery = {
    authorizationEndpoint: parsed.data.authorization_endpoint,
    tokenEndpoint: parsed.data.token_endpoint,
    endSessionEndpoint: parsed.data.end_session_endpoint,
    revocationEndpoint: parsed.data.revocation_endpoint,
    issuer: parsed.data.issuer,
  };

  cache.set(issuerUrl, discovery);
  return discovery;
}
