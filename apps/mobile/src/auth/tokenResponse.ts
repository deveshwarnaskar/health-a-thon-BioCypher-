import { z } from "zod";

export const tokenResponseSchema = z
  .object({
    access_token: z.string().min(1, "access_token is required"),
    refresh_token: z.string().min(1).optional(),
    id_token: z.string().min(1).optional(),
    expires_in: z
      .number()
      .int()
      .positive("expires_in must be a positive integer"),
    token_type: z.literal("Bearer"),
    scope: z.string().optional(),
  });

export type TokenResponse = z.infer<typeof tokenResponseSchema>;

export function parseTokenResponse(body: unknown): TokenResponse {
  const result = tokenResponseSchema.safeParse(body);
  if (!result.success) {
    throw new TokenExchangeError(
      "Token response does not match the OIDC token contract."
    );
  }
  return result.data;
}

export class TokenExchangeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TokenExchangeError";
  }
}
