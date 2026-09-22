import { useQuery } from "@tanstack/react-query";
import { fetchDoctorNotifications } from "./api";
import { doctorKeys } from "./doctorKeys";
import type { NotificationResponse } from "../../services/schemas/notifications";

export function useDoctorNotifications(patientId?: string, options?: { enabled?: boolean }) {
  const query = useQuery({
    queryKey: doctorKeys.notifications(patientId),
    queryFn: () => fetchDoctorNotifications(patientId),
    enabled: options?.enabled ?? true,
    staleTime: 30_000,
  });

  return {
    notifications: (query.data?.items ?? []) as NotificationResponse[],
    total: query.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
