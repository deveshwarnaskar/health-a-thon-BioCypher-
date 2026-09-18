/**
 * Client-safe environment configuration.
 *
 * Only EXPO_PUBLIC_* variables may exist in the app bundle. Server-only
 * secrets (JWT_SECRET, DATABASE_URL, Keycloak client secrets, WhatsApp/S3
 * keys) are STRICTLY FORBIDDEN here and never enter the mobile binary
 * (Gate 10A §7, §17).
 */

export type AppEnvironment = "development" | "staging" | "production";

export type AppApiConfig = {
  apiBaseUrl: string;
  environment: AppEnvironment;
  keycloakIssuerUrl: string;
  keycloakRealm: string;
  keycloakClientId: string;
  keycloakRedirectUri: string;
  authEnabled: boolean;
};

function isAppEnvironment(value: string | undefined): value is AppEnvironment {
  return value === "development" || value === "staging" || value === "production";
}

export function readApiConfig(env: Record<string, string | undefined> = process.env): AppApiConfig {
  return {
    apiBaseUrl: env.EXPO_PUBLIC_API_BASE_URL ?? "",
    environment: isAppEnvironment(env.EXPO_PUBLIC_ENVIRONMENT)
      ? env.EXPO_PUBLIC_ENVIRONMENT
      : "development",
    keycloakIssuerUrl: env.EXPO_PUBLIC_KEYCLOAK_ISSUER_URL ?? "",
    keycloakRealm: env.EXPO_PUBLIC_KEYCLOAK_REALM ?? "",
    keycloakClientId: env.EXPO_PUBLIC_KEYCLOAK_CLIENT_ID ?? "",
    keycloakRedirectUri: env.EXPO_PUBLIC_KEYCLOAK_REDIRECT_URI ?? "",
    authEnabled: (env.EXPO_PUBLIC_AUTH_ENABLED ?? "false") === "true",
  };
}

let cachedConfig: AppApiConfig | null = null;

/**
 * Config is resolved lazily so EXPO_PUBLIC_* values inlined by Expo at build
 * time are captured, while tests can set process.env before first use.
 */
export function getApiConfig(): AppApiConfig {
  if (!cachedConfig) {
    cachedConfig = readApiConfig();
  }
  return cachedConfig;
}

export function resetApiConfig(): void {
  cachedConfig = null;
}

export class ApiConfigError extends Error {
  constructor(missing: string) {
    super(`${missing} is not configured. Set it in apps/mobile/.env (see .env.example).`);
    this.name = "ApiConfigError";
  }
}

/**
 * Enforces "no hard-coded URLs": the client must be pointed at a configured
 * base URL before any request may fire.
 * In production mode, rejects insecure http:// and localhost endpoints.
 */
export function requireConfigured(config: AppApiConfig): AppApiConfig {
  if (!config.apiBaseUrl) {
    throw new ApiConfigError("EXPO_PUBLIC_API_BASE_URL");
  }
  if (config.environment === "production") {
    const url = config.apiBaseUrl.toLowerCase();
    if (url.startsWith("http://") || url.includes("localhost") || url.includes("127.0.0.1")) {
      throw new ApiConfigError(
        "Production environment requires a secure HTTPS API endpoint, non-localhost",
      );
    }
  }
  return config;
}