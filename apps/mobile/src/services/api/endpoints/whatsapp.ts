import {
  whatsAppIdentityResponseSchema,
  whatsAppRequestVerificationResponseSchema,
  whatsAppRequestVerificationRequestSchema,
  whatsAppVerifyCodeRequestSchema,
  type WhatsAppIdentityResponse,
  type WhatsAppRequestVerificationRequest,
  type WhatsAppRequestVerificationResponse,
  type WhatsAppVerifyCodeRequest,
} from "../../schemas/whatsapp";
import type { EndpointDefinition } from "./types";

export const whatsAppEndpoints = {
  getIdentity: {
    method: "GET",
    path: "/api/v2/whatsapp/identity",
    requiresIdempotencyKey: false,
    responseSchema: whatsAppIdentityResponseSchema,
  } satisfies EndpointDefinition<WhatsAppIdentityResponse, undefined>,

  requestVerification: {
    method: "POST",
    path: "/api/v2/whatsapp/identity/request-verification",
    requiresIdempotencyKey: false,
    requestSchema: whatsAppRequestVerificationRequestSchema,
    responseSchema: whatsAppRequestVerificationResponseSchema,
  } satisfies EndpointDefinition<
    WhatsAppRequestVerificationResponse,
    WhatsAppRequestVerificationRequest
  >,

  verifyCode: {
    method: "POST",
    path: "/api/v2/whatsapp/identity/verify-code",
    requiresIdempotencyKey: false,
    requestSchema: whatsAppVerifyCodeRequestSchema,
    responseSchema: whatsAppIdentityResponseSchema,
  } satisfies EndpointDefinition<
    WhatsAppIdentityResponse,
    WhatsAppVerifyCodeRequest
  >,

  disconnect: {
    method: "POST",
    path: "/api/v2/whatsapp/identity/disconnect",
    requiresIdempotencyKey: false,
    responseSchema: whatsAppIdentityResponseSchema,
  } satisfies EndpointDefinition<WhatsAppIdentityResponse, undefined>,
};
