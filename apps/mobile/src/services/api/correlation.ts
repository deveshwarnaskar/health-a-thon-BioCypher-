import * as Crypto from "expo-crypto";

/**
 * Cryptographically secure UUIDv4 via expo-crypto (iOS Keychain / Android
 * Keystore backed entropy, Gate 10A §9).
 */
export function secureUuid(): string {
  return Crypto.randomUUID();
}

/** Runs on every request; correlation IDs never contain PHI and are the only
 * request identifier written to device logs (Gate 10A §17). */
export function newCorrelationId(): string {
  return secureUuid();
}

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isUuidV4(value: string): boolean {
  return UUID_V4.test(value);
}