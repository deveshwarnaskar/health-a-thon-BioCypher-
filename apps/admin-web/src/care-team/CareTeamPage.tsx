import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  CareTeamMember,
  CareTeamMemberListResponseSchema,
  CareTeamMemberSchema,
  ProvisionCareTeamMemberRequestSchema,
  UpdateCareTeamMemberRequestSchema,
  FacilityListResponseSchema,
  CanonicalCareTeamRoles,
  CareTeamRole,
} from "../contracts";
import { Table, Column } from "../components/Table";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";

export const CareTeamPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [facilityFilter, setFacilityFilter] = useState<string>("all");
  const [isProvisionOpen, setIsProvisionOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<CareTeamMember | null>(null);
  const [deactivatingMember, setDeactivatingMember] = useState<CareTeamMember | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Provision Form State
  const [provUserId, setProvUserId] = useState("");
  const [provName, setProvName] = useState("");
  const [provRole, setProvRole] = useState<CareTeamRole>("doctor");
  const [provFacilityId, setProvFacilityId] = useState("");
  const [provErrors, setProvErrors] = useState<Record<string, string>>({});

  // Edit Form State
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState<CareTeamRole>("doctor");
  const [editFacilityId, setEditFacilityId] = useState("");
  const [editErrors, setEditErrors] = useState<Record<string, string>>({});

  // Queries
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "care-team"],
    queryFn: () =>
      api.get("/api/v2/admin/care-team-members", CareTeamMemberListResponseSchema, {
        params: { limit: 100 },
      }),
  });

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

  // Mutations
  const provisionMutation = useMutation({
    mutationFn: async (payload: {
      user_id: string;
      role: CareTeamRole;
      display_name: string;
      facility_id: string;
    }) => {
      ProvisionCareTeamMemberRequestSchema.parse(payload);
      return api.post("/api/v2/admin/care-team-members", CareTeamMemberSchema, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "care-team"] });
      setIsProvisionOpen(false);
      setProvUserId("");
      setProvName("");
      setProvFacilityId("");
      setProvErrors({});
    },
    onError: (err: Error) => {
      setProvErrors({ form: err.message });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: { display_name?: string; role?: CareTeamRole; facility_id?: string };
    }) => {
      UpdateCareTeamMemberRequestSchema.parse(payload);
      return api.patch(`/api/v2/admin/care-team-members/${id}`, CareTeamMemberSchema, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "care-team"] });
      setEditingMember(null);
      setEditErrors({});
    },
    onError: (err: Error) => {
      setEditErrors({ form: err.message });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.post(`/api/v2/admin/care-team-members/${id}/deactivate`, CareTeamMemberSchema);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "care-team"] });
      setDeactivatingMember(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Filter care team
  const filteredMembers = useMemo(() => {
    if (!data?.items) return [];
    return data.items.filter((m) => {
      if (roleFilter !== "all" && m.role !== roleFilter) return false;
      if (facilityFilter !== "all" && m.facility_id !== facilityFilter) return false;
      if (!searchTerm.trim()) return true;
      const lower = searchTerm.toLowerCase();
      return (
        m.display_name.toLowerCase().includes(lower) ||
        m.user_id.toLowerCase().includes(lower) ||
        m.role.toLowerCase().includes(lower)
      );
    });
  }, [data?.items, roleFilter, facilityFilter, searchTerm]);

  const columns: Column<CareTeamMember>[] = [
    {
      key: "display_name",
      header: "Clinician",
      render: (m) => (
        <div>
          <div className="font-semibold text-gray-900">{m.display_name}</div>
          <div className="text-xs font-mono text-gray-400">User ID: {m.user_id}</div>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      render: (m) => (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-blue-50 text-blue-700 border border-blue-200">
          {m.role}
        </span>
      ),
    },
    {
      key: "facility",
      header: "Facility",
      render: (m) => (
        <span className="text-xs text-gray-700">
          {m.facility_id ? facilityMap.get(m.facility_id) || m.facility_id : "None"}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (m) => (
        <Badge status={m.active ? "active" : "inactive"} label={m.active ? "Active" : "Deactivated"} />
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (m) => (
        <div className="flex justify-end space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setEditingMember(m);
              setEditName(m.display_name);
              setEditRole(m.role as CareTeamRole);
              setEditFacilityId(m.facility_id || "");
              setEditErrors({});
            }}
            aria-label={`Edit ${m.display_name}`}
          >
            Edit
          </Button>
          {m.active && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setDeactivatingMember(m)}
              aria-label={`Deactivate ${m.display_name}`}
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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Care Team Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Provision and manage clinician memberships (doctors, nurses, coordinators, FHWs).
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Button
            variant="primary"
            onClick={() => {
              setIsProvisionOpen(true);
              setProvErrors({});
              if (facilities.length > 0 && !provFacilityId) {
                setProvFacilityId(facilities[0]!.facility_id);
              }
            }}
          >
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Provision Member
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
          title="Failed to load care team"
          message={error instanceof Error ? error.message : "Network error"}
        />
      )}

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Input
          label="Search members"
          placeholder="Filter by name, user ID, or role..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />

        <Select
          label="Filter by Role"
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          options={[
            { value: "all", label: "All Roles" },
            ...CanonicalCareTeamRoles.map((r) => ({ value: r, label: r })),
          ]}
        />

        <Select
          label="Filter by Facility"
          value={facilityFilter}
          onChange={(e) => setFacilityFilter(e.target.value)}
          options={[
            { value: "all", label: "All Facilities" },
            ...facilities.map((f) => ({ value: f.facility_id, label: f.name })),
          ]}
        />
      </div>

      {/* Table */}
      <Table
        columns={columns as Column<Record<string, unknown>>[]}
        data={filteredMembers as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        emptyMessage="No care team members found matching your criteria."
        ariaLabel="Care team members directory"
      />

      {/* Provision Modal */}
      <Modal
        isOpen={isProvisionOpen}
        onClose={() => setIsProvisionOpen(false)}
        title="Provision Care Team Member"
        description="Introduce a new clinician membership into this tenant. Operator must provide authoritative Keycloak user_id."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const errors: Record<string, string> = {};
            if (!provUserId.trim()) errors.userId = "User ID (UUID) is required";
            if (!provName.trim()) errors.name = "Display name is required";
            if (!provFacilityId) errors.facilityId = "Facility is required";

            if (Object.keys(errors).length > 0) {
              setProvErrors(errors);
              return;
            }

            provisionMutation.mutate({
              user_id: provUserId.trim(),
              display_name: provName.trim(),
              role: provRole,
              facility_id: provFacilityId,
            });
          }}
          className="space-y-4"
        >
          {provErrors.form && <Alert type="error" message={provErrors.form} />}

          <Input
            label="Keycloak User ID (UUID)"
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            value={provUserId}
            onChange={(e) => setProvUserId(e.target.value)}
            error={provErrors.userId}
            required
            autoFocus
          />

          <Input
            label="Display Name"
            placeholder="e.g. Dr. Jane Doe"
            value={provName}
            onChange={(e) => setProvName(e.target.value)}
            error={provErrors.name}
            required
          />

          <Select
            label="Clinical Role"
            value={provRole}
            onChange={(e) => setProvRole(e.target.value as CareTeamRole)}
            options={CanonicalCareTeamRoles.map((r) => ({ value: r, label: r }))}
          />

          <Select
            label="Assigned Facility"
            value={provFacilityId}
            onChange={(e) => setProvFacilityId(e.target.value)}
            error={provErrors.facilityId}
            options={[
              { value: "", label: "-- Select Facility --" },
              ...facilities.map((f) => ({ value: f.facility_id, label: f.name })),
            ]}
            required
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
              Provision Member
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Care Team Member Modal */}
      {editingMember && (
        <Modal
          isOpen={true}
          onClose={() => setEditingMember(null)}
          title={`Edit Clinician: ${editingMember.display_name}`}
          description="Update display name, assigned role, or facility scoping."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!editName.trim()) {
                setEditErrors({ name: "Display name is required" });
                return;
              }
              updateMutation.mutate({
                id: editingMember.member_id,
                payload: {
                  display_name: editName.trim(),
                  role: editRole,
                  facility_id: editFacilityId || undefined,
                },
              });
            }}
            className="space-y-4"
          >
            {editErrors.form && <Alert type="error" message={editErrors.form} />}

            <Input
              label="Display Name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              error={editErrors.name}
              required
            />

            <Select
              label="Clinical Role"
              value={editRole}
              onChange={(e) => setEditRole(e.target.value as CareTeamRole)}
              options={CanonicalCareTeamRoles.map((r) => ({ value: r, label: r }))}
            />

            <Select
              label="Facility"
              value={editFacilityId}
              onChange={(e) => setEditFacilityId(e.target.value)}
              options={[
                { value: "", label: "-- None / Unassigned --" },
                ...facilities.map((f) => ({ value: f.facility_id, label: f.name })),
              ]}
            />

            <div className="flex justify-end space-x-3 pt-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditingMember(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                isLoading={updateMutation.isPending}
              >
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Deactivate Care Team Member Confirmation Modal */}
      {deactivatingMember && (
        <Modal
          isOpen={true}
          onClose={() => setDeactivatingMember(null)}
          title="Deactivate Care Team Member"
          description={`Are you sure you want to deactivate ${deactivatingMember.display_name} (${deactivatingMember.role})?`}
        >
          <div className="space-y-4">
            <Alert
              type="warning"
              message="Deactivated clinicians immediately lose clinical operational access to this tenant. Historical tasks and care logs are preserved."
            />
            <div className="flex justify-end space-x-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeactivatingMember(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                isLoading={deactivateMutation.isPending}
                onClick={() => deactivateMutation.mutate(deactivatingMember.member_id)}
              >
                Deactivate Member
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
