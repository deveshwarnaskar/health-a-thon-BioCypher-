import * as Crypto from "expo-crypto";

/**
 * PKCE helpers (RFC 7636) for Authorization Code + PKCE.
 *
 * Code verifier: 43-char random base64url string derived from 32 random bytes
 * sourced from expo-crypto. Code challenge: S256 =
 * BASE64URL(SHA256(verifier)).
 *
 * Randomness and digest functions are injectable so vitest can exercise the
 * exact RFC 7636 test vector without invoking native modules.
 */

function base64ToBase64url(b64: string): string {
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return base64ToBase64url(btoa(binary));
}

export type PkceRandom = {
  randomBytesAsync?: (count: number) => Promise<Uint8Array>;
  digestStringAsync?: typeof Crypto.digestStringAsync;
};

export type PkcePair = {
  codeVerifier: string;
  codeChallenge: string;
};

export async function createPkcePair(random?: PkceRandom): Promise<PkcePair> {
  const randomBytesAsync = random?.randomBytesAsync ?? Crypto.getRandomBytesAsync;
  const digestStringAsync = random?.digestStringAsync ?? Crypto.digestStringAsync;

  const bytes = await randomBytesAsync(32);
  const codeVerifier = bytesToBase64Url(bytes);

  const rawDigest = await digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    codeVerifier,
    { encoding: Crypto.CryptoEncoding.BASE64 }
  );

  const codeChallenge = base64ToBase64url(rawDigest);

  return { codeVerifier, codeChallenge };
}

export function isPkceVerifierValid(verifier: string): boolean {
  if (verifier.length < 43 || verifier.length > 128) return false;
  return /^[A-Za-z0-9\-._~]+$/.test(verifier);
}

export function isPkceChallengeValid(challenge: string): boolean {
  return /^[A-Za-z0-9\-._]{43}$/.test(challenge);
}

const KNOWN_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
const KNOWN_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM";

export const PKCE_RFC7636_TEST_VECTOR = {
  verifier: KNOWN_VERIFIER,
  challenge: KNOWN_CHALLENGE,
} as const;