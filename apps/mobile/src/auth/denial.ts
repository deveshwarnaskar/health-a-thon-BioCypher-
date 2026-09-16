import type { ApiErrorDetails } from "../services/api/errors";
import type { AccessDeniedReason } from "./authStateMachine";

/**
 * Maps an API error (typically a 403 from a protected endpoint) to the
 * client-safe access-denied reason that drives the protected-route denial
 * screen.  401s map to "deactivated" per mandate: the session is invalid or
 * the identity is disabled.
 */
export function denialReasonFromApiError(error: ApiErrorDetails): AccessDeniedReason {
  if (error.httpStatus === 401) return "deactivated";

  if (error.httpStatus === 403) {
    switch (error.forbiddenReason) {
      case "unlinked_identity":
        return "unlinked_identity";
      case "revoked_relationship":
        return "caregiver_revoked";
      case "expired_relationship":
        return "caregiver_expired";
      case "facility_mismatch":
        return "facility_mismatch";
      case "insufficient_capability":
        return "insufficient_capability";
      case "authorization_denied":
      default:
        return "general";
    }
  }

  return "general";
}

export function denialMessage(reason: AccessDeniedReason): string {
  switch (reason) {
    case "unknown_role":
      return "Your account does not have a recognized role. Please contact your clinic administrator.";
    case "unlinked_identity":
      return "Your account is not linked to a patient record yet. Please contact your clinic administrator.";
    case "caregiver_revoked":
      return "Your caregiver access has been revoked. Please contact your care coordinator.";
    case "caregiver_expired":
      return "Your caregiver access has expired. Please contact your care coordinator.";
    case "facility_mismatch":
      return "Your account does not have access to this facility. Please contact your administrator.";
    case "insufficient_capability":
      return "You do not have permission to perform this action.";
    case "deactivated":
      return "Your account has been deactivated. Please contact support.";
    case "general":
    default:
      return "You do not have access to this area. Please contact your administrator.";
  }
}
