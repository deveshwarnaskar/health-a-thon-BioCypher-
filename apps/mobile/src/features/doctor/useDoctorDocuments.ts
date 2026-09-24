import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPatientDocuments, uploadPatientDocument, type ClinicalDocumentItem } from "./api";
import { doctorKeys } from "./doctorKeys";

export function useDoctorDocuments(patientId: string, options?: { enabled?: boolean }) {
  const queryClient = useQueryClient();

  const query = useQuery<ClinicalDocumentItem[]>({
    queryKey: doctorKeys.documents(patientId),
    queryFn: () => fetchPatientDocuments(patientId),
    enabled: Boolean(patientId) && (options?.enabled ?? true),
    staleTime: 30_000,
  });

  const uploadMutation = useMutation({
    mutationFn: (request: {
      filename: string;
      mime_type: string;
      content_base64: string;
      kind?: string;
    }) => {
      const idempotencyKey = `doc-upload-${patientId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      return uploadPatientDocument(patientId, request, idempotencyKey);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: doctorKeys.documents(patientId) });
    },
  });

  return {
    documents: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    uploadDocument: uploadMutation.mutateAsync,
    isUploading: uploadMutation.isPending,
  };
}
