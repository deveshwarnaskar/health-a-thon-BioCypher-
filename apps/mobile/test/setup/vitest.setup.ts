import { vi } from "vitest";

// expo-crypto is a native-bound module. In the Node test environment we
// substitute the platform's own crypto.randomUUID implementation so the
// production UUID path (src/services/api/correlation.ts) is exercised
// without native modules.
vi.mock("expo-crypto", async () => {
  const { randomUUID } = await import("node:crypto");
  return { randomUUID };
});