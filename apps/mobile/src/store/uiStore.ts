import { create } from "zustand";
import type { RoleMode } from "../authz/roles";

/**
 * Client/UI state only (Gate 10A §10 tier 2).
 *
 * STRICTLY PROHIBITED in this store: JWTs/refresh tokens, server entities
 * (patients, observations, plans, AI artifacts), form values, idempotency
 * keys. Those belong to auth storage / TanStack Query / RHF / key stores.
 */
type UiState = {
  activeRoleMode: RoleMode;
  setActiveRoleMode: (role: RoleMode) => void;

  modalKey: string | null;
  openModal: (key: string) => void;
  closeModal: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  activeRoleMode: null,
  setActiveRoleMode: (role) => set({ activeRoleMode: role }),

  modalKey: null,
  openModal: (key) => set({ modalKey: key }),
  closeModal: () => set({ modalKey: null }),
}));