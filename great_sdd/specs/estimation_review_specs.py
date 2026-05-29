"""
GREAT System — Estimation Review Spec Registry.

Shares the core state machine from Pre-Estimation specs and adds:
- Estimation Review-specific role permissions (read-only for all)
- Send-to-HVT flow with eligibility rules
- HVT callback handling (approve/reject)
- Approval column derivation rules
- CSV export specs
- Estimation Review business rules
- Pending definitions (ERev-01, ERev-02, ERev-03)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from great_sdd.specs.pre_estimation_specs import (
    LineStatus,
    STATUS_TRANSITIONS,
    LOCKED_STATUSES,
    EDITABLE_STATUSES,
    TERMINAL_STATUSES,
    Role,
    ROLE_PERMISSIONS as PRE_ROLE_PERMISSIONS,
)


# ──────────────────────────────────────────────
# 1. Estimation Review Role Permissions (§2)
# ──────────────────────────────────────────────

@dataclass
class EstimationReviewPermission:
    can_view: bool
    can_send_to_hvt: bool
    can_export_csv: bool
    scope: str  # "all" | "own_rows_only"


ESTIMATION_REVIEW_PERMISSIONS: dict[Role, EstimationReviewPermission] = {
    Role.ADMIN:    EstimationReviewPermission(can_view=True,  can_send_to_hvt=True,  can_export_csv=True,  scope="all"),
    Role.PMO:      EstimationReviewPermission(can_view=True,  can_send_to_hvt=True,  can_export_csv=True,  scope="all"),
    Role.CPO:      EstimationReviewPermission(can_view=True,  can_send_to_hvt=False, can_export_csv=True,  scope="all"),
    Role.ENGINEER: EstimationReviewPermission(can_view=True,  can_send_to_hvt=False, can_export_csv=True,  scope="own_rows_only"),
    Role.RCRC:     EstimationReviewPermission(can_view=True,  can_send_to_hvt=False, can_export_csv=True,  scope="all"),
}


# ──────────────────────────────────────────────
# 2. Send-to-HVT Eligibility (§6)
# ──────────────────────────────────────────────

SEND_ELIGIBLE_STATUSES = {LineStatus.ESTIMATED}

SEND_IRREVERSIBLE = True  # §6.3 — Sent cannot be cancelled

SEND_SCOPE = "current_filtered_view"  # §6.2 — operates on current filtered view

# Pending: ERev-01 — manual PMO button vs automatic on status=Estimated
# Current decision: manual button. Awaiting PO confirmation.


# ──────────────────────────────────────────────
# 3. Approval Column Derivation (§5)
# ──────────────────────────────────────────────

ENGINEER_APPROVAL_MAP: dict[LineStatus, str] = {
    LineStatus.TODO:      "—",
    LineStatus.DRAFT:     "—",
    LineStatus.ESTIMATED: "✓",
    LineStatus.SENT:      "✓",
    LineStatus.APPROVED:  "✓",
    LineStatus.REJECTED:  "—",
}

CPO_APPROVAL_MAP: dict[LineStatus, str] = {
    LineStatus.TODO:      "—",
    LineStatus.DRAFT:     "—",
    LineStatus.ESTIMATED: "— (not yet sent)",
    LineStatus.SENT:      "⏳ Pending",
    LineStatus.APPROVED:  "✓ Approved",
    LineStatus.REJECTED:  "✗ Rejected",
}


# ──────────────────────────────────────────────
# 4. HVT Callback Handling (§7)
# ──────────────────────────────────────────────

@dataclass
class HVTCallback:
    """Callback from HVT for CPO approval/rejection."""
    project_line: str
    metier: str
    approved: bool
    comment: str = ""


HVT_PAYLOAD_EXAMPLE = {
    "project_line": "<PL Number>",
    "metier": "<métier>",
    "workload_summary": {
        "2024": {"fte": 0.0, "bh": 0.0, "km": 0.0},
        "2025": {"fte": 0.0, "bh": 0.0, "km": 0.0},
        "2026": {"fte": 0.0, "bh": 0.0, "km": 0.0},
        "2027": {"fte": 0.0, "bh": 0.0, "km": 0.0},
    },
}


def process_hvt_callback(callback: HVTCallback) -> dict:
    """
    Process an HVT callback.

    Args:
        callback: HVTCallback with project_line, metier, approved, comment

    Returns:
        dict with:
          - target_status: LineStatus (APPROVED or REJECTED)
          - comment: str (rejection reason if rejected)
          - notify_engineer: bool (true if rejected)
    """
    if callback.approved:
        return {
            "target_status": LineStatus.APPROVED,
            "comment": "",
            "notify_engineer": False,
        }
    else:
        return {
            "target_status": LineStatus.REJECTED,
            "comment": callback.comment,
            "notify_engineer": True,
        }


# ──────────────────────────────────────────────
# 5. CSV Export (§9)
# ──────────────────────────────────────────────

CSV_EXPORT_COLUMNS = [
    "PL Number",
    "PL Name",
    "Métier",
    "Inductor",
    "JU Code",
    "FMM Description",
    "JU Description",
    "Total FTE",
    "Total BH",
    "Total KM",
]

# Yearly columns: FTE 20XX, BH 20XX, KM 20XX — generated per cycle year


# ──────────────────────────────────────────────
# 6. Grid Columns (§4.1)
# ──────────────────────────────────────────────

ESTIMATION_REVIEW_GRID_COLUMNS = [
    "PL Number",
    "PL Name",
    "Métier",
    "Assignee",
    "Status",
    "Engineer Approval",
    "CPO Approval",
    "Total FTE",
    "Total BH",
    "Total KM",
    # Yearly columns appended dynamically per cycle
]

GRID_FILTERS = [
    {"field": "pl_number_name", "type": "free_text", "visible_to": "all"},
    {"field": "metier", "type": "dropdown", "visible_to": "all"},
    {"field": "status", "type": "multi_select", "visible_to": "all"},
    {"field": "assignee", "type": "dropdown", "visible_to": "pmo_admin_only"},
]


# ──────────────────────────────────────────────
# 7. Estimation Review Business Rules (§10)
# ──────────────────────────────────────────────

ESTIMATION_REVIEW_RULES: list[dict] = [
    {"id": "ERev-BR-01", "rule": "Read-only page — no data can be edited from Estimation Review"},
    {"id": "ERev-BR-02", "rule": "Sent = irreversible — Sent status cannot be cancelled from WP5"},
    {"id": "ERev-BR-03", "rule": "Approved = terminal — Approved status cannot be changed by any WP5 action"},
    {"id": "ERev-BR-04", "rule": "Send eligibility — Only status=Estimated rows are sent; all others silently skipped"},
    {"id": "ERev-BR-05", "rule": "Send scope — 'Send all eligible' operates on the current filtered view only"},
    {"id": "ERev-BR-06", "rule": "Engineer scoping — Engineers see only their own (PL, Métier) rows"},
    {"id": "ERev-BR-07", "rule": "Comments read-only — Rejection comments are not shown in this grid"},
    {"id": "ERev-BR-08", "rule": "No approval gestures — No approval checkboxes; approval is fully status-derived"},
    {"id": "ERev-BR-09", "rule": "Active cycle only — Grid shows data for the active estimation cycle only"},
    {"id": "ERev-BR-10", "rule": "CPO column via HVT only — CPO approval state cannot be set manually from any WP5 interface"},
]

# Merged full business rules (Pre-Estimation + Estimation Review)
ALL_BUSINESS_RULES = []
from great_sdd.specs.pre_estimation_specs import BUSINESS_RULES
ALL_BUSINESS_RULES.extend(BUSINESS_RULES)
ALL_BUSINESS_RULES.extend(ESTIMATION_REVIEW_RULES)


# ──────────────────────────────────────────────
# 8. Pending Definitions (§12)
# ──────────────────────────────────────────────

PENDING_DEFINITIONS = [
    {
        "id": "ERev-01",
        "topic": "Send to HVT trigger mechanism — manual PMO button vs automatic on status=Estimated",
        "current_decision": "Manual PMO button",
        "blocking": True,
        "notes": "Must be confirmed with Product Owner before implementation",
    },
    {
        "id": "ERev-02",
        "topic": "Exact HVT payload fields for Stage 2 submission",
        "current_decision": "See HVT_PAYLOAD_EXAMPLE in this file",
        "blocking": True,
        "notes": "Must be agreed with HVT team before implementation",
    },
    {
        "id": "ERev-03",
        "topic": "Email notification content and frequency for engineer rejection alerts",
        "current_decision": "Fallback is status-based discovery in Pre-Estimation View",
        "blocking": False,
        "notes": "Depends on transversal email service spec",
    },
]