import { z } from "zod";

/**
 * Validated OIDC Discovery Document (RFC 8414 & OpenID Connect Discovery 1.0).
 *
 * Operational endpoints required for THALI authentication, token exchange,
 * session management, and password recovery are strongly typed.
 */
export type OidcDiscovery = {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  endSessionEndpoint?: string;
  revocationEndpoint?: string;
  issuer: string;
  jwksUri?: string;
  userInfoEndpoint?: string;
  codeChallengeMethodsSupported?: string[];
};

/**
 * Zod schema for OIDC discovery document validation.
 *
 * Security-Critical Operational Fields:
 * - `issuer`: Must be a valid URL string.
 * - `authorization_endpoint`: Required valid URL for Authorization Code Flow with PKCE.
 * - `token_endpoint`: Required valid URL for code exchange & refresh.
 * - `jwks_uri`: Valid URL if present (backend token verification trust anchor).
 * - `end_session_endpoint`: Valid URL if present (RP-initiated logout).
 * - `revocation_endpoint`: Valid URL if present (token revocation).
 * - `userinfo_endpoint`: Valid URL if present (user claims).
 * - `code_challenge_methods_supported`: If advertised, must include S256 (THALI mandatory PKCE method).
 *
 * Informational OIDC Metadata Tolerated (RFC 8414 Section 3.2):
 * - Standard metadata parameters such as `scopes_supported`, `response_types_supported`,
 *   `grant_types_supported`, `subject_types_supported`, etc. are safely ignored/stripped
 *   so compliant IDPs (e.g. Keycloak 24) are accepted without allowing unrecognized
 *   keys to pollute the operational model.
 */
const discoverySchema = z.object({
  issuer: z.string().url(),
  authorization_endpoint: z.string().url(),
  token_endpoint: z.string().url(),
  jwks_uri: z.string().url().optional(),
  end_session_endpoint: z.string().url().optional(),
  revocation_endpoint: z.string().url().optional(),
  userinfo_endpoint: z.string().url().optional(),
  code_challenge_methods_supported: z
    .array(z.string())
    .optional()
    .refine(
      (methods) => methods === undefined || methods.includes("S256"),
      {
        message: "OIDC provider must support PKCE code_challenge_method S256.",
      }
    ),
});

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

  if (!raw.ok) {
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: raw.status,
      message: `OIDC discovery request failed with HTTP ${raw.status}.`,
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
    const errorDetails = parsed.error.issues
      .map((i) => `${i.path.join(".") || "document"}: ${i.message}`)
      .join("; ");
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: raw.status,
      message: `OIDC discovery document validation failed: ${errorDetails}`,
      cause: parsed.error,
    } satisfies OidcDiscoveryError;
  }

  // Strict issuer validation: RFC 8414 Section 3.3 requires the issuer
  // in the metadata to be identical to the configured issuer URL.
  const normalizeUrl = (u: string) => u.trim().replace(/\/+$/, "");
  if (normalizeUrl(parsed.data.issuer) !== normalizeUrl(issuerUrl)) {
    throw {
      kind: "OIDC_DISCOVERY_ERROR" as const,
      httpStatus: raw.status,
      message: `OIDC discovery issuer mismatch: expected "${issuerUrl}", got "${parsed.data.issuer}".`,
    } satisfies OidcDiscoveryError;
  }

  const discovery: OidcDiscovery = {
    authorizationEndpoint: parsed.data.authorization_endpoint,
    tokenEndpoint: parsed.data.token_endpoint,
    endSessionEndpoint: parsed.data.end_session_endpoint,
    revocationEndpoint: parsed.data.revocation_endpoint,
    issuer: parsed.data.issuer,
    jwksUri: parsed.data.jwks_uri,
    userInfoEndpoint: parsed.data.userinfo_endpoint,
    codeChallengeMethodsSupported: parsed.data.code_challenge_methods_supported,
  };

  cache.set(issuerUrl, discovery);
  return discovery;
}
