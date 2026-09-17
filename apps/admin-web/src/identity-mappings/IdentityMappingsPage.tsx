import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  IdentityMapping,
  IdentityMappingListResponseSchema,
  IdentityMappingSchema,
  CreateIdentityMappingRequestSchema,
  AdminPatientListResponseSchema,
} from "../contracts";
import { Table, Column } from "../components/Table";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";

export const IdentityMappingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isBindOpen, setIsBindOpen] = useState(false);
  const [revokingMapping, setRevokingMapping] = useState<IdentityMapping | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Bind Form State
  const [bindUserId, setBindUserId] = useState("");
  const [bindPatientId, setBindPatientId] = useState("");
  const [bindErrors, setBindErrors] = useState<Record<string, string>>({});

  // Query mappings
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "identity-mappings"],
    queryFn: () => api.get("/api/v2/admin/identity-mappings", IdentityMappingListResponseSchema),
  });

  // Query patients for easy selection during bind
  const patientsQuery = useQuery({
    queryKey: ["admin", "patients"],
    queryFn: () =>
      api.get("/api/v2/admin/patients", AdminPatientListResponseSchema, {
        params: { limit: 100 },
      }),
  });

  const patientItems = patientsQuery.data?.items;
  const patientMap = useMemo(() => {
    const map = new Map<string, { name: string; uhid: string }>();
    if (patientItems) {
      for (const p of patientItems) {
        map.set(p.patient_id, { name: p.name, uhid: p.uh_id });
      }
    }
    return map;
  }, [patientItems]);
  const patients = patientItems ?? [];

  // Bind mutation
  const bindMutation = useMutation({
    mutationFn: async (payload: { user_id: string; patient_id: string }) => {
      CreateIdentityMappingRequestSchema.parse(payload);
      return api.post("/api/v2/admin/identity-mappings", IdentityMappingSchema, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "identity-mappings"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "patients"] });
      setIsBindOpen(false);
      setBindUserId("");
      setBindPatientId("");
      setBindErrors({});
    },
    onError: (err: Error) => {
      setBindErrors({ form: err.message });
    },
  });

  // Revoke mutation
  const revokeMutation = useMutation({
    mutationFn: async (mappingId: string) => {
      return api.post(
        `/api/v2/admin/identity-mappings/${mappingId}/deactivate`,
        IdentityMappingSchema,
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "identity-mappings"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "patients"] });
      setRevokingMapping(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Filter mappings
  const filteredMappings = useMemo(() => {
    if (!data) return [];
    return data.filter((m) => {
      if (statusFilter !== "all" && (statusFilter === "active" ? !m.active : m.active)) {
        return false;
      }
      if (!searchTerm.trim()) return true;
      const lower = searchTerm.toLowerCase();
      const patientInfo = patientMap.get(m.patient_id);
      return (
        m.user_id.toLowerCase().includes(lower) ||
        m.patient_id.toLowerCase().includes(lower) ||
        m.mapping_id.toLowerCase().includes(lower) ||
        (patientInfo &&
          (patientInfo.name.toLowerCase().includes(lower) ||
            patientInfo.uhid.toLowerCase().includes(lower)))
      );
    });
  }, [data, statusFilter, searchTerm, patientMap]);

  const columns: Column<IdentityMapping>[] = [
    {
      key: "user_id",
      header: "Keycloak User ID",
      render: (m) => (
        <div>
          <span className="font-mono text-xs font-semibold text-gray-900">{m.user_id}</span>
          <div className="text-[10px] text-gray-400 font-mono">Map ID: {m.mapping_id}</div>
        </div>
      ),
    },
    {
      key: "patient",
      header: "Bound Patient",
      render: (m) => {
        const info = patientMap.get(m.patient_id);
        return (
          <div>
            <div className="font-medium text-gray-900">
              {info ? info.name : "Patient"}
            </div>
            <div className="text-xs font-mono text-gray-500">
              {info ? info.uhid : m.patient_id}
            </div>
          </div>
        );
      },
    },
    {
      key: "status",
      header: "Mapping Status",
      render: (m) => (
        <Badge status={m.active ? "active" : "revoked"} label={m.active ? "Active" : "Revoked"} />
      ),
    },
    {
      key: "created_at",
      header: "Bound Date",
      render: (m) => (
        <span className="text-xs text-gray-500 font-mono">
          {new Date(m.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (m) => (
        <div className="flex justify-end space-x-2">
          {m.active && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setRevokingMapping(m)}
              aria-label={`Revoke mapping for user ${m.user_id}`}
            >
              Revoke Access
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Identity Mappings</h1>
          <p className="mt-1 text-sm text-gray-500">
            Authoritative bindings between platform login identities (user_id) and patient records.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Button
            variant="primary"
            onClick={() => {
              setIsBindOpen(true);
              setBindErrors({});
              if (patients.length > 0 && !bindPatientId) {
                setBindPatientId(patients[0]!.patient_id);
              }
            }}
          >
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Bind Identity
          </Button>
        </div>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <Alert
          type="error"
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      )}
      {error && (
        <Alert
          type="error"
          title="Failed to load identity mappings"
          message={error instanceof Error ? error.message : "Network error"}
        />
      )}

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Search mappings"
          placeholder="Search by User ID, Patient ID, UHID, or Name..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <Select
          label="Filter by Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          options={[
            { value: "all", label: "All Mappings" },
            { value: "active", label: "Active Bindings Only" },
            { value: "inactive", label: "Revoked Bindings Only" },
          ]}
        />
      </div>

      {/* Table */}
      <Table
        columns={columns as Column<Record<string, unknown>>[]}
        data={filteredMappings as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        emptyMessage="No identity mappings found."
        ariaLabel="Identity to patient mappings directory"
      />

      {/* Bind Identity Modal */}
      <Modal
        isOpen={isBindOpen}
        onClose={() => setIsBindOpen(false)}
        title="Bind Platform Identity to Patient"
        description="Bind an authenticated Keycloak user_id to a tenant patient record. This unlocks mobile self-service access."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const errors: Record<string, string> = {};
            if (!bindUserId.trim()) errors.userId = "Keycloak User ID (UUID) is required";
            if (!bindPatientId) errors.patientId = "Target patient record must be selected";

            if (Object.keys(errors).length > 0) {
              setBindErrors(errors);
              return;
            }

            bindMutation.mutate({
              user_id: bindUserId.trim(),
              patient_id: bindPatientId,
            });
          }}
          className="space-y-4"
        >
          {bindErrors.form && <Alert type="error" message={bindErrors.form} />}

          <Input
            label="Keycloak User ID (UUID)"
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            value={bindUserId}
            onChange={(e) => setBindUserId(e.target.value)}
            error={bindErrors.userId}
            required
            autoFocus
          />

          <Select
            label="Target Patient"
            value={bindPatientId}
            onChange={(e) => setBindPatientId(e.target.value)}
            error={bindErrors.patientId}
            options={[
              { value: "", label: "-- Select Patient --" },
              ...patients.map((p) => ({
                value: p.patient_id,
                label: `${p.name} (${p.uh_id}) ${p.has_active_mapping ? "• Currently Mapped" : ""}`,
              })),
            ]}
            required
          />

          <div className="flex justify-end space-x-3 pt-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsBindOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={bindMutation.isPending}
            >
              Create Binding
            </Button>
          </div>
        </form>
      </Modal>

      {/* Revoke Mapping Confirmation Modal */}
      {revokingMapping && (
        <Modal
          isOpen={true}
          onClose={() => setRevokingMapping(null)}
          title="Revoke Identity Mapping"
          description={`Revoke patient portal access for user ${revokingMapping.user_id}?`}
        >
          <div className="space-y-4">
            <Alert
              type="warning"
              message="Revoking this binding denies patient self-access immediately. Clinical records and observations remain intact under the tenant."
            />
            <div className="flex justify-end space-x-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRevokingMapping(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                isLoading={revokeMutation.isPending}
                onClick={() => revokeMutation.mutate(revokingMapping.mapping_id)}
              >
                Revoke Access
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
