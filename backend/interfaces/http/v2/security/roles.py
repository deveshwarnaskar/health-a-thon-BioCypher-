"""Domain role ⇄ HTTP RBAC token bridge (Gate 06).

Extracts the canonical role tokens used by the authorization policy from
Keycloak realm roles, normalizing to the hyphenated spellings that the domain
``CareTeamRole`` enum owns. Syntax normalization happens here; role →
permission mapping lives in the policy module, never here.
"""

from __future__ import annotations

from .....domain.entities.care_team_member import CareTeamRole


ROLE_ALIASES: dict[str, str] = {
    # Keycloak realm role names -> canonical domain tokens
    "care coordinator": CareTeamRole.CARE_COORDINATOR.value.lower(),
    "care_coordinator": CareTeamRole.CARE_COORDINATOR.value.lower(),
    "carecoordinator": CareTeamRole.CARE_COORDINATOR.value.lower(),
    "dietitian/diabetes educator": CareTeamRole.DIETITIAN.value.lower(),
    "dietitian": CareTeamRole.DIETITIAN.value.lower(),
    "field health worker": CareTeamRole.FIELD_HEALTH_WORKER.value.lower(),
    "field_health_worker": CareTeamRole.FIELD_HEALTH_WORKER.value.lower(),
    "fieldhealthworker": CareTeamRole.FIELD_HEALTH_WORKER.value.lower(),
    "doctor": CareTeamRole.DOCTOR.value.lower(),
    "nurse": CareTeamRole.NURSE.value.lower(),
    "patient": "patient",
    "caregiver": "caregiver",
    "admin": "admin",
}


def role_tokens(roles: list[str]) -> list[str]:
    """Return the canonical, sorted role tokens present in ``roles``.

    Unknown strings are ignored — never mapped to a permission. Tokens are
    matched against the canonical domain spellings (e.g. ``doctor``,
    ``care_coordinator``, ``field_health_worker``).
    """
    raw_strings = [r.strip().lower() for r in roles if isinstance(r, str) and r.strip()]
    if not raw_strings:
        return []

    canonical = {
        # Clinical care-team roles (domain vocabulary)
        CareTeamRole.DOCTOR.value.lower(),
        CareTeamRole.NURSE.value.lower(),
        CareTeamRole.CARE_COORDINATOR.value.lower(),
        CareTeamRole.DIETITIAN.value.lower(),
        CareTeamRole.FIELD_HEALTH_WORKER.value.lower(),
        # Non-clinical identity/system roles consumed by the authorization
        # policy (patient proxy, caregiver proxy, administrator).
        "admin",
        "patient",
        "caregiver",
    }

    resolved: set[str] = set()
    for raw in raw_strings:
        if raw in canonical:
            resolved.add(raw)
        elif raw in ROLE_ALIASES:
            resolved.add(ROLE_ALIASES[raw])

    return sorted(canonical & resolved)
