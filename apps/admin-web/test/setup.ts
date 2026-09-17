import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll, afterAll } from "vitest";
import { setupServer } from "msw/node";
import { webcrypto } from "crypto";

// Ensure webcrypto is available in test environment
if (!globalThis.crypto) {
  // @ts-expect-error Node webcrypto polyfill
  globalThis.crypto = webcrypto;
} else if (!globalThis.crypto.subtle) {
  // @ts-expect-error Node webcrypto subtle polyfill
  globalThis.crypto.subtle = webcrypto.subtle;
}
if (!globalThis.crypto.randomUUID) {
  globalThis.crypto.randomUUID = () => webcrypto.randomUUID();
}

export const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  sessionStorage.clear();
  localStorage.clear();
});

afterAll(() => {
  server.close();
});
