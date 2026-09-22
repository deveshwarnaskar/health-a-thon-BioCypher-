import { z } from "zod";

// ─── WhatsApp Schemas (Gate 10P / WhatsApp Onboarding Contract) ─────────────

export const whatsAppConnectionStatusSchema = z.enum([
  "connected",
  "not_connected",
  "pending",
  "failed",
]);
export type WhatsAppConnectionStatus = z.infer<typeof whatsAppConnectionStatusSchema>;

export const whatsAppIdentityResponseSchema = z
  .object({
    status: whatsAppConnectionStatusSchema,
    phone_number: z.string().nullable().optional(),
    phone_number_masked: z.string().nullable().optional(),
    verified_at: z.string().nullable().optional(),
    capabilities: z.array(z.string()),
  })
  .strict();
export type WhatsAppIdentityResponse = z.infer<typeof whatsAppIdentityResponseSchema>;

export const whatsAppRequestVerificationRequestSchema = z
  .object({
    phone_number: z.string().min(1),
  })
  .strict();
export type WhatsAppRequestVerificationRequest = z.infer<
  typeof whatsAppRequestVerificationRequestSchema
>;

export const whatsAppRequestVerificationResponseSchema = z
  .object({
    success: z.boolean(),
    phone_number: z.string(),
    expires_in_seconds: z.number(),
    dev_code: z.string().nullable().optional(),
  })
  .passthrough();
export type WhatsAppRequestVerificationResponse = z.infer<
  typeof whatsAppRequestVerificationResponseSchema
>;

export const whatsAppVerifyCodeRequestSchema = z
  .object({
    phone_number: z.string().min(1),
    code: z.string().min(4),
  })
  .strict();
export type WhatsAppVerifyCodeRequest = z.infer<typeof whatsAppVerifyCodeRequestSchema>;
