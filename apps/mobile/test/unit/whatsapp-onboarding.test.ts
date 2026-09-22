import { describe, expect, it } from "vitest";
import {
  whatsAppConnectionStatusSchema,
  whatsAppIdentityResponseSchema,
  whatsAppRequestVerificationRequestSchema,
  whatsAppRequestVerificationResponseSchema,
  whatsAppVerifyCodeRequestSchema,
  type WhatsAppIdentityResponse,
} from "../../src/services/schemas/whatsapp";
import { whatsAppEndpoints } from "../../src/services/api/endpoints/whatsapp";
import { en } from "../../src/i18n/translations/en";
import { hi } from "../../src/i18n/translations/hi";
import { bn } from "../../src/i18n/translations/bn";
import { ta } from "../../src/i18n/translations/ta";
import { te } from "../../src/i18n/translations/te";
import { mr } from "../../src/i18n/translations/mr";

describe("WhatsApp Onboarding & Identity Lifecycle (Gate 10P)", () => {
  describe("WhatsApp Connection Status Schema", () => {
    it("accepts canonical status values: connected, not_connected, pending, failed", () => {
      expect(whatsAppConnectionStatusSchema.parse("connected")).toBe("connected");
      expect(whatsAppConnectionStatusSchema.parse("not_connected")).toBe("not_connected");
      expect(whatsAppConnectionStatusSchema.parse("pending")).toBe("pending");
      expect(whatsAppConnectionStatusSchema.parse("failed")).toBe("failed");
    });

    it("rejects invalid status values", () => {
      expect(() => whatsAppConnectionStatusSchema.parse("active")).toThrow();
      expect(() => whatsAppConnectionStatusSchema.parse("linked")).toThrow();
      expect(() => whatsAppConnectionStatusSchema.parse("")).toThrow();
    });
  });

  describe("WhatsApp Identity Response Schema", () => {
    it("parses valid unconnected response", () => {
      const unconnected = {
        status: "not_connected",
        phone_number: null,
        phone_number_masked: null,
        verified_at: null,
        capabilities: ["health_logging", "food_logging", "voice_messages"],
      };
      const parsed = whatsAppIdentityResponseSchema.parse(unconnected);
      expect(parsed.status).toBe("not_connected");
      expect(parsed.phone_number).toBeNull();
      expect(parsed.capabilities).toContain("health_logging");
    });

    it("parses valid connected response with masked phone", () => {
      const connected: WhatsAppIdentityResponse = {
        status: "connected",
        phone_number: "+919876543210",
        phone_number_masked: "+********3210",
        verified_at: "2026-09-21T10:00:00Z",
        capabilities: ["health_logging", "food_logging", "voice_messages"],
      };
      const parsed = whatsAppIdentityResponseSchema.parse(connected);
      expect(parsed.status).toBe("connected");
      expect(parsed.phone_number).toBe("+919876543210");
      expect(parsed.phone_number_masked).toBe("+********3210");
      expect(parsed.capabilities.length).toBe(3);
    });

    it("rejects unexpected properties when strict", () => {
      const payload = {
        status: "connected",
        capabilities: [],
        forbidden_field: "injected",
      };
      expect(() => whatsAppIdentityResponseSchema.parse(payload)).toThrow();
    });
  });

  describe("WhatsApp Request Verification Request & Response Schemas", () => {
    it("validates phone number in request", () => {
      expect(
        whatsAppRequestVerificationRequestSchema.parse({
          phone_number: "+919876543210",
        })
      ).toEqual({ phone_number: "+919876543210" });

      expect(() =>
        whatsAppRequestVerificationRequestSchema.parse({ phone_number: "" })
      ).toThrow();
    });

    it("validates request verification response with dev_code", () => {
      const response = {
        success: true,
        phone_number: "+919876543210",
        expires_in_seconds: 600,
        dev_code: "654321",
      };
      const parsed = whatsAppRequestVerificationResponseSchema.parse(response);
      expect(parsed.success).toBe(true);
      expect(parsed.dev_code).toBe("654321");
      expect(parsed.expires_in_seconds).toBe(600);
    });
  });

  describe("WhatsApp Verify Code Request Schema", () => {
    it("validates 6-digit code and phone number", () => {
      const valid = {
        phone_number: "+919876543210",
        code: "654321",
      };
      expect(whatsAppVerifyCodeRequestSchema.parse(valid)).toEqual(valid);
    });

    it("rejects short or empty codes", () => {
      expect(() =>
        whatsAppVerifyCodeRequestSchema.parse({
          phone_number: "+919876543210",
          code: "12",
        })
      ).toThrow();
    });
  });

  describe("WhatsApp API Endpoints Definition", () => {
    it("configures GET identity correctly", () => {
      expect(whatsAppEndpoints.getIdentity.method).toBe("GET");
      expect(whatsAppEndpoints.getIdentity.path).toBe("/api/v2/whatsapp/identity");
      expect(whatsAppEndpoints.getIdentity.requiresIdempotencyKey).toBe(false);
    });

    it("configures POST requestVerification correctly", () => {
      expect(whatsAppEndpoints.requestVerification.method).toBe("POST");
      expect(whatsAppEndpoints.requestVerification.path).toBe(
        "/api/v2/whatsapp/identity/request-verification"
      );
    });

    it("configures POST verifyCode correctly", () => {
      expect(whatsAppEndpoints.verifyCode.method).toBe("POST");
      expect(whatsAppEndpoints.verifyCode.path).toBe(
        "/api/v2/whatsapp/identity/verify-code"
      );
    });

    it("configures POST disconnect correctly", () => {
      expect(whatsAppEndpoints.disconnect.method).toBe("POST");
      expect(whatsAppEndpoints.disconnect.path).toBe(
        "/api/v2/whatsapp/identity/disconnect"
      );
    });
  });

  describe("Internationalization (i18n) Completeness", () => {
    const locales = [
      { name: "en", dict: en },
      { name: "hi", dict: hi },
      { name: "bn", dict: bn },
      { name: "ta", dict: ta },
      { name: "te", dict: te },
      { name: "mr", dict: mr },
    ];

    const requiredKeys = [
      "modalTitle",
      "modalSubtitle",
      "benefit1",
      "benefit2",
      "benefit3",
      "connectButton",
      "maybeLaterButton",
      "homeReminderTitle",
      "homeReminderSubtitle",
      "homeConnectAction",
      "flowStep1Title",
      "flowStep1Subtitle",
      "phoneLabel",
      "sendOtpButton",
      "flowStep2Title",
      "flowStep2Subtitle",
      "codeLabel",
      "verifyButton",
      "resendButton",
      "flowStep3Title",
      "flowStep3Subtitle",
      "doneButton",
      "settingsSectionTitle",
      "connectedStatus",
      "notConnectedStatus",
      "connectedDesc",
      "notConnectedDesc",
      "manageButton",
      "manageTitle",
      "linkedNumberLabel",
      "connectedSinceLabel",
      "supportedFeaturesTitle",
      "featureHealthLogging",
      "featureFoodLogging",
      "featureVoiceNotes",
      "disconnectButton",
      "disconnectConfirmTitle",
      "disconnectConfirmMessage",
      "confirmDisconnect",
      "cancel",
      "statusUnavailableOffline",
    ] as const;

    for (const { name, dict } of locales) {
      it(`contains all required WhatsApp keys for locale '${name}'`, () => {
        expect(dict.whatsapp).toBeDefined();
        for (const key of requiredKeys) {
          expect(dict.whatsapp[key], `Missing key '${key}' in locale '${name}'`).toBeTruthy();
          expect(typeof dict.whatsapp[key]).toBe("string");
        }
      });
    }
  });
});
