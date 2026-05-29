"""
GREAT System — Final Review Spec Registry.

Read-only consolidation of approved estimations with allocation data.
Last step of the WP5 cycle before Stage 3 transmission to HVT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from great_sdd.specs.pre_estimation_specs import LineStatus, Role


# ──────────────────────────────────────────────
# 1. Role Permissions (§2)
# ──────────────────────────────────────────────

@dataclass
class FinalReviewPermission:
    can_view: bool
    can_export: bool
    can_send_stage3: bool
    scope: str  # "all_lines"


FINAL_REVIEW_PERMISSIONS: dict[Role, FinalReviewPermission] = {
    Role.ADMIN:    FinalReviewPermission(can_view=True, can_export=True, can_send_stage3=True, scope="all_lines"),
    Role.PMO:      FinalReviewPermission(can_view=True, can_export=True, can_send_stage3=True, scope="all_lines"),
    Role.CPO:      FinalReviewPermission(can_view=True, can_export=True, can_send_stage3=False, scope="all_lines"),
    Role.ENGINEER: FinalReviewPermission(can_view=True, can_export=True, can_send_stage3=False, scope="all_lines"),
    Role.RCRC:     FinalReviewPermission(can_view=True, can_export=True, can_send_stage3=False, scope="all_lines"),
}


# ──────────────────────────────────────────────
# 2. Which Lines Appear (§3)
# ──────────────────────────────────────────────

FINAL_REVIEW_ELIGIBLE_STATUSES = {LineStatus.APPROVED}

# Lines with incomplete allocation (missing societe or K€) are INCLUDED
# with zero K€ for unallocated rows. This is by design — PMO needs visibility.


# ──────────────────────────────────────────────
# 3. Aggregation Levels (§5.2)
# ──────────────────────────────────────────────

AGGREGATION_LEVELS = [
    "job_unit_row",      # Individual JU values
    "cost_type",         # Sum per cost type within society + métier
    "society",           # Sum across cost types within métier
    "metier",            # Sum across all societies for that métier
    "pl_total",          # Grand total across all métiers
]


# ──────────────────────────────────────────────
# 4. Final Review Grid Columns (§5.1)
# ──────────────────────────────────────────────

FINAL_REVIEW_JU_COLUMNS = [
    "Métier",
    "Owner N2",
    "Societe",
    "Cost Type",
    "FMM Description",
    "JU Description",
    "JU Code",
    "Total FTE",
    "Total K€",
    "Total BH",
    "Total KM",
]

# Yearly columns: FTE/K€/BH/KM 20XX — generated per cycle year


# ──────────────────────────────────────────────
# 5. CSV Global Export Columns (§7.2)
# ──────────────────────────────────────────────

FINAL_REVIEW_CSV_COLUMNS = [
    "PL Number",
    "PL Name",
    "Métier",
    "Owner N2",
    "Societe",
    "Cost Type",
    "FMM Description",
    "JU Description",
    "JU Code",
    "Total FTE",
    "Total K€",
    "Total BH",
    "Total KM",
]


# ──────────────────────────────────────────────
# 6. Stage 3 Send to HVT (§8)
# ──────────────────────────────────────────────

STAGE3_SEND_CONFIG = {
    "scope": "all_lines",           # Sends entire active cycle
    "per_line_send": False,         # No per-line send
    "resendable": True,             # Can be triggered multiple times
    "blocking_prerequisites": False, # Not blocked by incomplete allocation
    "warning_on_incomplete": True,  # Shows warning about unallocated JUs
}

# Pending: FINAL-01 — exact payload fields to agree with HVT


# ──────────────────────────────────────────────
# 7. Final Review Business Rules (§9)
# ──────────────────────────────────────────────

FINAL_REVIEW_RULES: list[dict] = [
    {"id": "FR-BR-01", "rule": "Read-only page — No data can be edited from Final Review"},
    {"id": "FR-BR-02", "rule": "No approval columns — Approval workflow complete before this page"},
    {"id": "FR-BR-03", "rule": "Approved lines only — Only status=Approved (PL, Métier) pairs appear"},
    {"id": "FR-BR-04", "rule": "All roles see all lines — No scoping by assignee"},
    {"id": "FR-BR-05", "rule": "No prototype data — Prototype costs do not appear in Final Review"},
    {"id": "FR-BR-06", "rule": "Stage 3 non-blocking — PMO can send even with incomplete allocation"},
    {"id": "FR-BR-07", "rule": "Stage 3 re-sendable — Each send transmits current state"},
    {"id": "FR-BR-08", "rule": "Stage 3: all lines — Sends entire active cycle, no per-line send"},
    {"id": "FR-BR-09", "rule": "Active cycle only"},
    {"id": "FR-BR-10", "rule": "CSV flat export — One row per JU, no subtotal rows"},
]

FR_CSV_COLUMNS = [
    "PL Number", "PL Name", "Métier", "Owner N2", "Societe",
    "Cost Type", "FMM Description", "JU Description", "JU Code",
    "Total FTE", "Total K€", "Total BH", "Total KM",
]


# ──────────────────────────────────────────────
# 8. Pending Definitions (§11)
# ──────────────────────────────────────────────

FINAL_REVIEW_PENDING = [
    {
        "id": "FINAL-01",
        "topic": "Stage 3 HVT payload: fields, granularity (per JU / per (PL,Métier) / per PL), mandatory fields, response format",
        "blocking": True,
        "notes": "Must be agreed with HVT team before implementation",
    },
]


# ──────────────────────────────────────────────
# 9. Totals Calculation helper
# ──────────────────────────────────────────────

def calculate_subtotals(rows: list[dict], fields: list[str]) -> dict:
    """Sum specified fields across a list of rows."""
    totals = {f: 0.0 for f in fields}
    for row in rows:
        for f in fields:
            totals[f] += row.get(f, 0.0)
    return totals


def aggregate_at_level(
    job_units: list[dict],
    group_by: list[str],
    aggregate_fields: list[str],
) -> list[dict]:
    """
    Group job units by specified fields and aggregate.

    Args:
        job_units: List of JU dicts
        group_by: Fields to group by (e.g. ["metier", "societe", "cost_type"])
        aggregate_fields: Fields to sum (e.g. ["total_fte", "total_ke"])

    Returns:
        List of aggregated rows with group fields + totals
    """
    from collections import defaultdict

    groups = defaultdict(lambda: {f: 0.0 for f in aggregate_fields})

    for ju in job_units:
        key = tuple(ju.get(f, "") for f in group_by)
        for f in aggregate_fields:
            groups[key][f] += ju.get(f, 0.0)

    result = []
    for key, totals in groups.items():
        row = dict(zip(group_by, key))
        row.update(totals)
        result.append(row)

    return result