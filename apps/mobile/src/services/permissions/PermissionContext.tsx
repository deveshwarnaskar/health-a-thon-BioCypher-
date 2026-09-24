import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { AppState, type AppStateStatus } from "react-native";
import {
  areAllPermissionsGranted,
  checkAllPermissions,
  getMissingPermissions,
  hasCompletedInitialPrompt,
  openAppSettings,
  requestAllPermissions as serviceRequestAllPermissions,
  requestPermission as serviceRequestPermission,
  resetAllPermissionData,
  setCompletedInitialPrompt,
} from "./permissionService";
import {
  INITIAL_PERMISSION_STATE,
  type PermissionState,
  type PermissionStatus,
  type PermissionType,
} from "./types";
import { CompactPermissionModal } from "../../components/permissions/CompactPermissionModal";

export interface PermissionContextValue {
  state: PermissionState;
  isInitialInstall: boolean;
  isChecking: boolean;
  areAllGranted: boolean;
  missingPermissions: PermissionType[];
  showPrompt: () => void;
  requestAll: () => Promise<PermissionState>;
  requestSingle: (type: PermissionType) => Promise<PermissionStatus>;
  openSettings: () => Promise<void>;
  recheck: () => Promise<void>;
  resetPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextValue | null>(null);

export interface PermissionProviderProps {
  children: React.ReactNode;
  /**
   * Current authenticated user actor ID to isolate permission prompts per account.
   */
  userId?: string;
  /**
   * For testing or controlled environments: override whether initial prompt has completed.
   */
  initialCompletedOverride?: boolean;
}

export function PermissionProvider({
  children,
  userId,
  initialCompletedOverride,
}: PermissionProviderProps) {
  const [permissionState, setPermissionState] = useState<PermissionState>(
    INITIAL_PERMISSION_STATE
  );
  const [isInitialInstall, setIsInitialInstall] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [showInitialModal, setShowInitialModal] = useState(false);
  const [showSubsequentModal, setShowSubsequentModal] = useState(false);
  const [dismissedForSession, setDismissedForSession] = useState(false);

  const performCheck = useCallback(async () => {
    setIsChecking(true);
    try {
      const isCompleted =
        initialCompletedOverride !== undefined
          ? initialCompletedOverride
          : await hasCompletedInitialPrompt(userId);

      const current = await checkAllPermissions();
      setPermissionState(current);

      const allGranted = areAllPermissionsGranted(current);

      if (__DEV__) {
        console.log("[Permissions] performCheck:", {
          userId,
          isCompleted,
          allGranted,
          current,
          dismissedForSession,
        });
      }

      if (!isCompleted) {
        setIsInitialInstall(true);
        setShowInitialModal(true);
        setShowSubsequentModal(false);
      } else {
        setIsInitialInstall(false);
        setShowInitialModal(false);
        if (!allGranted && !dismissedForSession) {
          setShowSubsequentModal(true);
        } else if (allGranted) {
          setShowSubsequentModal(false);
        }
      }
    } finally {
      setIsChecking(false);
    }
  }, [initialCompletedOverride, dismissedForSession, userId]);

  // Initial check on mount or when user changes
  useEffect(() => {
    let active = true;

    void (async () => {
      const isCompleted =
        initialCompletedOverride !== undefined
          ? initialCompletedOverride
          : await hasCompletedInitialPrompt(userId);

      const current = await checkAllPermissions();
      if (!active) return;

      setPermissionState(current);
      const allGranted = areAllPermissionsGranted(current);

      if (__DEV__) {
        console.log("[Permissions] Mount check:", {
          userId,
          isCompleted,
          allGranted,
          current,
        });
      }

      if (!isCompleted) {
        setIsInitialInstall(true);
        setShowInitialModal(true);
        setShowSubsequentModal(false);
      } else {
        setIsInitialInstall(false);
        setShowInitialModal(false);
        if (!allGranted && !dismissedForSession) {
          setShowSubsequentModal(true);
        } else if (allGranted) {
          setShowSubsequentModal(false);
        }
      }
      setIsChecking(false);
    })();

    return () => {
      active = false;
    };
  }, [initialCompletedOverride, dismissedForSession, userId]);

  // AppState listener: When returning from device Settings, auto-refresh permissions
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === "active") {
        void checkAllPermissions().then((updated) => {
          setPermissionState(updated);
          if (areAllPermissionsGranted(updated)) {
            setShowInitialModal(false);
            setShowSubsequentModal(false);
          }
        });
      }
    };

    const subscription = AppState.addEventListener("change", handleAppStateChange);
    return () => {
      subscription.remove();
    };
  }, []);

  const handleRequestAll = useCallback(async (): Promise<PermissionState> => {
    const updated = await serviceRequestAllPermissions(userId);
    setPermissionState(updated);
    await setCompletedInitialPrompt(true, userId);
    setIsInitialInstall(false);

    if (areAllPermissionsGranted(updated)) {
      setShowInitialModal(false);
      setShowSubsequentModal(false);
    }
    return updated;
  }, [userId]);

  const handleRequestSingle = useCallback(
    async (type: PermissionType): Promise<PermissionStatus> => {
      const res = await serviceRequestPermission(type);
      const updated = await checkAllPermissions();
      setPermissionState(updated);

      // In subsequent prompt mode, if all remaining permissions are granted, close modal
      if (!isInitialInstall && areAllPermissionsGranted(updated)) {
        setShowSubsequentModal(false);
      }
      return res;
    },
    [isInitialInstall]
  );

  const handleInitialModalComplete = useCallback(async () => {
    await setCompletedInitialPrompt(true, userId);
    setIsInitialInstall(false);
    setShowInitialModal(false);

    // If permissions are still missing after initial onboarding,
    // future app uses will trigger the subsequent prompt.
    const current = await checkAllPermissions();
    setPermissionState(current);
  }, [userId]);

  const handleDismissForSession = useCallback(() => {
    setDismissedForSession(true);
    setShowSubsequentModal(false);
  }, []);

  const handleManualShowPrompt = useCallback(() => {
    setShowSubsequentModal(true);
  }, []);

  const handleResetPermissions = useCallback(async () => {
    await resetAllPermissionData(userId);
    setDismissedForSession(false);
    setIsInitialInstall(true);
    setShowInitialModal(true);
    setShowSubsequentModal(false);
    const current = await checkAllPermissions();
    setPermissionState(current);
  }, [userId]);

  const allGranted = useMemo(
    () => areAllPermissionsGranted(permissionState),
    [permissionState]
  );
  const missing = useMemo(
    () => getMissingPermissions(permissionState),
    [permissionState]
  );

  const value = useMemo<PermissionContextValue>(
    () => ({
      state: permissionState,
      isInitialInstall,
      isChecking,
      areAllGranted: allGranted,
      missingPermissions: missing,
      showPrompt: handleManualShowPrompt,
      requestAll: handleRequestAll,
      requestSingle: handleRequestSingle,
      openSettings: openAppSettings,
      recheck: performCheck,
      resetPermissions: handleResetPermissions,
    }),
    [
      permissionState,
      isInitialInstall,
      isChecking,
      allGranted,
      missing,
      handleManualShowPrompt,
      handleRequestAll,
      handleRequestSingle,
      performCheck,
      handleResetPermissions,
    ]
  );

  return (
    <PermissionContext.Provider value={value}>
      {children}

      {/* 1st time install: compact, dark, non-scrollable, 1-at-a-time modal after user signs in */}
      <CompactPermissionModal
        key={`initial-${showInitialModal}`}
        visible={showInitialModal}
        isInitial={true}
        permissionsToAsk={["notifications", "microphone", "camera"]}
        state={permissionState}
        onRequestPermission={handleRequestSingle}
        onOpenSettings={openAppSettings}
        onFinish={handleInitialModalComplete}
      />

      {/* Subsequent app use: compact, dark, non-scrollable, 1-at-a-time modal for missing permissions */}
      <CompactPermissionModal
        key={`subsequent-${missing.join("-")}-${showSubsequentModal}`}
        visible={showSubsequentModal}
        isInitial={false}
        permissionsToAsk={missing}
        state={permissionState}
        onRequestPermission={handleRequestSingle}
        onOpenSettings={openAppSettings}
        onFinish={handleDismissForSession}
      />
    </PermissionContext.Provider>
  );
}

export function usePermissions(): PermissionContextValue {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error("usePermissions must be used within a PermissionProvider");
  }
  return context;
}
