/**
 * Contract status registry.
 *
 * "verified"  — backend contract exists and was audited in Gate 10A §6/§12.
 * "pending"   — backend endpoint is NOT mounted in HTTP v2 yet; client must
 *               not fabricate calls.
 */
export type ContractStatus = "verified" | "pending";

export type ContractDescriptor = {
  name: string;
  endpoint: string;
  status: ContractStatus;
};

export const CONTRACT_STATUS: ContractDescriptor[] = [
  { name: "AuthVerifyResponse", endpoint: "GET /api/v2/auth/verify", status: "verified" },
  {
    name: "PatientObservationFeedResponse",
    endpoint: "GET /api/v2/clinical/observations",
    status: "verified",
  },
  {
    name: "IngestGlucoseRequest/Response",
    endpoint: "POST /api/v2/clinical/observations",
    status: "verified",
  },
  {
    name: "CreateMedicationPlanRequest/Response",
    endpoint: "POST /api/v2/clinical/medication-plans",
    status: "verified",
  },
  {
    name: "ReviewAIArtifactRequest/Response",
    endpoint: "POST /api/v2/clinical/ai-artifacts/{id}/review",
    status: "verified",
  },
];

export function contractStatus(name: string): ContractStatus {
  return CONTRACT_STATUS.find((c) => c.name === name)?.status ?? "pending";
}