import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  AdminPatient,
  AdminPatientListResponseSchema,
  AdminPatientSchema,
  ProvisionPatientRequestSchema,
  FacilityListResponseSchema,
  assertNoClinicalFields,
} from "../contracts";
import { Table, Column } from "../components/Table";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";

export const PatientsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [facilityFilter, setFacilityFilter] = useState<string>("all");
  const [activeFilter, setActiveFilter] = useState<string>("all");
  const [isProvisionOpen, setIsProvisionOpen] = useState(false);
  const [viewingPatient, setViewingPatient] = useState<AdminPatient | null>(null);
  const [deactivatingPatient, setDeactivatingPatient] = useState<AdminPatient | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [provName, setProvName] = useState("");
  const [provUhId, setProvUhId] = useState("");
  const [provPhone, setProvPhone] = useState("");
  const [provFacilityId, setProvFacilityId] = useState("");
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Query facilities
  const facilitiesQuery = useQuery({
    queryKey: ["admin", "facilities"],
    queryFn: () =>
      api.get("/api/v2/admin/facilities", FacilityListResponseSchema, {
        params: { limit: 100 },
      }),
  });

  const facilityItems = facilitiesQuery.data?.items;
  const facilityMap = useMemo(() => {
    const map = new Map<string, string>();
    if (facilityItems) {
      for (const f of facilityItems) {
        map.set(f.facility_id, f.name);
      }
    }
    return map;
  }, [facilityItems]);
  const facilities = facilityItems ?? [];

  // Query patients
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "patients", facilityFilter, activeFilter],
    queryFn: async () => {
      const params: Record<string, string | number | boolean> = { limit: 100 };
      if (facilityFilter !== "all") params.facility_id = facilityFilter;
      if (activeFilter !== "all") params.active = activeFilter === "active";

      const res = await api.get("/api/v2/admin/patients", AdminPatientListResponseSchema, {
        params,
      });

      // Explicit assertion against any clinical data leakage
      assertNoClinicalFields(res);
      return res;
    },
  });

  // Provision mutation
  const provisionMutation = useMutation({
    mutationFn: async (payload: {
      name: string;
      facility_id?: string | null;
      uh_id?: string | null;
      phone?: string | null;
    }) => {
      ProvisionPatientRequestSchema.parse(payload);
      const res = await api.post("/api/v2/admin/patients", AdminPatientSchema, payload);
      assertNoClinicalFields(res);
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "patients"] });
      setIsProvisionOpen(false);
      setProvName("");
      setProvUhId("");
      setProvPhone("");
      setProvFacilityId("");
      setFormErrors({});
    },
    onError: (err: Error) => {
      setFormErrors({ form: err.message });
    },
  });

  // Deactivate mutation
  const deactivateMutation = useMutation({
    mutationFn: async (patientId: string) => {
      const res = await api.post(
        `/api/v2/admin/patients/${patientId}/deactivate`,
        AdminPatientSchema,
      );
      assertNoClinicalFields(res);
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "patients"] });
      setDeactivatingPatient(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Filter patients by search term
  const filteredPatients = useMemo(() => {
    if (!data?.items) return [];
    if (!searchTerm.trim()) return data.items;
    const lower = searchTerm.toLowerCase();
    return data.items.filter(
      (p) =>
        p.name.toLowerCase().includes(lower) ||
        p.uh_id.toLowerCase().includes(lower) ||
        p.patient_id.toLowerCase().includes(lower) ||
        (p.phone && p.phone.includes(searchTerm)),
    );
  }, [data?.items, searchTerm]);

  const columns: Column<AdminPatient>[] = [
    {
      key: "uh_id",
      header: "UHID",
      render: (p) => (
        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-800">
          {p.uh_id}
        </span>
      ),
    },
    {
      key: "name",
      header: "Patient Name",
      render: (p) => (
        <div>
          <div className="font-semibold text-gray-900">{p.name}</div>
          <div className="text-xs font-mono text-gray-400">ID: {p.patient_id}</div>
        </div>
      ),
    },
    {
      key: "facility",
      header: "Facility",
      render: (p) => (
        <span className="text-xs text-gray-700">
          {p.facility_id ? facilityMap.get(p.facility_id) || p.facility_id : "Unassigned"}
        </span>
      ),
    },
    {
      key: "phone",
      header: "Phone",
      render: (p) => (
        <span className="text-xs text-gray-600 font-mono">
          {p.phone || "—"}
        </span>
      ),
    },
    {
      key: "mapping",
      header: "Identity Mapping",
      render: (p) => (
        <Badge
          status={p.has_active_mapping ? "active" : "inactive"}
          label={p.has_active_mapping ? "Bound" : "Unmapped"}
        />
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (p) => (
        <Badge status={p.active ? "active" : "inactive"} label={p.active ? "Active" : "Deactivated"} />
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (p) => (
        <div className="flex justify-end space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setViewingPatient(p)}
            aria-label={`View details for ${p.name}`}
          >
            Details
          </Button>
          {p.active && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setDeactivatingPatient(p)}
              aria-label={`Deactivate ${p.name}`}
            >
              Deactivate
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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Patient Directory</h1>
          <p className="mt-1 text-sm text-gray-500">
            Tenant-scoped operational patient records. Strict PHI minimization enforced: non-clinical data only.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Button
            variant="primary"
            onClick={() => {
              setIsProvisionOpen(true);
              setFormErrors({});
            }}
          >
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Provision Patient
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
          title="Failed to load patient records"
          message={error instanceof Error ? error.message : "Network error"}
        />
      )}

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Search patients"
          placeholder="Filter by name, UHID, or ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <Select
          label="Facility Filter"
          value={facilityFilter}
          onChange={(e) => setFacilityFilter(e.target.value)}
          options={[
            { value: "all", label: "All Facilities" },
            ...facilities.map((f) => ({ value: f.facility_id, label: f.name })),
          ]}
        />

        <Select
          label="Status Filter"
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
          options={[
            { value: "all", label: "All Statuses" },
            { value: "active", label: "Active Only" },
            { value: "inactive", label: "Deactivated Only" },
          ]}
        />
      </div>

      {/* Table */}
      <Table
        columns={columns as Column<Record<string, unknown>>[]}
        data={filteredPatients as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        emptyMessage="No patient records match the selected filters."
        ariaLabel="Patient directory table"
      />

      {/* Provision Patient Modal */}
      <Modal
        isOpen={isProvisionOpen}
        onClose={() => setIsProvisionOpen(false)}
        title="Provision Patient Record"
        description="Register an operational patient identifier within this tenant. Only demographic and routing data is collected."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!provName.trim()) {
              setFormErrors({ name: "Patient name is required." });
              return;
            }

            provisionMutation.mutate({
              name: provName.trim(),
              uh_id: provUhId.trim() || undefined,
              phone: provPhone.trim() || undefined,
              facility_id: provFacilityId || undefined,
            });
          }}
          className="space-y-4"
        >
          {formErrors.form && <Alert type="error" message={formErrors.form} />}

          <Input
            label="Patient Full Name"
            placeholder="e.g. Ramesh Kumar"
            value={provName}
            onChange={(e) => setProvName(e.target.value)}
            error={formErrors.name}
            required
            autoFocus
          />

          <Input
            label="UHID (Universal Hospital ID)"
            placeholder="e.g. UHID-10023 (optional)"
            value={provUhId}
            onChange={(e) => setProvUhId(e.target.value)}
          />

          <Input
            label="Phone Number"
            placeholder="e.g. +919876543210 (optional)"
            value={provPhone}
            onChange={(e) => setProvPhone(e.target.value)}
          />

          <Select
            label="Assigned Facility"
            value={provFacilityId}
            onChange={(e) => setProvFacilityId(e.target.value)}
            options={[
              { value: "", label: "-- None / Unassigned --" },
              ...facilities.map((f) => ({ value: f.facility_id, label: f.name })),
            ]}
          />

          <div className="flex justify-end space-x-3 pt-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsProvisionOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={provisionMutation.isPending}
            >
              Provision Patient
            </Button>
          </div>
        </form>
      </Modal>

      {/* Patient Detail Modal (PHI-minimized inspection) */}
      {viewingPatient && (
        <Modal
          isOpen={true}
          onClose={() => setViewingPatient(null)}
          title={`Patient Record: ${viewingPatient.name}`}
          description="Operational record view. Clinical observations and health telemetry are strictly restricted from the admin console."
        >
          <div className="space-y-4">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 bg-gray-50 p-4 rounded-md border border-gray-200 text-xs">
              <div>
                <dt className="text-gray-500 font-medium">UHID</dt>
                <dd className="font-mono text-gray-900 font-semibold">{viewingPatient.uh_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Internal Patient ID</dt>
                <dd className="font-mono text-gray-900">{viewingPatient.patient_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Phone</dt>
                <dd className="font-mono text-gray-900">{viewingPatient.phone || "—"}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Facility</dt>
                <dd className="text-gray-900">
                  {viewingPatient.facility_id
                    ? facilityMap.get(viewingPatient.facility_id) || viewingPatient.facility_id
                    : "Unassigned"}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Identity Mapping Status</dt>
                <dd className="mt-0.5">
                  <Badge
                    status={viewingPatient.has_active_mapping ? "active" : "inactive"}
                    label={viewingPatient.has_active_mapping ? "Active Identity Mapping" : "No Identity Mapping"}
                  />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Account Status</dt>
                <dd className="mt-0.5">
                  <Badge
                    status={viewingPatient.active ? "active" : "inactive"}
                    label={viewingPatient.active ? "Active" : "Deactivated"}
                  />
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="text-gray-500 font-medium">Created Timestamp</dt>
                <dd className="text-gray-900 font-mono">
                  {new Date(viewingPatient.created_at).toLocaleString()}
                </dd>
              </div>
            </dl>

            <div className="flex justify-end pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setViewingPatient(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Deactivate Patient Confirmation Modal */}
      {deactivatingPatient && (
        <Modal
          isOpen={true}
          onClose={() => setDeactivatingPatient(null)}
          title="Deactivate Patient"
          description={`Are you sure you want to deactivate patient ${deactivatingPatient.name} (${deactivatingPatient.uh_id})?`}
        >
          <div className="space-y-4">
            <Alert
              type="warning"
              message="Deactivation marks the patient inactive and revokes self-access. Existing historical care tasks and records are preserved."
            />
            <div className="flex justify-end space-x-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeactivatingPatient(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                isLoading={deactivateMutation.isPending}
                onClick={() => deactivateMutation.mutate(deactivatingPatient.patient_id)}
              >
                Deactivate Patient
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
