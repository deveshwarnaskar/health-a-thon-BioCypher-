import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as SecureStore from "expo-secure-store";
import { apiClient } from "../../services/api/client";
import { whatsAppEndpoints } from "../../services/api/endpoints/whatsapp";
import { useConnectivity } from "../../connectivity/useConnectivity";
import type {
  WhatsAppIdentityResponse,
  WhatsAppRequestVerificationResponse,
} from "../../services/schemas/whatsapp";

export const WHATSAPP_QUERY_KEY = ["whatsapp-identity"] as const;

export function useWhatsAppIdentity(options?: { enabled?: boolean }) {
  const { isOnline, isOffline } = useConnectivity();

  const query = useQuery<WhatsAppIdentityResponse>({
    queryKey: WHATSAPP_QUERY_KEY,
    queryFn: async () => {
      return apiClient.request<WhatsAppIdentityResponse>({
        method: whatsAppEndpoints.getIdentity.method,
        path: whatsAppEndpoints.getIdentity.path,
        schema: whatsAppEndpoints.getIdentity.responseSchema,
      });
    },
    enabled: (options?.enabled ?? true) && isOnline,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    ...query,
    isOffline,
  };
}

export function useRequestWhatsAppVerification() {
  return useMutation<
    WhatsAppRequestVerificationResponse,
    Error,
    { phoneNumber: string }
  >({
    mutationFn: async ({ phoneNumber }) => {
      return apiClient.request<WhatsAppRequestVerificationResponse>({
        method: whatsAppEndpoints.requestVerification.method,
        path: whatsAppEndpoints.requestVerification.path,
        schema: whatsAppEndpoints.requestVerification.responseSchema,
        body: { phone_number: phoneNumber },
      });
    },
  });
}

export function useVerifyWhatsAppCode() {
  const queryClient = useQueryClient();

  return useMutation<
    WhatsAppIdentityResponse,
    Error,
    { phoneNumber: string; code: string }
  >({
    mutationFn: async ({ phoneNumber, code }) => {
      return apiClient.request<WhatsAppIdentityResponse>({
        method: whatsAppEndpoints.verifyCode.method,
        path: whatsAppEndpoints.verifyCode.path,
        schema: whatsAppEndpoints.verifyCode.responseSchema,
        body: { phone_number: phoneNumber, code },
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(WHATSAPP_QUERY_KEY, data);
      queryClient.invalidateQueries({ queryKey: WHATSAPP_QUERY_KEY });
    },
  });
}

export function useDisconnectWhatsApp() {
  const queryClient = useQueryClient();

  return useMutation<WhatsAppIdentityResponse, Error, void>({
    mutationFn: async () => {
      return apiClient.request<WhatsAppIdentityResponse>({
        method: whatsAppEndpoints.disconnect.method,
        path: whatsAppEndpoints.disconnect.path,
        schema: whatsAppEndpoints.disconnect.responseSchema,
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(WHATSAPP_QUERY_KEY, data);
      queryClient.invalidateQueries({ queryKey: WHATSAPP_QUERY_KEY });
    },
  });
}

// ─── Local Dismissal / Seen State Persistence ─────────────────────────────────

const MEMORY_DISMISSED = new Set<string>();

export function useWhatsAppOnboardingSeen(userId: string | undefined) {
  const [isDismissed, setIsDismissed] = useState<boolean>(() =>
    userId ? MEMORY_DISMISSED.has(userId) : false
  );
  const [isLoaded, setIsLoaded] = useState<boolean>(() =>
    !userId || (userId ? MEMORY_DISMISSED.has(userId) : false)
  );

  useEffect(() => {
    if (!userId || MEMORY_DISMISSED.has(userId)) {
      return;
    }

    let active = true;
    (async () => {
      try {
        const val = await SecureStore.getItemAsync(
          `@thali:wa_onboarding_dismissed:${userId}`
        );
        if (active) {
          if (val === "true") {
            MEMORY_DISMISSED.add(userId);
            setIsDismissed(true);
          }
          setIsLoaded(true);
        }
      } catch {
        if (active) setIsLoaded(true);
      }
    })();

    return () => {
      active = false;
    };
  }, [userId]);

  const dismiss = async () => {
    setIsDismissed(true);
    if (!userId) return;
    MEMORY_DISMISSED.add(userId);
    try {
      await SecureStore.setItemAsync(
        `@thali:wa_onboarding_dismissed:${userId}`,
        "true"
      );
    } catch {
      // Best-effort storage
    }
  };

  return { isDismissed, isLoaded, dismiss };
}
