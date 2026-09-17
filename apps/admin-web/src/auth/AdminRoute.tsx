import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./useAuth";

export const AdminRoute: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isAdmin, isLoading, logout } = useAuth();

  if (isLoading) {
    return (
      <div
        role="status"
        aria-label="Verifying authentication credentials"
        className="flex min-h-screen items-center justify-center bg-gray-50"
      >
        <div className="flex flex-col items-center space-y-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
          <p className="text-sm font-medium text-gray-600">Verifying session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!isAdmin) {
    return (
      <div
        role="alert"
        className="flex min-h-screen items-center justify-center bg-gray-50 px-4"
      >
        <div className="max-w-md w-full rounded-lg bg-white p-8 shadow-md text-center border border-red-200">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 mb-4">
            <svg
              className="h-6 w-6 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Operation Denied</h1>
          <p className="text-sm text-gray-600 mb-6">
            The Thali Admin Console is strictly restricted to operators holding the
            <code className="mx-1 px-1.5 py-0.5 bg-gray-100 text-red-700 rounded text-xs font-mono">
              admin
            </code>
            role. Clinical, patient, or other non-administrative accounts cannot access this
            console.
          </p>
          <div className="flex justify-center space-x-3">
            <button
              onClick={logout}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              Log out / Switch Account
            </button>
          </div>
        </div>
      </div>
    );
  }

  return children ? <>{children}</> : <Outlet />;
};
