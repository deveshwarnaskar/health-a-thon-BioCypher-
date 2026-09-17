/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_KEYCLOAK_URL?: string;
  readonly VITE_KEYCLOAK_REALM?: string;
  readonly VITE_KEYCLOAK_CLIENT_ID?: string;
  readonly VITE_OIDC_REDIRECT_URI?: string;
  readonly VITE_OIDC_SCOPE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
