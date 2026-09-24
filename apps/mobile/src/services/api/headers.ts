/**
 * Request header assembly (Gate 10A §9 interceptor matrix).
 */

export type HttpHeaders = Record<string, string>;

export const HEADER_AUTHORIZATION = "Authorization";
export const HEADER_CORRELATION_ID = "X-Correlation-ID";
export const HEADER_IDEMPOTENCY_KEY = "Idempotency-Key";
export const HEADER_CONTENT_TYPE = "Content-Type";
export const HEADER_ACCEPT = "Accept";
export const HEADER_RETRY_AFTER = "Retry-After";

export type AssembleHeadersOptions = {
  token?: string;
  correlationId: string;
  idempotencyKey?: string;
  hasBody?: boolean;
};

export function assembleHeaders(options: AssembleHeadersOptions): HttpHeaders {
  const headers: HttpHeaders = {
    [HEADER_ACCEPT]: "application/json",
    [HEADER_CORRELATION_ID]: options.correlationId,
  };

  if (options.token) {
    headers[HEADER_AUTHORIZATION] = `Bearer ${options.token}`;
  }
  if (options.idempotencyKey) {
    headers[HEADER_IDEMPOTENCY_KEY] = options.idempotencyKey;
  }
  if (options.hasBody) {
    headers[HEADER_CONTENT_TYPE] = "application/json";
  }
  return headers;
}