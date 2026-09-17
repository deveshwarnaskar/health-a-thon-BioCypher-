import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  AuditEvent,
  AuditEventListResponseSchema,
} from "../contracts";
import { Table, Column } from "../components/Table";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Select } from "../components/Select";
import { Badge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { Alert } from "../components/Alert";

export const AuditPage: React.FC = () => {
  const [actorIdFilter, setActorIdFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const [resourceFilter, setResourceFilter] = useState("all");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [viewingEvent, setViewingEvent] = useState<AuditEvent | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [
      "admin",
      "audit",
      actorIdFilter,
      actionFilter,
      resourceFilter,
      startTime,
      endTime,
    ],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit: 100 };
      if (actorIdFilter.trim()) params.actor_id = actorIdFilter.trim();
      if (actionFilter !== "all") params.action = actionFilter;
      if (resourceFilter !== "all") params.resource_type = resourceFilter;
      if (startTime) params.start_time = new Date(startTime).toISOString();
      if (endTime) params.end_time = new Date(endTime).toISOString();

      return api.get("/api/v2/admin/audit-events", AuditEventListResponseSchema, {
        params,
      });
    },
  });

  const columns: Column<AuditEvent>[] = [
    {
      key: "occurred_at",
      header: "Timestamp",
      render: (e) => (
        <span className="text-xs font-mono text-gray-600">
          {new Date(e.occurred_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "actor_id",
      header: "Actor",
      render: (e) => (
        <div>
          <span className="font-mono text-xs font-medium text-gray-900">{e.actor_id}</span>
          <div className="text-[10px] text-gray-500 uppercase">{e.actor_type}</div>
        </div>
      ),
    },
    {
      key: "action",
      header: "Action",
      render: (e) => (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-gray-100 text-gray-800 border border-gray-200">
          {e.action}
        </span>
      ),
    },
    {
      key: "resource_type",
      header: "Resource Type",
      render: (e) => (
        <span className="text-xs text-gray-700 font-medium">
          {e.resource_type}
        </span>
      ),
    },
    {
      key: "outcome",
      header: "Outcome",
      render: (e) => (
        <Badge
          status={e.outcome === "SUCCESS" ? "success" : "error"}
          label={e.outcome}
        />
      ),
    },
    {
      key: "actions",
      header: "Details",
      className: "text-right",
      render: (e) => (
        <Button
          size="sm"
          variant="outline"
          onClick={() => setViewingEvent(e)}
          aria-label={`View audit event ${e.audit_event_id}`}
        >
          Inspect
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Audit Trail</h1>
          <p className="mt-1 text-sm text-gray-500">
            Immutable, append-only security log recording all administrative and platform events.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <Button variant="outline" onClick={() => refetch()}>
            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Log
          </Button>
        </div>
      </div>

      {error && (
        <Alert
          type="error"
          title="Failed to load audit events"
          message={error instanceof Error ? error.message : "Network error"}
        />
      )}

      {/* Filter Controls */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm space-y-4">
        <div className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Filter Audit Events
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <Input
            label="Actor ID (UUID)"
            placeholder="Filter by actor UUID..."
            value={actorIdFilter}
            onChange={(e) => setActorIdFilter(e.target.value)}
          />

          <Select
            label="Action"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            options={[
              { value: "all", label: "All Actions" },
              { value: "CREATE", label: "CREATE" },
              { value: "UPDATE", label: "UPDATE" },
              { value: "REVOKE", label: "REVOKE" },
              { value: "READ", label: "READ" },
              { value: "LOGIN", label: "LOGIN" },
            ]}
          />

          <Select
            label="Resource Type"
            value={resourceFilter}
            onChange={(e) => setResourceFilter(e.target.value)}
            options={[
              { value: "all", label: "All Resources" },
              { value: "facility", label: "facility" },
              { value: "care_team.member", label: "care_team.member" },
              { value: "patient.provision", label: "patient.provision" },
              { value: "identity_mapping", label: "identity_mapping" },
              { value: "admin.patient", label: "admin.patient" },
              { value: "auth.verify", label: "auth.verify" },
            ]}
          />

          <Input
            type="datetime-local"
            label="Start Time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
          />

          <Input
            type="datetime-local"
            label="End Time"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
          />
        </div>

        {(actorIdFilter || actionFilter !== "all" || resourceFilter !== "all" || startTime || endTime) && (
          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={() => {
                setActorIdFilter("");
                setActionFilter("all");
                setResourceFilter("all");
                setStartTime("");
                setEndTime("");
              }}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* Audit Table */}
      <Table
        columns={columns as Column<Record<string, unknown>>[]}
        data={(data ?? []) as unknown as Record<string, unknown>[]}
        isLoading={isLoading}
        emptyMessage="No audit records match the selected filters."
        ariaLabel="Audit trail table"
      />

      {/* Event Inspection Modal */}
      {viewingEvent && (
        <Modal
          isOpen={true}
          onClose={() => setViewingEvent(null)}
          title="Audit Event Inspection"
          description="Read-only immutable audit record details."
        >
          <div className="space-y-4">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 bg-gray-50 p-4 rounded-md border border-gray-200 text-xs">
              <div>
                <dt className="text-gray-500 font-medium">Event ID</dt>
                <dd className="font-mono text-gray-900 font-semibold">{viewingEvent.audit_event_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Occurred At</dt>
                <dd className="font-mono text-gray-900">
                  {new Date(viewingEvent.occurred_at).toLocaleString()}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Actor ID</dt>
                <dd className="font-mono text-gray-900">{viewingEvent.actor_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Actor Type</dt>
                <dd className="font-mono text-gray-900">{viewingEvent.actor_type}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Action</dt>
                <dd className="font-mono font-semibold text-gray-900">{viewingEvent.action}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Resource Type</dt>
                <dd className="font-mono text-gray-900">{viewingEvent.resource_type}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Resource ID</dt>
                <dd className="font-mono text-gray-900">{viewingEvent.resource_id || "None"}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Outcome</dt>
                <dd className="mt-0.5">
                  <Badge
                    status={viewingEvent.outcome === "SUCCESS" ? "success" : "error"}
                    label={viewingEvent.outcome}
                  />
                </dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Source IP</dt>
                <dd className="font-mono text-gray-900">{viewingEvent.source_ip || "—"}</dd>
              </div>
              <div>
                <dt className="text-gray-500 font-medium">Correlation ID</dt>
                <dd className="font-mono text-gray-900 truncate" title={viewingEvent.correlation_id}>
                  {viewingEvent.correlation_id || "—"}
                </dd>
              </div>
              {viewingEvent.reason && (
                <div className="sm:col-span-2">
                  <dt className="text-gray-500 font-medium">Reason / Detail</dt>
                  <dd className="text-gray-900 mt-0.5">{viewingEvent.reason}</dd>
                </div>
              )}
            </dl>

            <div className="flex justify-end pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setViewingEvent(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
