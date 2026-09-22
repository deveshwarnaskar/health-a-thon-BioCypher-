import { useMutation, useQueryClient } from "@tanstack/react-query";
import { generateClinicalReport, type ClinicalDocumentItem } from "./api";
import { doctorKeys } from "./doctorKeys";

export function useGenerateReport(patientId: string) {
  const queryClient = useQueryClient();

  const mutation = useMutation<
    ClinicalDocumentItem,
    unknown,
    { report_type?: string; format?: string } | void
  >({
    mutationFn: async (params) => {
      const idempotencyKey = `report-gen-${patientId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      return generateClinicalReport(
        {
          patient_id: patientId,
          report_type: params?.report_type ?? "clinical_summary",
          format: params?.format ?? "pdf",
        },
        idempotencyKey
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: doctorKeys.documents(patientId) });
    },
  });

  return {
    generateReport: mutation.mutateAsync,
    isGenerating: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    generatedDocument: mutation.data,
    reset: mutation.reset,
  };
}
