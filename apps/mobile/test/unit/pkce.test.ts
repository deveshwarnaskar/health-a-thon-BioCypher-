import { describe, it, expect, vi } from "vitest";
import {
  createPkcePair,
  isPkceVerifierValid,
  isPkceChallengeValid,
  PKCE_RFC7636_TEST_VECTOR,
} from "../../src/auth/pkce";

vi.mock("expo-crypto", async () => {
  const { randomUUID } = await import("node:crypto");
  return {
    randomUUID,
    CryptoDigestAlgorithm: { SHA256: "SHA-256" },
    CryptoEncoding: { BASE64: "base64" },
  };
});

describe("pkce (RFC 7636)", () => {
  it("derives the RFC 7636 test vector challenge from a known verifier", async () => {
    const crypto = await import("node:crypto");

    // Decode the known verifier from base64url to raw bytes.
    // bytesToBase64Url(knownVerifierBytes) must round-trip back to the verifier string.
    const b64 = PKCE_RFC7636_TEST_VECTOR.verifier
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const knownVerifierBytes = new Uint8Array(
      Buffer.from(padded, "base64")
    );

    const { codeVerifier, codeChallenge } = await createPkcePair({
      randomBytesAsync: async () => knownVerifierBytes,
      digestStringAsync: async (_algo, data, _opts) => {
        return crypto.createHash("sha256").update(data).digest("base64");
      },
    });

    expect(codeVerifier).toBe(PKCE_RFC7636_TEST_VECTOR.verifier);
    const expectedChallenge = crypto
      .createHash("sha256")
      .update(PKCE_RFC7636_TEST_VECTOR.verifier)
      .digest("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    expect(codeChallenge).toBe(expectedChallenge);
  });

  it("validates verifier and challenge formats", () => {
    expect(isPkceVerifierValid("a".repeat(43))).toBe(true);
    expect(isPkceVerifierValid("a".repeat(42))).toBe(false);
    expect(isPkceVerifierValid("a".repeat(129))).toBe(false);
    expect(isPkceVerifierValid("a".repeat(43).replace("a", "???"))).toBe(false);
    expect(isPkceChallengeValid("a".repeat(43))).toBe(true);
    expect(isPkceChallengeValid("a".repeat(42))).toBe(false);
  });
});
