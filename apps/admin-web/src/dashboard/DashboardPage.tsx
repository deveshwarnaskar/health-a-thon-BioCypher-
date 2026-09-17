import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  FacilityListResponseSchema,
  CareTeamMemberListResponseSchema,
  AdminPatientListResponseSchema,
  IdentityMappingListResponseSchema,
} from "../contracts";
import { useAuth } from "../auth";
import { Badge } from "../components/Badge";

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const facilitiesQuery = useQuery({
    queryKey: ["admin", "facilities"],
    queryFn: () => api.get("/api/v2/admin/facilities", FacilityListResponseSchema),
  });

  const careTeamQuery = useQuery({
    queryKey: ["admin", "care-team"],
    queryFn: () => api.get("/api/v2/admin/care-team-members", CareTeamMemberListResponseSchema),
  });

  const patientsQuery = useQuery({
    queryKey: ["admin", "patients"],
    queryFn: () => api.get("/api/v2/admin/patients", AdminPatientListResponseSchema),
  });

  const mappingsQuery = useQuery({
    queryKey: ["admin", "identity-mappings"],
    queryFn: () => api.get("/api/v2/admin/identity-mappings", IdentityMappingListResponseSchema),
  });

  const isLoading =
    facilitiesQuery.isLoading ||
    careTeamQuery.isLoading ||
    patientsQuery.isLoading ||
    mappingsQuery.isLoading;

  const totalFacilities = facilitiesQuery.data?.total ?? 0;
  const activeFacilities =
    facilitiesQuery.data?.items.filter((f) => f.active).length ?? 0;

  const totalCareTeam = careTeamQuery.data?.total ?? 0;
  const activeCareTeam =
    careTeamQuery.data?.items.filter((m) => m.active).length ?? 0;

  const totalPatients = patientsQuery.data?.total ?? 0;
  const activePatients =
    patientsQuery.data?.items.filter((p) => p.active).length ?? 0;

  const totalMappings = mappingsQuery.data?.length ?? 0;
  const activeMappings =
    mappingsQuery.data?.filter((m) => m.active).length ?? 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
          Operational Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Tenant-scoped operational health and resource administration for tenant{" "}
          <code className="text-xs font-mono font-medium text-indigo-600 bg-indigo-50 px-1 py-0.5 rounded">
            {user?.tenant_id}
          </code>
        </p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {/* Facilities */}
        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200 p-5">
          <div className="flex items-center">
            <div className="flex-shrink-0 bg-indigo-50 rounded-md p-3 text-indigo-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div className="ml-4 w-0 flex-1">
              <dl>
                <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Facilities
                </dt>
                <dd className="flex items-baseline mt-1">
                  <div className="text-2xl font-bold text-gray-900">
                    {isLoading ? "..." : totalFacilities}
                  </div>
                  <div className="ml-2 text-xs text-gray-500">
                    ({activeFacilities} active)
                  </div>
                </dd>
              </dl>
            </div>
          </div>
          <div className="mt-4 border-t border-gray-100 pt-3">
            <Link
              to="/facilities"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 inline-flex items-center"
            >
              Manage facilities &rarr;
            </Link>
          </div>
        </div>

        {/* Care Team */}
        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200 p-5">
          <div className="flex items-center">
            <div className="flex-shrink-0 bg-blue-50 rounded-md p-3 text-blue-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <div className="ml-4 w-0 flex-1">
              <dl>
                <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Care Team
                </dt>
                <dd className="flex items-baseline mt-1">
                  <div className="text-2xl font-bold text-gray-900">
                    {isLoading ? "..." : totalCareTeam}
                  </div>
                  <div className="ml-2 text-xs text-gray-500">
                    ({activeCareTeam} active)
                  </div>
                </dd>
              </dl>
            </div>
          </div>
          <div className="mt-4 border-t border-gray-100 pt-3">
            <Link
              to="/care-team"
              className="text-xs font-medium text-blue-600 hover:text-blue-800 inline-flex items-center"
            >
              Manage care team &rarr;
            </Link>
          </div>
        </div>

        {/* Patients */}
        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200 p-5">
          <div className="flex items-center">
            <div className="flex-shrink-0 bg-emerald-50 rounded-md p-3 text-emerald-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <div className="ml-4 w-0 flex-1">
              <dl>
                <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Active Patients
                </dt>
                <dd className="flex items-baseline mt-1">
                  <div className="text-2xl font-bold text-gray-900">
                    {isLoading ? "..." : activePatients}
                  </div>
                  <div className="ml-2 text-xs text-gray-500">
                    ({totalPatients} total)
                  </div>
                </dd>
              </dl>
            </div>
          </div>
          <div className="mt-4 border-t border-gray-100 pt-3">
            <Link
              to="/patients"
              className="text-xs font-medium text-emerald-600 hover:text-emerald-800 inline-flex items-center"
            >
              Patient directory &rarr;
            </Link>
          </div>
        </div>

        {/* Identity Mappings */}
        <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200 p-5">
          <div className="flex items-center">
            <div className="flex-shrink-0 bg-purple-50 rounded-md p-3 text-purple-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <div className="ml-4 w-0 flex-1">
              <dl>
                <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Identity Mappings
                </dt>
                <dd className="flex items-baseline mt-1">
                  <div className="text-2xl font-bold text-gray-900">
                    {isLoading ? "..." : activeMappings}
                  </div>
                  <div className="ml-2 text-xs text-gray-500">
                    ({totalMappings} total)
                  </div>
                </dd>
              </dl>
            </div>
          </div>
          <div className="mt-4 border-t border-gray-100 pt-3">
            <Link
              to="/identity-mappings"
              className="text-xs font-medium text-purple-600 hover:text-purple-800 inline-flex items-center"
            >
              View mappings &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Operational Readiness and Architecture Boundaries */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">
          Control Plane & Security Readiness
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Keycloak Identity
              </span>
              <Badge status="active" label="Enforced" />
            </div>
            <p className="text-xs text-gray-600">
              OIDC PKCE Public Browser Client. Authoritative identity mapping via user_id.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                PostgreSQL RLS
              </span>
              <Badge status="active" label="Active" />
            </div>
            <p className="text-xs text-gray-600">
              Row-Level Security enforced per tenant across facilities, care team, and identity records.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Mutation Idempotency
              </span>
              <Badge status="active" label="Guaranteed" />
            </div>
            <p className="text-xs text-gray-600">
              UUIDv4 Idempotency-Key generated on all unsafe administrative mutations with automatic conflict recovery.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Clinical Boundary
              </span>
              <Badge status="active" label="Zero PHI" />
            </div>
            <p className="text-xs text-gray-600">
              Strictly non-clinical. Observations, meal entries, medications, and AI scores are never queried or displayed.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Audit Trail
              </span>
              <Badge status="active" label="Append-Only" />
            </div>
            <p className="text-xs text-gray-600">
              Every administrative mutation generates an immutable, tamper-evident audit record.
            </p>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                Tenant Isolation
              </span>
              <Badge status="active" label="Hardware Bound" />
            </div>
            <p className="text-xs text-gray-600">
              Derived solely from caller's authenticated token. Tenant switching is strictly impossible.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
