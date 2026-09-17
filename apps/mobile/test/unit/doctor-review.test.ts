import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../src/services/api/client";
import { readApiConfig } from "../../src/services/api/config";
import type { ApiErrorDetails } from "../../src/services/api/errors";
import { aiEndpoints } from "../../src/services/api/endpoints/ai";
import { clinicalEndpoints } from "../../src/services/api/endpoints/clinical";
import {
  fetchArtifactDetail,
  fetchClinicianFeed,
  fetchReviewQueue,
  submitArtifactReview,
} from "../../src/features/doctor/api";
import type { ClinicianObservationFeedResponse } from "../../src/services/schemas/clinical";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers });
}

function makeClient(fetchImpl: typeof fetch, resolved?: (res: () => unknown) => void) {
  return new ApiClient({
    config: readApiConfig({ EXPO_PUBLIC_API_BASE_URL: "http://api.test", ...process.env }),
    fetchImpl,
  });
}

const QUEUE_BODY = {
  artifact_count: 2,
  items: [
    {
      artifact_id: "art-1",
      patient_id: "p-1",
      artifact_kind: "meal_review",
      state: "PENDING_REVIEW",
      summary: "AI summary for patient p-1.",
      created_at: "2026-09-17T10:00:00Z",
    },
    {
      artifact_id: "art-2",
      patient_id: "p-2",
      artifact_kind: "glucose_review",
      state: "PENDING_REVIEW",
      summary: "AI summary for patient p-2.",
      created_at: "2026-09-17T10:05:00Z",
    },
  ],
};

const FEED_BODY: ClinicianObservationFeedResponse = {
  patient_id: "p-1",
  items: [
    {
      kind: "glucose",
      observation_id: "obs-1",
      value_mg_dl: 118,
      tag: "fasting",
      taken_at: "2026-09-17T08:00:00Z",
      confirmation: "confirmed",
    },
    {
      kind: "meal",
      observation_id: "obs-2",
      description: "Rice and dal",
      portion_label: "plate",
      quantity: 1,
      carbs_grams: 55,
      glycemic_index: "medium",
      recorded_at: "2026-09-17T09:00:00Z",
      confirmation: "confirmed",
    },
  ],
};

describe("doctor AI-review endpoints (Gate 10F-B → Gate 10F-M)", () => {
  it("fetches the PENDING_REVIEW queue via GET /api/v2/clinical/ai-artifacts", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, QUEUE_BODY));
    const client = makeClient(fetchImpl);

    const queue = await fetchReviewQueue(client, "tok-1");

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test/api/v2/clinical/ai-artifacts");
    expect(init.method).toBe("GET");
    expect(new Headers(init.headers as Record<string, string>).get("Authorization")).toBe("Bearer tok-1");
    expect(queue.artifact_count).toBe(2);
    expect(queue.items[0]!.artifact_id).toBe("art-1");
    expect(init.body).toBeUndefined();
  });

  it("rejects a queue body that violates the sealed DTO (CLIENT_CONTRACT_MISMATCH)", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { items: [] }));
    const client = makeClient(fetchImpl);

    const error = await fetchReviewQueue(client).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(error?.code).toBe("CLIENT_CONTRACT_MISMATCH");
  });

  it("fetches one artifact via GET /api/v2/clinical/ai-artifacts/{artifact_id}", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, QUEUE_BODY.items[0]));
    const client = makeClient(fetchImpl);

    const artifact = await fetchArtifactDetail("art-1", client);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test" + aiEndpoints.detail.path("art-1"));
    expect(artifact.artifact_id).toBe("art-1");
    expect(artifact.state).toBe("PENDING_REVIEW");
  });

  it("submits a review POST with body + Idempotency-Key to /review", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { artifact_id: "art-1", state: "APPROVED", reviewed_by_user_id: "u-1" }),
    );
    const client = makeClient(fetchImpl);

    const result = await submitArtifactReview(
      "art-1",
      { decision: "approve", edited_summary: null },
      "key-abc",
      client,
    );

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe("http://api.test" + aiEndpoints.review.path("art-1"));
    expect(init.method).toBe("POST");
    const headerMap = new Headers(init.headers as Record<string, string>);
    expect(headerMap.get("Idempotency-Key")).toBe("key-abc");
    expect(JSON.parse(String(init.body))).toEqual({ decision: "approve", edited_summary: null });
    expect(result.state).toBe("APPROVED");
  });

  it("maps a 403 review denial to FORBIDDEN / insufficient_capability (never a logout)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(403, { error: { code: "REVIEW_UNAUTHORIZED", message: "Clinician review not authorized." } }),
    );
    const client = makeClient(fetchImpl);

    const error = await submitArtifactReview("art-1", { decision: "reject", edited_summary: null }, "key-1", client).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(error?.httpStatus).toBe(403);
    expect(error?.kind).toBe("FORBIDDEN");
    expect(error?.forbiddenReason).toBe("insufficient_capability");
  });

  it("maps 409 conflict and 429 rate-limit (Retry-After) for review submits", async () => {
    const fetches = [
      jsonResponse(409, { error: { code: "INVALID_STATE", message: "Artifact is not PENDING_REVIEW." } }),
      jsonResponse(429, { error: { code: "RATE_LIMITED", message: "Slow down." } }, { "Retry-After": "37" }),
    ];
    let call = 0;
    const client = makeClient(vi.fn(async () => fetches[call++]) as typeof fetch);

    const conflict = await submitArtifactReview("art-1", { decision: "approve" }, "key-2", client).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(conflict?.httpStatus).toBe(409);
    expect(conflict?.conflictSubtype).toBe("INVALID_STATE");

    const limited = await submitArtifactReview("art-1", { decision: "approve" }, "key-2", client).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(limited?.httpStatus).toBe(429);
    expect(limited?.retryAfterSeconds).toBe(37);
  });
});

describe("doctor clinician-observation feed (Gate 10F-M)", () => {
  it("fetches the clinician feed for one patient with patient_id + limit", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, FEED_BODY));
    const client = makeClient(fetchImpl);

    const feed = await fetchClinicianFeed("p-1", 50, client);

    const [url] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toBe(
      "http://api.test" + clinicalEndpoints.clinicianFeed.path + "?patient_id=p-1&limit=50",
    );
    expect(feed.items).toHaveLength(2);
    expect(feed.items[1]).toMatchObject({ carbs_grams: 55, glycemic_index: "medium" });
  });

  it("rejects a patient-shaped feed (no clinician lifecycle markers)", async () => {
    const patientShaped = {
      patient_id: "p-1",
      items: [
        {
          kind: "glucose",
          value_mg_dl: 118,
          taken_at: "2026-09-17T08:00:00Z",
          confirmed: true,
        },
      ],
    };
    const fetchImpl = vi.fn(async () => jsonResponse(200, patientShaped));
    const client = makeClient(fetchImpl);

    const error = await fetchClinicianFeed("p-1", 50, client).then(
      () => null,
      (err) => err as ApiErrorDetails,
    );
    expect(error).toBeTruthy();
  });
});