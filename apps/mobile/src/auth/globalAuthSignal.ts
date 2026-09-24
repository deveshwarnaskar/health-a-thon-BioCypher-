/**
 * Singleton auth-expired signal shared by TanStack Query's QueryCache and the
 * session manager.  This breaks what would otherwise be a circular dependency
 * between those two modules.
 */
import { createAuthExpiredSignal } from "./authSignal";
import type { AuthExpiredSignal } from "./authSignal";

export const globalAuthExpiredSignal: AuthExpiredSignal = createAuthExpiredSignal();
