"""Endpoint conformance oracle for GET /project-lines.

MIRRORS THE EXTERNAL CONTRACT (cap_horse_great/docs/open-api/pev-openapi.yaml +
the FastAPI service list_lines). The SDD is NOT the source of truth here — this
re-implements the documented endpoint behavior deterministically so a Python
backend and a TypeScript frontend can both prove conformance against ONE golden
fixture. No view/rules are added to the business-rule census.

Deterministic: fixed UUIDs/OIDs, no network/LLM/time/randomness.
"""
from __future__ import annotations

from sdd.base_conformance import EndpointProbe

# Métier enum MIRRORED FROM THE EXTERNAL CONTRACT (ProjectLineMetier). This
# intentionally EXCLUDES H-TESTING and therefore differs from the SDD métier
# taxonomy in great_sdd/specs/pre_estimation_specs.py. Do NOT "fix" it toward the
# SDD set — the endpoint contract is the source of truth here.
PROJECT_LINE_METIERS = [
    "H-DESIGN", "H-TUNING", "H-SOFTWARE", "H-CUSTOMER", "H-PROJECT", "H-NP",
]
STATUSES = ["To do", "Draft", "Estimated", "Sent", "Rejected", "Approved"]
ROLES_ALLOWED = {"Admin", "PMO", "RCRC", "Engineer"}

# The 24 response fields in the contract's order (ProjectLine DTO). `assignee`
# maps from the DB column assignee_oid.
PROJECT_LINE_FIELDS = [
    "id", "pl_number", "pl_name", "status", "request_type", "client", "metier",
    "organ_type", "project_ranking", "market", "alliance_code", "vehicle_code",
    "energy", "injection_system", "standard_emissions", "engineering",
    "estimate_type", "sp_date", "pc_date", "co_date", "sop_date", "assignee",
    "total_days", "total_keuro",
]


def _row(uuid: str, pl_number: str, pl_name: str, metier: str,
         status: str, assignee_oid: str) -> dict:
    """A full 24-field project-line row; every unset field is null."""
    row = {field: None for field in PROJECT_LINE_FIELDS}
    row.update({
        "id": uuid, "pl_number": pl_number, "pl_name": pl_name,
        "metier": metier, "status": status, "assignee": assignee_oid,
    })
    return row


# Deterministic seed — fixed UUIDs/OIDs. Includes H-NP and H-PROJECT (the contract
# returns them); never H-TESTING (not a valid project-line métier).
SEED = [
    _row("11111111-1111-4111-8111-111111111111", "PL-001", "Auth refactor",
         "H-SOFTWARE", "Rejected", "oid-engineer-1"),
    _row("22222222-2222-4222-8222-222222222222", "PL-002", "OAuth integration",
         "H-DESIGN", "To do", "oid-engineer-2"),
    _row("33333333-3333-4333-8333-333333333333", "PL-003", "NP line",
         "H-NP", "To do", "oid-engineer-1"),
    _row("44444444-4444-4444-8444-444444444444", "PL-004", "Infra deploy",
         "H-PROJECT", "Draft", "oid-pmo"),
]

# SEED is part of the mirrored contract — keep it valid against the contract enums
# (these also document the allowed values for consumers building their own mocks).
assert all(row["metier"] in PROJECT_LINE_METIERS for row in SEED), "seed métier off-contract"
assert all(row["status"] in STATUSES for row in SEED), "seed status off-contract"


def list_project_lines(request: dict) -> dict:
    """Deterministic reference for GET /project-lines.

    request keys: role (str|None), user_oid (str|None), query (dict with optional
    'assignee'/'metier'), active_cycle (bool). Returns {"status": int, "body": dict|None}.

    Mirrors list_lines + the openapi guard order:
      - auth first (dependency layer): no role/JWT -> 401; CPO or other role -> 403;
        an Engineer without an oid -> 401
      - then the service: no active cycle -> 404
      - Engineer hard-scoped to own assignee_oid (the assignee query is ignored)
      - PMO/Admin/RCRC honor the assignee/metier query
      - filterOptions reflect the role-scoped set, ignoring active filters
    """
    role = request.get("role")
    user_oid = request.get("user_oid")
    # Auth is enforced at the dependency layer (Depends(_ALLOWED)) BEFORE the
    # service queries the active cycle, so 401/403 take precedence over 404
    # (this mirrors the FastAPI guard order).
    if role is None:
        return {"status": 401, "body": None}
    if role not in ROLES_ALLOWED:                       # CPO and anything else
        return {"status": 403, "body": None}
    if role == "Engineer" and not user_oid:
        # An Engineer carries an oid from the JWT; missing oid == no valid identity.
        return {"status": 401, "body": None}
    if not request.get("active_cycle", True):
        return {"status": 404, "body": None}

    query = request.get("query") or {}

    if role == "Engineer":
        scope_oid = user_oid
        effective_assignee = user_oid                   # ignore the assignee query
    else:
        scope_oid = None
        effective_assignee = query.get("assignee")

    # Role-scoped set drives filterOptions (ignores active filters).
    scoped = [r for r in SEED if scope_oid is None or r["assignee"] == scope_oid]

    metier_filter = query.get("metier")
    data = sorted(
        (r for r in scoped
         if (effective_assignee is None or r["assignee"] == effective_assignee)
         and (metier_filter is None or r["metier"] == metier_filter)),
        key=lambda r: r["pl_number"],
    )
    filter_options = {
        "assignees": sorted({r["assignee"] for r in scoped if r["assignee"] is not None}),
        "metiers": sorted({r["metier"] for r in scoped}),
    }
    return {"status": 200, "body": {"data": data, "filterOptions": filter_options}}


PROBE = EndpointProbe(
    endpoint="GET /project-lines",
    name="project_lines_list",
    fn=list_project_lines,
    cases=[
        {"role": "Engineer", "user_oid": "oid-engineer-1", "query": {}, "active_cycle": True},
        {"role": "Engineer", "user_oid": "oid-engineer-1",
         "query": {"assignee": "oid-engineer-2"}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {"metier": "H-DESIGN"}, "active_cycle": True},
        {"role": "CPO", "user_oid": "oid-cpo", "query": {}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {}, "active_cycle": False},
        {"role": None, "user_oid": None, "query": {}, "active_cycle": True},
    ],
)

# ── HTTP contract (mirrored from cap_horse_great pev-openapi.yaml) ──
# Used by the collection exporter to build Bruno/Postman requests. The server
# base path (/api/v1) is a collection variable {{baseUrl}}; auth is Bearer {{token}}.

HTTP_BINDING = {
    "method": "GET",
    "path": "/project-lines",
    "query_params": ["assignee", "metier"],
    "auth": "bearer",
    "body": None,
}

REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ListProjectLinesQuery",
    "type": "object",
    "properties": {
        "assignee": {"type": "string",
                     "description": "Filter by assignee OID (PMO/Admin/RCRC)."},
        "metier": {"type": "string", "enum": list(PROJECT_LINE_METIERS),
                   "description": "Filter by project line métier (PMO/Admin/RCRC)."},
    },
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ProjectLinesResponse",
    "type": "object",
    "required": ["data", "filterOptions"],
    "properties": {
        "data": {"type": "array", "items": {"$ref": "#/definitions/ProjectLine"}},
        "filterOptions": {
            "type": "object",
            "required": ["assignees", "metiers"],
            "properties": {
                "assignees": {"type": "array", "items": {"type": "string"}},
                "metiers": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "definitions": {
        "ProjectLine": {
            "type": "object",
            "required": ["id", "pl_number", "pl_name", "status", "metier"],
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "pl_number": {"type": "string"},
                "pl_name": {"type": "string"},
                "status": {"type": "string", "enum": list(STATUSES)},
                "request_type": {"type": ["string", "null"]},
                "client": {"type": ["string", "null"]},
                "metier": {"type": "string", "enum": list(PROJECT_LINE_METIERS)},
                "organ_type": {"type": ["string", "null"]},
                "project_ranking": {"type": ["string", "null"]},
                "market": {"type": ["string", "null"]},
                "alliance_code": {"type": ["string", "null"]},
                "vehicle_code": {"type": ["string", "null"]},
                "energy": {"type": ["string", "null"]},
                "injection_system": {"type": ["string", "null"]},
                "standard_emissions": {"type": ["string", "null"]},
                "engineering": {"type": ["string", "null"]},
                "estimate_type": {"type": ["string", "null"]},
                "sp_date": {"type": ["string", "null"], "format": "date"},
                "pc_date": {"type": ["string", "null"], "format": "date"},
                "co_date": {"type": ["string", "null"], "format": "date"},
                "sop_date": {"type": ["string", "null"], "format": "date"},
                "assignee": {"type": ["string", "null"],
                             "description": "Entra OID (from column assignee_oid)."},
                "total_days": {"type": ["integer", "null"]},
                "total_keuro": {"type": ["number", "null"]},
            },
        }
    },
}
