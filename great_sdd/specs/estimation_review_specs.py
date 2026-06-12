"""
GREAT System — Estimation Review Spec Registry.

Shares the core state machine from Pre-Estimation specs and adds:
- Estimation Review-specific role permissions (read-only for all)
- HVT callback handling (approve/reject from external system)
- Approval column derivation rules
- CSV export specs (two modes: selected / all_filtered)
- Estimation Review business rules
- Pending definitions (ERev-02, ERev-03)
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
    can_export_selected: bool
    can_export_all_filtered: bool
    scope: str  # "all" | "own_rows_only"


ESTIMATION_REVIEW_PERMISSIONS: dict[Role, EstimationReviewPermission] = {
    Role.ADMIN:    EstimationReviewPermission(can_view=True, can_export_selected=True, can_export_all_filtered=True, scope="all"),
    Role.PMO:      EstimationReviewPermission(can_view=True, can_export_selected=True, can_export_all_filtered=True, scope="all"),
    Role.CPO:      EstimationReviewPermission(can_view=True, can_export_selected=True, can_export_all_filtered=True, scope="all"),
    Role.ENGINEER: EstimationReviewPermission(can_view=True, can_export_selected=True, can_export_all_filtered=True, scope="own_rows_only"),
    Role.RCRC:     EstimationReviewPermission(can_view=True, can_export_selected=True, can_export_all_filtered=True, scope="all"),
}


# ──────────────────────────────────────────────
# 2. Approval Column Derivation (§5)
# ──────────────────────────────────────────────

ENGINEER_APPROVAL_MAP: dict[LineStatus, str] = {
    LineStatus.TODO:                   "—",
    LineStatus.DRAFT:                  "—",
    LineStatus.ESTIMATED:              "✓",
    LineStatus.SENT:                   "✓",
    LineStatus.APPROVED:               "✓",
    LineStatus.MODIFICATION_REQUESTED: "—",
}

CPO_APPROVAL_MAP: dict[LineStatus, str] = {
    LineStatus.TODO:                   "—",
    LineStatus.DRAFT:                  "—",
    LineStatus.ESTIMATED:              "— (not yet sent)",
    LineStatus.SENT:                   "⏳ Pending",
    LineStatus.APPROVED:               "✓ Approved",
    LineStatus.MODIFICATION_REQUESTED: "✗ Rejected",
}


# ──────────────────────────────────────────────
# 3. HVT Callback Handling (§7)
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
          - target_status: LineStatus (APPROVED or MODIFICATION_REQUESTED)
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
            "target_status": LineStatus.MODIFICATION_REQUESTED,
            "comment": callback.comment,
            "notify_engineer": True,
        }


# ──────────────────────────────────────────────
# 4. CSV Export (§9)
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
# 5. Grid Columns (§4.1)
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
    # Yearly columns appended dynamically per cycle: FTE 20XX, BH 20XX, KM 20XX, K€ 20XX
]

GRID_FILTERS = [
    {"field": "pl_number_name", "type": "free_text", "visible_to": "all"},
    {"field": "metier", "type": "dropdown", "visible_to": "all"},
    {"field": "status", "type": "multi_select", "visible_to": "all"},
    {"field": "assignee", "type": "dropdown", "visible_to": "pmo_admin_only"},
]

GRID_DEFAULT_GROUPING = "pl_number"  # §4 — rows grouped by Project Line, not by status


# ──────────────────────────────────────────────
# 6. Estimation Review Business Rules (§10)
# ──────────────────────────────────────────────

ESTIMATION_REVIEW_RULES: list[dict] = [
    {"id": "ERev-BR-01", "rule": "Read-only page — no data can be edited from Estimation Review"},
    {"id": "ERev-BR-02", "rule": "Sent = irreversible — Sent status cannot be cancelled from WP5"},
    {"id": "ERev-BR-03", "rule": "Approved = terminal — Approved status cannot be changed by any WP5 action"},
    {"id": "ERev-BR-04", "rule": "Grid grouping — Rows are grouped by Project Line (PL); sorting by status is not the default"},
    {"id": "ERev-BR-05", "rule": "CSV export modes — Two modes: 'selected' (checked rows only) and 'all_filtered' (current filtered view)"},
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
# 7. Pending Definitions (§12)
# ──────────────────────────────────────────────

PENDING_DEFINITIONS = [
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