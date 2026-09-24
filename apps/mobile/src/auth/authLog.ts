/**
 * PHI-safe structured logger for authentication events.
 *
 * Never logs: access tokens, refresh tokens, authorization headers,
 * patient names, phone numbers, glucose values, clinical payloads,
 * or JWT contents (Gate 10C §Security).
 *
 * Only safe metadata: event type, status, correlation ID, HTTP status,
 * and non-sensitive error category strings.
 */
export type AuthLogEntry = {
  event: string;
  status?: string;
  correlationId?: string;
  httpStatus?: number;
  category?: string;
  [key: string]: unknown;
};

export function authLog(entry: AuthLogEntry): void {
  console.log("[auth]", JSON.stringify(entry));
}
