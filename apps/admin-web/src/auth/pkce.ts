/**
 * PKCE helpers (RFC 7636) for Keycloak Authorization Code + PKCE flow.
 *
 * Code verifier: 43-char random base64url string.
 * Code challenge: BASE64URL(SHA256(verifier)).
 */

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]!);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export interface PkcePair {
  codeVerifier: string;
  codeChallenge: string;
}

export async function createPkcePair(): Promise<PkcePair> {
  const bytes = new Uint8Array(32);
  window.crypto.getRandomValues(bytes);
  const codeVerifier = base64UrlEncode(bytes);

  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const digest = await window.crypto.subtle.digest("SHA-256", data);
  const codeChallenge = base64UrlEncode(new Uint8Array(digest));

  return { codeVerifier, codeChallenge };
}

export const PKCE_RFC7636_TEST_VECTOR = {
  verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
  challenge: "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
} as const;
