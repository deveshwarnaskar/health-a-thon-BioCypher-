import { describe, expect, it } from "vitest";
import {
  notificationStatusSchema,
  notificationResponseSchema,
  notificationListResponseSchema,
  type NotificationResponse,
} from "../../src/services/schemas/notifications";
import { buildNotificationsPath } from "../../src/services/api/endpoints/notifications";

describe("Gate 10L Notification Schemas & Client Contracts", () => {
  const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

  describe("Notification Status Schema", () => {
    it("accepts canonical status values: pending, queued, delivering, delivered, failed, cancelled", () => {
      expect(notificationStatusSchema.parse("pending")).toBe("pending");
      expect(notificationStatusSchema.parse("queued")).toBe("queued");
      expect(notificationStatusSchema.parse("delivering")).toBe("delivering");
      expect(notificationStatusSchema.parse("delivered")).toBe("delivered");
      expect(notificationStatusSchema.parse("failed")).toBe("failed");
      expect(notificationStatusSchema.parse("cancelled")).toBe("cancelled");
    });

    it("rejects invalid status values", () => {
      expect(() => notificationStatusSchema.parse("sent")).toThrow();
      expect(() => notificationStatusSchema.parse("unknown")).toThrow();
      expect(() => notificationStatusSchema.parse("")).toThrow();
    });
  });

  describe("Notification Response Schema", () => {
    const validNotif: NotificationResponse = {
      id: validUUID,
      tenant_id: validUUID,
      recipient_id: validUUID,
      recipient_phone: "+919876543210",
      patient_id: validUUID,
      notification_type: "reminder",
      channel: "WHATSAPP",
      template_name: "medication_reminder",
      template_params: {
        medication: "Metformin 500mg",
        instruction: "Take with food",
      },
      status: "delivered",
      created_at: "2026-09-17T12:00:00Z",
      scheduled_at: null,
      delivered_at: "2026-09-17T12:00:05Z",
      failed_at: null,
      failure_reason: null,
      correlation_id: validUUID,
      retry_count: 0,
    };

    it("parses valid notification response", () => {
      const parsed = notificationResponseSchema.parse(validNotif);
      expect(parsed).toEqual(validNotif);
      expect(parsed.id).toBe(validUUID);
      expect(parsed.status).toBe("delivered");
    });

    it("enforces strictness and rejects unexpected extra fields", () => {
      const extra = {
        ...validNotif,
        unknown_field: "injected",
      };
      expect(() => notificationResponseSchema.parse(extra)).toThrow();
    });

    it("parses list response", () => {
      const list = {
        total: 1,
        items: [validNotif],
      };
      const parsed = notificationListResponseSchema.parse(list);
      expect(parsed.total).toBe(1);
      expect(parsed.items.length).toBe(1);
    });
  });

  describe("Path Builder", () => {
    it("builds query path with params", () => {
      const path = buildNotificationsPath({
        patient_id: validUUID,
        status: "delivered",
        limit: 10,
        offset: 5,
      });
      expect(path).toContain(`/api/v2/notifications?`);
      expect(path).toContain(`patient_id=${validUUID}`);
      expect(path).toContain(`status=delivered`);
      expect(path).toContain(`limit=10`);
      expect(path).toContain(`offset=5`);
    });

    it("builds default path without params", () => {
      expect(buildNotificationsPath()).toBe("/api/v2/notifications");
    });
  });
});
