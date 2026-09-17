import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "./useAuth";
import { Button } from "../components/Button";
import { Alert } from "../components/Alert";

export const CallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleOidcCallback } = useAuth();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const errorParam = searchParams.get("error");
    const errorDesc = searchParams.get("error_description");

    if (errorParam) {
      setErrorMsg(errorDesc || `OIDC Authorization error: ${errorParam}`);
      return;
    }

    if (!code || !state) {
      setErrorMsg("Missing authorization code or state in callback URL.");
      return;
    }

    handleOidcCallback(code, state)
      .then(() => {
        navigate("/", { replace: true });
      })
      .catch((err: unknown) => {
        setErrorMsg(err instanceof Error ? err.message : "Authentication failed");
      });
  }, [searchParams, handleOidcCallback, navigate]);

  if (errorMsg) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white p-6 rounded-lg shadow-sm border border-gray-200 space-y-4">
          <Alert type="error" title="Sign In Failed" message={errorMsg} />
          <Button
            variant="primary"
            className="w-full"
            onClick={() => navigate("/login", { replace: true })}
          >
            Back to Sign In
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-label="Completing authentication"
      className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4"
    >
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent mb-4" />
      <p className="text-sm font-medium text-gray-700">
        Completing sign in and verifying operator privileges...
      </p>
    </div>
  );
};
