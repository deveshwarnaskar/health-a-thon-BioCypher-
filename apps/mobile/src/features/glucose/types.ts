export {
  READING_TAGS,
  READING_TAG_LABELS,
  type ReadingTag,
  type GlucoseFormInput,
  type PatientGlucoseObservation,
  type IngestGlucoseRequest,
  type IngestGlucoseResponse,
} from "../../services/schemas/clinical";

export const glucoseKeys = {
  all: ["clinical"] as const,
  observations: () => ["clinical", "observations"] as const,
  feed: (patientId: string) => ["clinical", "observations", patientId] as const,
};
