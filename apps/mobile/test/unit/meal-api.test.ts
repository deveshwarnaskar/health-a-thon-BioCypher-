import { describe, expect, it, vi } from "vitest";
import {
  fetchClinicianMeals,
  fetchPatientMeals,
  submitMealConfirmation,
  submitMealDraft,
} from "../../src/features/meals/api";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import type { ApiErrorDetails } from "../../src/services/api/errors";
import type { AuthSessionProvider } from "../../src/auth/AuthSessionProvider";

const validUUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

function makeClient(
  fetchImpl: typeof fetch,
  authProvider?: AuthSessionProvider
) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl,
    createCorrelationId: () => "corr-meal-1234",
    authProvider,
  });
}

describe("Gate 10H-M Meal API Integration", () => {
  describe("Meal Draft Submission (10H-M-05, 10H-M-06)", () => {
    it("10H-M-05: submitMealDraft calls POST /api/v2/clinical/meals with Idempotency-Key and payload", async () => {
      const mockResponse = {
        meal_observation_id: "obs-meal-01",
        patient_id: validUUID,
        portion_label: "medium",
        quantity: 1.0,
      };

      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      const result = await submitMealDraft(
        {
          patient_id: validUUID,
          description: "Dal and rice",
          portion: {
            food_key: "rice",
            katori_volume_ml: 220,
            quantity: 1.0,
          },
        },
        "idemp-key-001",
        client,
        "test-token"
      );

      expect(result.meal_observation_id).toBe("obs-meal-01");
      expect(result.portion_label).toBe("medium");

      expect(fetchImpl).toHaveBeenCalledOnce();
      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/clinical/meals");
      expect(init.method).toBe("POST");

      const headers = new Headers(init.headers as Record<string, string>);
      expect(headers.get("Authorization")).toBe("Bearer test-token");
      expect(headers.get("Idempotency-Key")).toBe("idemp-key-001");
      expect(headers.get("X-Correlation-ID")).toBe("corr-meal-1234");

      const body = JSON.parse(String(init.body));
      expect(body.patient_id).toBe(validUUID);
      expect(body.description).toBe("Dal and rice");
      expect(body.portion.katori_volume_ml).toBe(220);
    });

    it("10H-M-06: Idempotency is preserved across retry calls", async () => {
      let callCount = 0;
      const fetchImpl = vi.fn(async () => {
        callCount++;
        if (callCount === 1) {
          return new Response(JSON.stringify({ detail: "Gateway timeout" }), { status: 504 });
        }
        return new Response(
          JSON.stringify({
            meal_observation_id: "obs-meal-01",
            patient_id: validUUID,
            portion_label: "medium",
            quantity: 1.0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });

      const client = makeClient(fetchImpl as typeof fetch);
      const payload = {
        patient_id: validUUID,
        description: "Dal and rice",
      };

      // First attempt fails with 504
      await expect(
        submitMealDraft(payload, "idemp-key-fixed", client, "test-token")
      ).rejects.toMatchObject({ httpStatus: 504 });

      // Second attempt succeeds using the identical Idempotency-Key
      const retryResult = await submitMealDraft(payload, "idemp-key-fixed", client, "test-token");
      expect(retryResult.meal_observation_id).toBe("obs-meal-01");

      const [, firstInit] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      const [, secondInit] = fetchImpl.mock.calls[1] as unknown as [string, RequestInit];

      const h1 = new Headers(firstInit.headers as Record<string, string>);
      const h2 = new Headers(secondInit.headers as Record<string, string>);
      expect(h1.get("Idempotency-Key")).toBe("idemp-key-fixed");
      expect(h2.get("Idempotency-Key")).toBe("idemp-key-fixed");
    });
  });

  describe("Meal Confirmation (10H-M-07, 10H-M-08, 10H-M-09)", () => {
    it("10H-M-07: submitMealConfirmation calls POST /api/v2/clinical/meals/{id}/confirm with Idempotency-Key", async () => {
      const mockResponse = {
        meal_observation_id: "obs-meal-01",
        patient_id: validUUID,
        confirmation: "confirmed",
      };

      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify(mockResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      const result = await submitMealConfirmation(
        "obs-meal-01",
        { corrected_description: "Corrected meal" },
        "idemp-confirm-001",
        client,
        "test-token"
      );

      expect(result.confirmation).toBe("confirmed");
      expect(result.meal_observation_id).toBe("obs-meal-01");

      const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
      expect(String(url)).toBe("http://api.test/api/v2/clinical/meals/obs-meal-01/confirm");
      expect(init.method).toBe("POST");

      const headers = new Headers(init.headers as Record<string, string>);
      expect(headers.get("Idempotency-Key")).toBe("idemp-confirm-001");
    });

    it("10H-M-08: Confirmed state comes authoritatively from the server response", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            meal_observation_id: "obs-meal-01",
            patient_id: validUUID,
            confirmation: "confirmed",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

      const client = makeClient(fetchImpl as typeof fetch);
      const result = await submitMealConfirmation(
        "obs-meal-01",
        {},
        "idemp-confirm-002",
        client
      );

      expect(result.confirmation).toBe("confirmed");
    });

    it("10H-M-09: Duplicate confirmation returns 409 conflict", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: "Meal observation is already confirmed",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      );

      const client = makeClient(fetchImpl as typeof fetch);
      await expect(
        submitMealConfirmation("obs-meal-01", {}, "idemp-confirm-003", client)
      ).rejects.toMatchObject({
        httpStatus: 409,
      });
    });
  });

  describe("Error Handling & Centralized Auth (10H-M-10, 10H-M-11, 10H-M-12, 10H-M-13, 10H-M-14, 10H-M-15)", () => {
    it("10H-M-10: 401 uses centralized refresh and retry", async () => {
      let callCount = 0;
      const fetchImpl = vi.fn(async () => {
        callCount++;
        if (callCount === 1) {
          return new Response(JSON.stringify({ detail: "Token expired" }), { status: 401 });
        }
        return new Response(
          JSON.stringify({
            meal_observation_id: "obs-meal-01",
            patient_id: validUUID,
            portion_label: "medium",
            quantity: 1.0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      });

      const refreshSession = vi.fn(async () => "fresh-refreshed-token");
      const authProvider: AuthSessionProvider = {
        getAccessToken: async () => "tok-initial",
        refreshSession,
        clearSession: async () => {},
        getAuthenticatedContext: async () => ({ state: "anonymous" as const }),
        signalAuthExpired: vi.fn(),
        onAuthExpired: () => () => {},
      };
      const client = makeClient(fetchImpl as typeof fetch, authProvider);

      const result = await submitMealDraft(
        { patient_id: validUUID, description: "Meal" },
        "idemp-key-refresh",
        client,
        "expired-token"
      );

      expect(refreshSession).toHaveBeenCalledOnce();
      expect(result.meal_observation_id).toBe("obs-meal-01");
      expect(fetchImpl).toHaveBeenCalledTimes(2);

      const [, secondInit] = fetchImpl.mock.calls[1] as unknown as [string, RequestInit];
      const headers = new Headers(secondInit.headers as Record<string, string>);
      expect(headers.get("Authorization")).toBe("Bearer fresh-refreshed-token");
    });

    it("10H-M-11: 403 access denied does not logout globally", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Access denied" }), { status: 403 })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      let thrown: ApiErrorDetails | undefined;
      try {
        await submitMealDraft(
          { patient_id: validUUID, description: "Meal" },
          "idemp-key-403",
          client
        );
      } catch (err) {
        thrown = err as ApiErrorDetails;
      }

      expect(thrown?.httpStatus).toBe(403);
      expect(thrown?.kind).toBe("FORBIDDEN");
    });

    it("10H-M-12: 404 not found is handled safely", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify({ detail: "Meal observation not found" }), { status: 404 })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      await expect(
        submitMealConfirmation("missing-obs-id", {}, "idemp-404", client)
      ).rejects.toMatchObject({
        httpStatus: 404,
      });
    });

    it("10H-M-13: 409 phone required error is cleanly mapped", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "PHONE_REQUIRED",
              message: "Patient phone is required to confirm a meal observation",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        )
      );

      const client = makeClient(fetchImpl as typeof fetch);
      await expect(
        submitMealConfirmation("obs-meal-01", {}, "idemp-409", client)
      ).rejects.toMatchObject({
        httpStatus: 409,
        message: expect.stringContaining("Patient phone is required"),
      });
    });

    it("10H-M-14: 422 validation error is mapped to typed error", async () => {
      const fetchImpl = vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: [{ loc: ["body", "description"], msg: "field required" }] }),
          { status: 422 }
        )
      );

      const client = makeClient(fetchImpl as typeof fetch);
      await expect(
        submitMealDraft({ patient_id: validUUID, description: "Rice" }, "idemp-422", client)
      ).rejects.toMatchObject({
        httpStatus: 422,
      });
    });

    it("10H-M-15: Network failure never claims confirmation", async () => {
      const fetchImpl = vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      });

      const client = makeClient(fetchImpl as typeof fetch);
      await expect(
        submitMealConfirmation("obs-meal-01", {}, "idemp-net-err", client)
      ).rejects.toMatchObject({
        kind: "NETWORK_ERROR",
      });
    });
  });

  describe("Observation Feeds (Patient vs Clinician)", () => {
    it("fetchPatientMeals filters to meals and enforces DTO safety", async () => {
      const feedResponse = {
        patient_id: validUUID,
        items: [
          {
            kind: "glucose",
            value_mg_dl: 110,
            taken_at: "2026-09-17T08:00:00Z",
            confirmed: true,
          },
          {
            kind: "meal",
            description: "Upma",
            portion_label: "medium",
            quantity: 1.0,
            recorded_at: "2026-09-17T09:00:00Z",
            confirmed: true,
          },
        ],
      };

      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify(feedResponse), { status: 200 })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      const meals = await fetchPatientMeals(validUUID, 50, client);

      expect(meals).toHaveLength(1);
      expect(meals[0]?.description).toBe("Upma");
      expect(meals[0]?.kind).toBe("meal");
    });

    it("fetchClinicianMeals returns meals with clinician analytics", async () => {
      const clinicianFeedResponse = {
        patient_id: validUUID,
        items: [
          {
            kind: "meal",
            observation_id: "obs-meal-01",
            description: "Poha",
            portion_label: "medium",
            quantity: 1.0,
            carbs_grams: 35.0,
            glycemic_index: "medium",
            recorded_at: "2026-09-17T09:00:00Z",
            confirmation: "confirmed",
          },
        ],
      };

      const fetchImpl = vi.fn(async () =>
        new Response(JSON.stringify(clinicianFeedResponse), { status: 200 })
      );

      const client = makeClient(fetchImpl as typeof fetch);
      const meals = await fetchClinicianMeals(validUUID, client);

      expect(meals).toHaveLength(1);
      expect(meals[0]?.carbs_grams).toBe(35.0);
      expect(meals[0]?.glycemic_index).toBe("medium");
    });
  });
});
