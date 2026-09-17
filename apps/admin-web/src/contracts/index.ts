import { z } from "zod";

// ============================================================================
// 1. Auth Contract (Gate 07 / 09)
// ============================================================================

export const AuthVerifyResponseSchema = z
  .object({
    actor_id: z.string(),
    tenant_id: z.string(),
    roles: z.array(z.string()),
    facility_id: z.string().nullable().optional(),
  })
  .strict();

export type AuthVerifyResponse = z.infer<typeof AuthVerifyResponseSchema>;

// ============================================================================
// 2. Facilities Contracts (Gate 10K-B)
// ============================================================================

export const FacilitySchema = z
  .object({
    facility_id: z.string(),
    name: z.string().min(1).max(255),
    active: z.boolean(),
    created_at: z.string(),
  })
  .strict();

export type Facility = z.infer<typeof FacilitySchema>;

export const FacilityListResponseSchema = z
  .object({
    total: z.number().int().nonnegative(),
    items: z.array(FacilitySchema),
  })
  .strict();

export type FacilityListResponse = z.infer<typeof FacilityListResponseSchema>;

export const CreateFacilityRequestSchema = z
  .object({
    name: z.string().min(1, "Facility name is required").max(255),
  })
  .strict();

export type CreateFacilityRequest = z.infer<typeof CreateFacilityRequestSchema>;

export const UpdateFacilityRequestSchema = z
  .object({
    name: z.string().min(1).max(255).optional(),
    active: z.boolean().optional(),
  })
  .strict();

export type UpdateFacilityRequest = z.infer<typeof UpdateFacilityRequestSchema>;

// ============================================================================
// 3. Care Team Contracts (Gate 10H-B / 10K-B)
// ============================================================================

export const CanonicalCareTeamRoles = [
  "doctor",
  "nurse",
  "care_coordinator",
  "dietitian",
  "field_health_worker",
] as const;

export const CareTeamRoleEnum = z.enum(CanonicalCareTeamRoles);
export type CareTeamRole = z.infer<typeof CareTeamRoleEnum>;

export const CareTeamMemberSchema = z
  .object({
    member_id: z.string(),
    user_id: z.string(),
    role: z.string(),
    display_name: z.string().min(1).max(255),
    facility_id: z.string().nullable().optional(),
    active: z.boolean(),
  })
  .strict();

export type CareTeamMember = z.infer<typeof CareTeamMemberSchema>;

export const CareTeamMemberListResponseSchema = z
  .object({
    total: z.number().int().nonnegative(),
    items: z.array(CareTeamMemberSchema),
  })
  .strict();

export type CareTeamMemberListResponse = z.infer<
  typeof CareTeamMemberListResponseSchema
>;

export const ProvisionCareTeamMemberRequestSchema = z
  .object({
    user_id: z.string().uuid("Must be a valid UUID"),
    role: CareTeamRoleEnum,
    display_name: z.string().min(1, "Display name is required").max(255),
    facility_id: z.string().uuid("Must be a valid facility UUID"),
  })
  .strict();

export type ProvisionCareTeamMemberRequest = z.infer<
  typeof ProvisionCareTeamMemberRequestSchema
>;

export const UpdateCareTeamMemberRequestSchema = z
  .object({
    role: CareTeamRoleEnum.optional(),
    display_name: z.string().min(1).max(255).optional(),
    facility_id: z.string().uuid("Must be a valid facility UUID").optional(),
    active: z.boolean().optional(),
  })
  .strict();

export type UpdateCareTeamMemberRequest = z.infer<
  typeof UpdateCareTeamMemberRequestSchema
>;

// ============================================================================
// 4. Admin Patient Directory Contracts (Gate 10K-B - strictly PHI-minimized)
// ============================================================================

export const FORBIDDEN_CLINICAL_FIELDS = [
  "glucose",
  "meal",
  "meals",
  "carbohydrates",
  "carbs_grams",
  "glycemic_index",
  "medication",
  "medications",
  "prescription",
  "prescriptions",
  "ai_review",
  "ai_artifacts",
  "risk",
  "risk_score",
  "diagnosis",
  "observations",
  "clinical_notes",
  "clinical_trends",
] as const;

export function assertNoClinicalFields(data: unknown): void {
  if (!data || typeof data !== "object") return;
  if (Array.isArray(data)) {
    for (const item of data) {
      assertNoClinicalFields(item);
    }
    return;
  }
  const obj = data as Record<string, unknown>;
  for (const forbidden of FORBIDDEN_CLINICAL_FIELDS) {
    if (forbidden in obj) {
      throw new Error(
        `CRITICAL SECURITY VIOLATION: Forbidden clinical field '${forbidden}' detected in administrative patient DTO!`,
      );
    }
  }
  for (const value of Object.values(obj)) {
    if (value && typeof value === "object") {
      assertNoClinicalFields(value);
    }
  }
}

export const AdminPatientSchema = z
  .object({
    patient_id: z.string(),
    uh_id: z.string(),
    name: z.string(),
    facility_id: z.string().nullable().optional(),
    phone: z.string().nullable().optional(),
    active: z.boolean(),
    has_active_mapping: z.boolean(),
    created_at: z.string(),
  })
  .strict();

export type AdminPatient = z.infer<typeof AdminPatientSchema>;

export const AdminPatientListResponseSchema = z
  .object({
    total: z.number().int().nonnegative(),
    items: z.array(AdminPatientSchema),
  })
  .strict();

export type AdminPatientListResponse = z.infer<
  typeof AdminPatientListResponseSchema
>;

export const ProvisionPatientRequestSchema = z
  .object({
    name: z.string().min(1, "Patient name is required").max(255),
    facility_id: z.string().uuid("Must be a valid facility UUID").optional().nullable(),
    uh_id: z.string().max(64).optional().nullable(),
    phone: z.string().max(32).optional().nullable(),
  })
  .strict();

export type ProvisionPatientRequest = z.infer<
  typeof ProvisionPatientRequestSchema
>;

// ============================================================================
// 5. Identity Mappings Contracts (Gate 08 / Gate 10K-B)
// ============================================================================

export const IdentityMappingSchema = z
  .object({
    mapping_id: z.string(),
    user_id: z.string(),
    patient_id: z.string(),
    active: z.boolean(),
    created_at: z.string(),
  })
  .strict();

export type IdentityMapping = z.infer<typeof IdentityMappingSchema>;

export const IdentityMappingListResponseSchema = z.array(IdentityMappingSchema);
export type IdentityMappingListResponse = z.infer<
  typeof IdentityMappingListResponseSchema
>;

export const CreateIdentityMappingRequestSchema = z
  .object({
    user_id: z.string().uuid("Must be a valid user UUID"),
    patient_id: z.string().uuid("Must be a valid patient UUID"),
  })
  .strict();

export type CreateIdentityMappingRequest = z.infer<
  typeof CreateIdentityMappingRequestSchema
>;

// ============================================================================
// 6. Audit Trail Contracts (Gate 09 / Gate 10K-B)
// ============================================================================

export const AuditEventSchema = z
  .object({
    audit_event_id: z.string(),
    tenant_id: z.string(),
    actor_id: z.string(),
    actor_type: z.string(),
    action: z.string(),
    resource_type: z.string(),
    resource_id: z.string().nullable().optional(),
    occurred_at: z.string(),
    correlation_id: z.string().optional().default(""),
    source_ip: z.string().nullable().optional(),
    outcome: z.string(),
    reason: z.string().nullable().optional(),
  })
  .strict();

export type AuditEvent = z.infer<typeof AuditEventSchema>;

export const AuditEventListResponseSchema = z.array(AuditEventSchema);
export type AuditEventListResponse = z.infer<typeof AuditEventListResponseSchema>;

// ============================================================================
// 7. Error Contracts
// ============================================================================

export const ApiErrorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).optional(),
});

export type ApiErrorDetail = z.infer<typeof ApiErrorDetailSchema>;

export const ApiErrorResponseSchema = z.object({
  error: ApiErrorDetailSchema,
});

export type ApiErrorResponse = z.infer<typeof ApiErrorResponseSchema>;
