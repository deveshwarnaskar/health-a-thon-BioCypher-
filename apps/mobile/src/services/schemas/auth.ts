import { z } from "zod";

// ─── Auth ────────────────────────────────────────────────────────────────
// Mirrors backend/interfaces/http/v2/schemas/models.py:AuthVerifyResponse.

export const authVerifyResponseSchema = z
  .object({
    actor_id: z.string(),
    tenant_id: z.string(),
    roles: z.array(z.string()),
    facility_id: z.string().nullable().optional(),
  })
  .strict();

export type AuthVerifyResponse = z.infer<typeof authVerifyResponseSchema>;