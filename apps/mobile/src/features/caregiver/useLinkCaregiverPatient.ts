import { useMutation, useQueryClient } from "@tanstack/react-query";
import { linkCaregiverPatient } from "./api";
import { caregiverKeys } from "./useCaregiverPatients";
import type {
  CaregiverPatientListItem,
  LinkCaregiverPatientRequest,
} from "../../services/schemas/caregiver";

export function useLinkCaregiverPatient(options?: {
  onSuccess?: (patient: CaregiverPatientListItem) => void;
  onError?: (error: unknown) => void;
}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: LinkCaregiverPatientRequest) => linkCaregiverPatient(request),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: caregiverKeys.patients() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}
