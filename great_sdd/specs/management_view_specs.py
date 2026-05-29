"""
GREAT System — Management View Spec Registry.

Read-only operational dashboard with status distribution pie chart
and status evolution timeline for PMO and Admin.
"""
from __future__ import annotations

from dataclasses import dataclass

from great_sdd.specs.pre_estimation_specs import (
    LineStatus, Role, STATUS_TRANSITIONS,
)
from great_sdd.specs.estimation_review_specs import ALL_BUSINESS_RULES


# ──────────────────────────────────────────────
# 1. Role Permissions (§2)
# ──────────────────────────────────────────────

MANAGEMENT_ACCESS: dict[Role, bool] = {
    Role.ADMIN:    True,
    Role.PMO:      True,
    Role.CPO:      False,
    Role.ENGINEER: False,
    Role.RCRC:     False,
}


# ──────────────────────────────────────────────
# 2. Status Model (§3)
# ──────────────────────────────────────────────

# Uses the same full status model from Pre-Estimation
MGMT_STATUSES = list(LineStatus)  # All 6 statuses displayed

# H-NP and H-PROJECT excluded from metier filter
MGMT_EXCLUDED_METIERS = {"H-NP", "H-PROJECT"}

MGMT_METIER_FILTER_OPTIONS = [
    "All", "H-DESIGN", "H-TUNING", "H-SOFTWARE",
    "H-CUSTOMER", "H-TESTING",
]


# ──────────────────────────────────────────────
# 3. Unit of Measurement (§4)
# ──────────────────────────────────────────────

# Both charts count (PL, Métier) pairs — the atomic unit of estimation in WP5
# A project line with 4 métiers = 4 units, each independently tracked by status


# ──────────────────────────────────────────────
# 4. Chart Configuration (§6, §7)
# ──────────────────────────────────────────────

@dataclass
class PieChartSlice:
    status: str
    count: int
    percentage: float


@dataclass
class TimelineDataPoint:
    date: str  # YYYY-MM-DD
    status_counts: dict[str, int]  # status -> count at that date


def compute_pie_chart(pairs_by_status: dict[str, int]) -> list[PieChartSlice]:
    """Compute pie chart slices from (PL, Métier) pair counts per status."""
    total = sum(pairs_by_status.values())
    if total == 0:
        return [PieChartSlice(s, 0, 0.0) for s in MGMT_STATUSES]

    slices = []
    for status in LineStatus:
        count = pairs_by_status.get(status.value, 0)
        pct = round((count / total) * 100, 1)
        slices.append(PieChartSlice(status.value, count, pct))

    return slices


# ──────────────────────────────────────────────
# 5. Data Refresh (§8)
# ──────────────────────────────────────────────

# Charts reflect state at page load time. No auto-refresh.
# PMO reloads the page to get latest data.


# ──────────────────────────────────────────────
# 6. Cycle Scope (§9)
# ──────────────────────────────────────────────

# Active cycle only. No cycle switcher. No historical comparison.


# ──────────────────────────────────────────────
# 7. Management Business Rules (§10)
# ──────────────────────────────────────────────

MANAGEMENT_RULES: list[dict] = [
    {"id": "MGMT-BR-01", "rule": "PMO and Admin only — No other role can access"},
    {"id": "MGMT-BR-02", "rule": "(PL, Métier) pair counting — Both charts count pairs, not unique PL Numbers"},
    {"id": "MGMT-BR-03", "rule": "Full status model — All 6 statuses from the PRD model are shown"},
    {"id": "MGMT-BR-04", "rule": "H-NP and H-PROJECT excluded — Consistent with Pre-Estimation filter"},
    {"id": "MGMT-BR-05", "rule": "Single filter for both charts — Métier applies to both simultaneously"},
    {"id": "MGMT-BR-06", "rule": "Active cycle only — No historical cycle data"},
    {"id": "MGMT-BR-07", "rule": "On page load refresh — No auto-polling or live updates"},
    {"id": "MGMT-BR-08", "rule": "Read-only — No data entry, no side effects"},
]


# ──────────────────────────────────────────────
# 8. Pending Definitions (§12)
# ──────────────────────────────────────────────

MANAGEMENT_PENDING = [
    {
        "id": "MGMT-01",
        "topic": "Timeline data source: event log vs daily snapshot",
        "blocking": True,
        "notes": "4 open questions: (1) approach; (2) new table vs reuse; "
                 "(3) snapshot trigger; (4) retention period",
    },
]


# Update merged rules
ALL_BUSINESS_RULES_FULL = list(ALL_BUSINESS_RULES)
ALL_BUSINESS_RULES_FULL.extend(MANAGEMENT_RULES)