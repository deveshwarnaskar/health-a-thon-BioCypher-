import type { ZodType } from "zod";

export type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

export type EndpointDefinition<TResponse, TRequest = undefined> = {
  method: HttpMethod;
  path: string | ((...args: string[]) => string);
  /** Gate 09: every state-changing mutation MUST carry an Idempotency-Key. */
  requiresIdempotencyKey: boolean;
  responseSchema?: ZodType<TResponse>;
  requestSchema?: ZodType<TRequest>;
};

export function withQuery(path: string, params: Record<string, string | number | undefined>): string {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join("&");
  return query ? `${path}?${query}` : path;
}