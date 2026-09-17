import React, { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "./useAuth";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";

export const LoginPage: React.FC = () => {
  const { isAuthenticated, isAdmin, login, isLoading, error } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get("reason") === "expired";

  useEffect(() => {
    if (isAuthenticated && isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, isAdmin, navigate]);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <div className="h-12 w-12 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-2xl shadow-md">
            T
          </div>
        </div>
        <h1 className="mt-4 text-center text-2xl font-bold tracking-tight text-gray-900">
          Thali Admin Console
        </h1>
        <p className="mt-1 text-center text-sm text-gray-600">
          Operational Control Plane • Non-Clinical
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10 border border-gray-200 space-y-6">
          {sessionExpired && (
            <Alert
              type="warning"
              title="Session Expired"
              message="Your administrative session has timed out. Please sign in again."
            />
          )}

          {error && (
            <Alert
              type="error"
              title="Authentication Error"
              message={error}
            />
          )}

          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-900 leading-relaxed">
            <span className="font-semibold block mb-1">Access Notice:</span>
            This console requires an authoritative Keycloak account with the{" "}
            <code className="font-mono font-semibold bg-amber-100 px-1 py-0.5 rounded text-amber-950">
              admin
            </code>{" "}
            role. Clinical or patient accounts will be denied entry.
          </div>

          <Button
            type="button"
            variant="primary"
            size="lg"
            className="w-full"
            isLoading={isLoading}
            onClick={login}
          >
            Sign in via Keycloak OIDC
          </Button>

          <div className="text-center">
            <span className="text-xs text-gray-400">
              Authorization Code Flow with PKCE (RFC 7636)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
