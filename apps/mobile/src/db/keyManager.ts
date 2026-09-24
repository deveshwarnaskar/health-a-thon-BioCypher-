import * as Crypto from "expo-crypto";

const DB_ENCRYPTION_KEY_ALIAS = "thali.sqlcipher.db_key";

export interface KeyStorage {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
}

const defaultStorage: KeyStorage = {
  async getItemAsync(key: string) {
    const SecureStore = await import("expo-secure-store");
    return SecureStore.getItemAsync(key);
  },
  async setItemAsync(key: string, value: string) {
    const SecureStore = await import("expo-secure-store");
    return SecureStore.setItemAsync(key, value);
  },
  async deleteItemAsync(key: string) {
    const SecureStore = await import("expo-secure-store");
    return SecureStore.deleteItemAsync(key);
  },
};

export class SqlCipherKeyManager {
  private readonly storage: KeyStorage;

  constructor(storage: KeyStorage = defaultStorage) {
    this.storage = storage;
  }

  /**
   * Retrieves the existing 256-bit SQLCipher encryption key or securely generates
   * and persists a new 32-byte (256-bit) hex key in SecureStore/Keychain/Keystore.
   *
   * Invariants:
   * - Key is NEVER hardcoded, committed, or plaintext in logs/AsyncStorage/Zustand.
   * - 256-bit cryptographically secure entropy.
   */
  async getOrCreateDatabaseKey(): Promise<string> {
    const existing = await this.storage.getItemAsync(DB_ENCRYPTION_KEY_ALIAS);
    if (existing !== null) {
      if (this.isValidKey(existing)) {
        return existing;
      }
      throw new Error("Stored database encryption key is corrupted or invalid format.");
    }

    const generatedKey = await this.generateSecureKey();
    await this.storage.setItemAsync(DB_ENCRYPTION_KEY_ALIAS, generatedKey);
    return generatedKey;
  }

  /**
   * Retrieves the existing key without auto-generating a new one.
   * Returns null if key does not exist.
   */
  async getDatabaseKey(): Promise<string | null> {
    const existing = await this.storage.getItemAsync(DB_ENCRYPTION_KEY_ALIAS);
    if (existing && this.isValidKey(existing)) {
      return existing;
    }
    return null;
  }

  /**
   * Clears the encryption key from hardware-backed secure storage.
   * Only used for explicit security reset / wipe.
   */
  async clearDatabaseKey(): Promise<void> {
    await this.storage.deleteItemAsync(DB_ENCRYPTION_KEY_ALIAS);
  }

  private async generateSecureKey(): Promise<string> {
    try {
      const bytes = await Crypto.getRandomBytesAsync(32);
      return Array.from(bytes)
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    } catch {
      // Fallback to crypto.getRandomValues if in browser/Node or expo-crypto unavailable
      if (typeof globalThis.crypto?.getRandomValues === "function") {
        const bytes = new Uint8Array(32);
        globalThis.crypto.getRandomValues(bytes);
        return Array.from(bytes)
          .map((b) => b.toString(16).padStart(2, "0"))
          .join("");
      }
      throw new Error("Cryptographic random entropy source is unavailable.");
    }
  }

  private isValidKey(key: string): boolean {
    return typeof key === "string" && key.length === 64 && /^[0-9a-fA-F]{64}$/.test(key);
  }
}

export const sqlCipherKeyManager = new SqlCipherKeyManager();
