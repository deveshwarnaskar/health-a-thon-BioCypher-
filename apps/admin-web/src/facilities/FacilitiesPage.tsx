import React, { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  Facility,
  FacilityListResponseSchema,
  FacilitySchema,
  CreateFacilityRequestSchema,
  UpdateFacilityRequestSchema,
} from "../contracts";
import { Table, Column } from "../components/Table";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";

export const FacilitiesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingFacility, setEditingFacility] = useState<Facility | null>(null);
  const [deactivatingFacility, setDeactivatingFacility] = useState<Facility | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form states
  const [createName, setCreateName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  // Queries
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "facilities"],
    queryFn: () => api.get("/api/v2/admin/facilities", FacilityListResponseSchema, { params: { limit: 100 } }),
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      CreateFacilityRequestSchema.parse({ name });
      return api.post("/api/v2/admin/facilities", FacilitySchema, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "facilities"] });
      setIsCreateOpen(false);
      setCreateName("");
      setCreateError(null);
    },
    onError: (err: Error) => {
      setCreateError(err.message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      UpdateFacilityRequestSchema.parse({ name });
      return api.patch(`/api/v2/admin/facilities/${id}`, FacilitySchema, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "facilities"] });
      setEditingFacility(null);
      setEditName("");
      setEditError(null);
    },
    onError: (err: Error) => {
      setEditError(err.message);
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.post(`/api/v2/admin/facilities/${id}/deactivate`, FacilitySchema);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "facilities"] });
      setDeactivatingFacility(null);
    },
    onError: (err: Error) => {
      setErrorMessage(err.message);
    },
  });

  // Filter facilities by name or id
  const filteredFacilities = useMemo(() => {
    if (!data?.items) return [];
    if (!searchTerm.trim()) return data.items;
    const lower = searchTerm.toLowerCase();
    return data.items.filter(
      (f) =>
        f.name.toLowerCase().includes(lower) ||
        f.facility_id.toLowerCase().includes(lower),
    );
  }, [data?.items, searchTerm]);

  const columns: Column<Facility>[] = [
    {
      key: "name",
      header: "Facility Name",
      render: (f) => (
        <div>
          <div className="font-semibold text-gray-900">{f.name}</div>
          <div className="text-xs font-mono text-gray-400">{f.facility_id}</div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (f) => (
        <Badge status={f.active ? "active" : "inactive"} label={f.active ? "Active" : "Inactive"} />
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (f) => (
        <span className="text-xs text-gray-500">
          {new Date(f.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (f) => (
        <div className="flex justify-end space-x-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setEditingFacility(f);
              setEditName(f.name);
              setEditError(null);
            }}
            aria-label={`Edit ${f.name}`}
          >
            Edit
          </Button>
          {f.active && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setDeactivatingFacility(f)}
              aria-label={`Deactivate ${f.name}`}
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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Facilities</h1>
          <p className="mt-1 text-sm text-gray-500">
            Provision and administer clinical facility centers belonging to this tenant.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Button
            variant="primary"
            onClick={() => {
              setIsCreateOpen(true);
              setCreateError(null);
            }}
          >
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create Facility
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
          title="Failed to load facilities"
          message={error instanceof Error ? error.message : "Network error"}
        />
      )}

      {/* Filter and Search */}
      <div className="flex items-center space-x-4">
        <div className="max-w-md w-full">
          <Input
            label="Search facilities"
            placeholder="Search by facility name or ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* Facilities Table */}
      <Table
        columns={columns as Column<Record<string, unknown>>[]}
        data={filteredFacilities as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        emptyMessage={searchTerm ? "No facilities match your search." : "No facilities registered yet."}
        ariaLabel="Facilities directory table"
      />

      {/* Create Facility Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Facility"
        description="Register a new operational facility for this tenant. Tenant assignment is automatic."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!createName.trim()) {
              setCreateError("Facility name is required.");
              return;
            }
            createMutation.mutate(createName.trim());
          }}
          className="space-y-4"
        >
          <Input
            label="Facility Name"
            placeholder="e.g. City Health Clinic"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            error={createError || undefined}
            required
            autoFocus
          />
          <div className="flex justify-end space-x-3 pt-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={createMutation.isPending}
            >
              Create Facility
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Facility Modal */}
      {editingFacility && (
        <Modal
          isOpen={true}
          onClose={() => setEditingFacility(null)}
          title={`Edit Facility: ${editingFacility.name}`}
          description="Update the facility display name."
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!editName.trim()) {
                setEditError("Facility name cannot be empty.");
                return;
              }
              updateMutation.mutate({
                id: editingFacility.facility_id,
                name: editName.trim(),
              });
            }}
            className="space-y-4"
          >
            <Input
              label="Facility Name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              error={editError || undefined}
              required
              autoFocus
            />
            <div className="flex justify-end space-x-3 pt-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditingFacility(null)}
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

      {/* Deactivate Facility Confirmation Modal */}
      {deactivatingFacility && (
        <Modal
          isOpen={true}
          onClose={() => setDeactivatingFacility(null)}
          title="Deactivate Facility"
          description={`Are you sure you want to deactivate ${deactivatingFacility.name}? This will mark the facility inactive. Existing clinical records remain intact.`}
        >
          <div className="space-y-4">
            <Alert
              type="warning"
              message="Deactivation immediately revokes new patient and care-team assignments to this facility."
            />
            <div className="flex justify-end space-x-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeactivatingFacility(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                isLoading={deactivateMutation.isPending}
                onClick={() => deactivateMutation.mutate(deactivatingFacility.facility_id)}
              >
                Deactivate Facility
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
