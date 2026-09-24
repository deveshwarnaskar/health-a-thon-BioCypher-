import React, { createContext, useContext, useState, useMemo, useCallback } from "react";
import { useCaregiverPatients } from "../useCaregiverPatients";
import type { CaregiverPatientListItem } from "../../../services/schemas/caregiver";

export type CaregiverContextValue = {
  linkedPatients: CaregiverPatientListItem[];
  activePatientId: string | null;
  activePatient: CaregiverPatientListItem | null;

  isLoading: boolean;
  isError: boolean;

  selectPatient: (patientId: string) => void;
  clearActivePatient: () => void;
  refreshPatients: () => Promise<unknown>;
};

const CaregiverContext = createContext<CaregiverContextValue | null>(null);

export type CaregiverProviderProps = {
  children: React.ReactNode;
  initialPatientId?: string | null;
};

export function CaregiverProvider({ children, initialPatientId }: CaregiverProviderProps) {
  const { patients, isLoading, isError, refetch } = useCaregiverPatients();
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(initialPatientId ?? null);
  const [isExplicitlyCleared, setIsExplicitlyCleared] = useState(false);

  // Active patient ID: derived state adhering to React 19 / Compiler purity rules.
  // Case A: zero patients or explicitly cleared -> null
  // Case B: patient previously selected -> return ID if still authorized, otherwise null (never silently switch)
  // Case C: initial load with no prior selection -> default to first authorized patient
  const activePatientId = useMemo(() => {
    if (isExplicitlyCleared || !patients || patients.length === 0) {
      return null;
    }
    if (selectedPatientId) {
      return patients.some((p) => p.patient_id === selectedPatientId) ? selectedPatientId : null;
    }
    return patients[0]?.patient_id ?? null;
  }, [patients, selectedPatientId, isExplicitlyCleared]);

  const selectPatient = useCallback(
    (patientId: string) => {
      // Must be present in authoritative linkedPatients
      const found = patients.find((p) => p.patient_id === patientId);
      if (found) {
        setIsExplicitlyCleared(false);
        setSelectedPatientId(patientId);
      }
    },
    [patients]
  );

  const clearActivePatient = useCallback(() => {
    setIsExplicitlyCleared(true);
    setSelectedPatientId(null);
  }, []);

  const activePatient = useMemo(() => {
    if (!activePatientId || !patients) return null;
    return patients.find((p) => p.patient_id === activePatientId) ?? null;
  }, [activePatientId, patients]);

  const value = useMemo<CaregiverContextValue>(
    () => ({
      linkedPatients: patients ?? [],
      activePatientId,
      activePatient,
      isLoading,
      isError,
      selectPatient,
      clearActivePatient,
      refreshPatients: refetch,
    }),
    [patients, activePatientId, activePatient, isLoading, isError, selectPatient, clearActivePatient, refetch]
  );

  return <CaregiverContext.Provider value={value}>{children}</CaregiverContext.Provider>;
}

export function useCaregiverContext(): CaregiverContextValue {
  const context = useContext(CaregiverContext);
  if (!context) {
    throw new Error("useCaregiverContext must be used within a CaregiverProvider");
  }
  return context;
}
