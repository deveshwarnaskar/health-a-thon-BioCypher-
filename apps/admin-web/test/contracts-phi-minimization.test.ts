import { describe, it, expect } from "vitest";
import {
  AdminPatientSchema,
  assertNoClinicalFields,
  FORBIDDEN_CLINICAL_FIELDS,
  FacilitySchema,
  CareTeamMemberSchema,
  IdentityMappingSchema,
  AuditEventSchema,
  AuthVerifyResponseSchema,
} from "../src/contracts";

describe("Contracts & PHI Minimization", () => {
  it("strictly accepts valid PHI-minimized patient DTO", () => {
    const validPatient = {
      patient_id: "550e8400-e29b-41d4-a716-446655440000",
      uh_id: "UHID-12345",
      name: "Ramesh Kumar",
      facility_id: "550e8400-e29b-41d4-a716-446655440001",
      phone: "+919876543210",
      active: true,
      has_active_mapping: false,
      created_at: "2026-09-17T12:00:00Z",
    };

    const parsed = AdminPatientSchema.parse(validPatient);
    expect(parsed.name).toBe("Ramesh Kumar");
    expect(parsed.uh_id).toBe("UHID-12345");
  });

  it("strictly rejects any extraneous clinical fields via strict Zod schema", () => {
    const clinicalLeak = {
      patient_id: "550e8400-e29b-41d4-a716-446655440000",
      uh_id: "UHID-12345",
      name: "Ramesh Kumar",
      active: true,
      has_active_mapping: false,
      created_at: "2026-09-17T12:00:00Z",
      glucose_observations: [120, 140], // FORBIDDEN CLINICAL DATA
    };

    expect(() => AdminPatientSchema.parse(clinicalLeak)).toThrow();
  });

  it("assertNoClinicalFields detects all forbidden clinical keys", () => {
    for (const forbidden of FORBIDDEN_CLINICAL_FIELDS) {
      const payload = {
        patient_id: "550e8400-e29b-41d4-a716-446655440000",
        name: "Test",
        [forbidden]: "some-value",
      };

      expect(() => assertNoClinicalFields(payload)).toThrow(
        /CRITICAL SECURITY VIOLATION: Forbidden clinical field/,
      );
    }
  });

  it("assertNoClinicalFields inspects nested lists of records", () => {
    const nestedPayload = {
      items: [
        { patient_id: "1", name: "Clean Patient" },
        { patient_id: "2", name: "Compromised Patient", medication: "Metformin" },
      ],
    };

    expect(() => assertNoClinicalFields(nestedPayload)).toThrow(
      /CRITICAL SECURITY VIOLATION/,
    );
  });

  it("validates FacilitySchema", () => {
    const facility = {
      facility_id: "550e8400-e29b-41d4-a716-446655440000",
      name: "Main Clinic",
      active: true,
      created_at: "2026-09-17T10:00:00Z",
    };
    expect(FacilitySchema.parse(facility)).toEqual(facility);
  });

  it("validates CareTeamMemberSchema", () => {
    const member = {
      member_id: "550e8400-e29b-41d4-a716-446655440001",
      user_id: "550e8400-e29b-41d4-a716-446655440002",
      role: "doctor",
      display_name: "Dr. Sharma",
      facility_id: "550e8400-e29b-41d4-a716-446655440000",
      active: true,
    };
    expect(CareTeamMemberSchema.parse(member)).toEqual(member);
  });

  it("validates IdentityMappingSchema", () => {
    const mapping = {
      mapping_id: "550e8400-e29b-41d4-a716-446655440010",
      user_id: "550e8400-e29b-41d4-a716-446655440002",
      patient_id: "550e8400-e29b-41d4-a716-446655440000",
      active: true,
      created_at: "2026-09-17T10:00:00Z",
    };
    expect(IdentityMappingSchema.parse(mapping)).toEqual(mapping);
  });

  it("validates AuditEventSchema", () => {
    const event = {
      audit_event_id: "550e8400-e29b-41d4-a716-446655440020",
      tenant_id: "550e8400-e29b-41d4-a716-446655440000",
      actor_id: "550e8400-e29b-41d4-a716-446655440002",
      actor_type: "user",
      action: "CREATE",
      resource_type: "facility",
      resource_id: "550e8400-e29b-41d4-a716-446655440001",
      occurred_at: "2026-09-17T10:00:00Z",
      correlation_id: "corr-123",
      source_ip: "127.0.0.1",
      outcome: "SUCCESS",
      reason: null,
    };
    expect(AuditEventSchema.parse(event)).toEqual(event);
  });

  it("validates AuthVerifyResponseSchema", () => {
    const auth = {
      actor_id: "550e8400-e29b-41d4-a716-446655440002",
      tenant_id: "550e8400-e29b-41d4-a716-446655440000",
      roles: ["admin"],
      facility_id: null,
    };
    expect(AuthVerifyResponseSchema.parse(auth)).toEqual(auth);
  });
});
