import { createBrowserRouter, Navigate } from "react-router-dom";
import { AdminRoute } from "../auth/AdminRoute";
import { LoginPage } from "../auth/LoginPage";
import { CallbackPage } from "../auth/CallbackPage";
import { AdminLayout } from "../layouts/AdminLayout";
import { DashboardPage } from "../dashboard/DashboardPage";
import { FacilitiesPage } from "../facilities/FacilitiesPage";
import { CareTeamPage } from "../care-team/CareTeamPage";
import { PatientsPage } from "../patients/PatientsPage";
import { IdentityMappingsPage } from "../identity-mappings/IdentityMappingsPage";
import { AuditPage } from "../audit/AuditPage";

import { NotFoundPage } from "./NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/auth/callback",
    element: <CallbackPage />,
  },
  {
    path: "/",
    element: (
      <AdminRoute>
        <AdminLayout />
      </AdminRoute>
    ),
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: "facilities",
        element: <FacilitiesPage />,
      },
      {
        path: "care-team",
        element: <CareTeamPage />,
      },
      {
        path: "patients",
        element: <PatientsPage />,
      },
      {
        path: "identity-mappings",
        element: <IdentityMappingsPage />,
      },
      {
        path: "audit",
        element: <AuditPage />,
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/login" replace />,
  },
]);
