"""
GREAT System — Transversal Features Spec Registry.

Capabilities that span the entire application:
- Estimation cycle management
- Workload standard versioning and updates
- Filterable/sortable/resizable tables
- Automatic email alerts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from great_dspy.specs.pre_estimation_specs import Role

# Pending definitions count at the bottom


# ──────────────────────────────────────────────
# 1. Estimation Cycles (§2)
# ──────────────────────────────────────────────

@dataclass
class EstimationCycle:
    name: str
    start_date: str  # YYYY-MM-DD
    active: bool = False
    # No end date — a cycle closes implicitly when a new one is activated


# Who can manage cycles
CYCLE_MANAGERS = {Role.PMO, Role.ADMIN}


CYCLE_RULES: list[dict] = [
    {"id": "CYCLE-BR-01", "rule": "One active cycle — Only one cycle can be active at any time"},
    {"id": "CYCLE-BR-02", "rule": "No reactivation — Inactive cycles cannot be reactivated"},
    {"id": "CYCLE-BR-03", "rule": "No deletion — Cycles and their data are never deleted"},
    {"id": "CYCLE-BR-04", "rule": "Auto-deactivation — Creating a new cycle automatically deactivates the current one"},
]


# ──────────────────────────────────────────────
# 2. Workload Standard Versioning (§3)
# ──────────────────────────────────────────────

@dataclass
class WorkloadStandardVersion:
    version_id: str
    uploaded_at: str  # ISO timestamp
    uploaded_by: str  # User identifier
    filename: str
    status: str = "active"  # active | superseded
    validation_errors: list[str] = field(default_factory=list)


WORKLOAD_UPLOADERS = {Role.ADMIN, Role.RCRC}

WORKLOAD_RULES: list[dict] = [
    {"id": "WL-BR-01", "rule": "Admin + RCRC only — No other role can upload"},
    {"id": "WL-BR-02", "rule": "Excel format only — Only .xlsx files accepted"},
    {"id": "WL-BR-03", "rule": "Preprocessing on upload — Existing pipeline validates and converts"},
    {"id": "WL-BR-04", "rule": "Versioned — Each upload is a new version; old versions retained"},
    {"id": "WL-BR-05", "rule": "Isolation — Saved JU coefficients are immutable after save"},
    {"id": "WL-BR-06", "rule": "Validation before commit — Structural errors reported before persistence"},
]


# ──────────────────────────────────────────────
# 2b. Bulk Inductor Deletion (§3b)
# ──────────────────────────────────────────────

# Who can delete inductors (same roles that can upload)
WORKLOAD_DELETERS = {Role.ADMIN, Role.RCRC}

BULK_DELETION_RULES: list[dict] = [
    {"id": "DEL-BR-01", "rule": "Admin + RCRC only — No other role can bulk-delete inductors"},
    {"id": "DEL-BR-02", "rule": "Show loaded only — Deletion view shows only already-loaded inductors"},
    {"id": "DEL-BR-03", "rule": "Select all shortcut — Header checkbox selects/deselects all visible rows"},
    {"id": "DEL-BR-04", "rule": "Confirm before delete — Modal confirmation required before批量删除 executes"},
    {"id": "DEL-BR-05", "rule": "Active version protected — Cannot delete inductors from the active version if it is the only version"},
    {"id": "DEL-BR-06", "rule": "Deletion is permanent — Deleted inductors are not recoverable from the UI"},
    {"id": "DEL-BR-07", "rule": "Superseded version cascade — Deleting from a superseded version does not affect the active version"},
    {"id": "DEL-BR-08", "rule": "Filter preserves selection — Changing filters preserves current selection state"},
    {"id": "DEL-BR-09", "rule": "Empty selection blocked — Delete button disabled when no rows selected"},
    {"id": "DEL-BR-10", "rule": "Deletion summary — After delete, show count of deleted vs skipped inductors"},
]


# ──────────────────────────────────────────────
# 3. Filterable/Sortable/Resizable Tables (§4)
# ──────────────────────────────────────────────

TABLE_CAPABILITIES = {
    "column_filtering": True,
    "column_sorting": True,
    "column_resizing": True,
}

TABLE_SCOPE = [
    "Pre-Estimation View",      # Project line grid
    "Estimation Review",         # (PL, Métier) pairs grid
    "Allocation",                # Job unit grid
    "Final Review",              # Job unit rows within tabs
    # Management View has no grid (charts only)
]

TABLE_SESSION_PERSISTENCE = "current_session"
# Filter state, sort order, column widths persist within the current page session.
# Navigating away and returning resets all to defaults.


TABLE_RULES: list[dict] = [
    {"id": "TABLE-BR-01", "rule": "All grids must support column filtering, sorting, and resizing"},
    {"id": "TABLE-BR-02", "rule": "Filter/sort/resize state persists within the current page session only"},
    {"id": "TABLE-BR-03", "rule": "Navigating away and returning resets all table state to defaults"},
]


# ──────────────────────────────────────────────
# 4. Automatic Email Alerts (§5)
# ──────────────────────────────────────────────

@dataclass
class EmailAlertConfig:
    alert_type: str
    recipients: str  # Role description
    frequency: str
    content_pending: bool
    depends_on_trans: str  # Blocking dependency


EMAIL_ALERTS: list[EmailAlertConfig] = [
    EmailAlertConfig("Engineer weekly summary", "Each engineer individually",
                     "Weekly (fixed)", True, "TRANS-01, TRANS-02"),
    EmailAlertConfig("RCRC weekly overview", "All RCRCs",
                     "Weekly (fixed)", True, "TRANS-01, TRANS-03"),
    EmailAlertConfig("Engineer rejection notification", "Assigned engineer",
                     "Triggered (on Rejected)", False, "TRANS-01"),
]

EMAIL_LOG_FIELDS = ["timestamp", "recipient", "alert_type", "cycle", "success"]
EMAIL_LOG_RETENTION = "active cycle duration"


EMAIL_RULES: list[dict] = [
    {"id": "EMAIL-BR-01", "rule": "Weekly alerts run on a fixed weekly cadence — not configurable"},
    {"id": "EMAIL-BR-02", "rule": "No per-user opt-out in current scope"},
    {"id": "EMAIL-BR-03", "rule": "Every sent email is logged with timestamp, recipient, type, cycle, success/failure"},
    {"id": "EMAIL-BR-04", "rule": "Email logs retained for the duration of the active cycle"},
]


# ──────────────────────────────────────────────
# 5. Pending Definitions (§6)
# ──────────────────────────────────────────────

TRANSVERSAL_PENDING = [
    {
        "id": "TRANS-01",
        "topic": "Email service: which service (Microsoft Graph API / SMTP relay / other), "
                 "sender address, display name, corporate email policies",
        "blocking": True,
        "notes": "Must be decided with infrastructure team — blocks ALL email alerts",
    },
    {
        "id": "TRANS-02",
        "topic": "Engineer weekly email: per-line data included, status filters, "
                 "direct link to Pre-Estimation View, subject line format",
        "blocking": False,
        "notes": "Can be defined during implementation, needed before go-live",
    },
    {
        "id": "TRANS-03",
        "topic": "RCRC weekly email: cycle-level metrics (status breakdown, allocation progress, "
                 "counts by métier), direct link to Allocation page, subject line format",
        "blocking": False,
        "notes": "Can be defined during implementation, needed before go-live",
    },
]


# ──────────────────────────────────────────────
# 6. Merged Transversal Business Rules
# ──────────────────────────────────────────────

TRANSVERSAL_RULES: list[dict] = []
TRANSVERSAL_RULES.extend(CYCLE_RULES)
TRANSVERSAL_RULES.extend(WORKLOAD_RULES)
TRANSVERSAL_RULES.extend(BULK_DELETION_RULES)
TRANSVERSAL_RULES.extend(TABLE_RULES)
TRANSVERSAL_RULES.extend(EMAIL_RULES)