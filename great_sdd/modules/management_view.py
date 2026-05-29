"""
GREAT Management View — Pipeline Modules.

Operational dashboard with status distribution pie chart
and status evolution timeline.
"""
from __future__ import annotations

import logging
from typing import Optional

from great_sdd.modules.base import Module
from great_sdd.specs.pre_estimation_specs import LineStatus, Role
from great_sdd.specs.management_view_specs import (
    MANAGEMENT_ACCESS,
    MGMT_EXCLUDED_METIERS,
    compute_pie_chart,
    PieChartSlice,
)

logger = logging.getLogger(__name__)


class ManagementAccessChecker(Module):
    """Check if role can access Management View (§2)."""

    def forward(self, role: str) -> dict:
        try:
            role_enum = Role(role)
        except ValueError:
            return {"allowed": False, "reason": f"Unknown role: {role}"}

        allowed = MANAGEMENT_ACCESS.get(role_enum, False)
        if not allowed:
            return {"allowed": False, "reason": f"{role} has no access to Management View"}

        return {"allowed": True, "reason": f"{role} can access Management View"}


class PieChartBuilder(Module):
    """Build pie chart data from status counts (§6)."""

    def forward(self, pairs_by_status: dict[str, int],
                metier_filter: str = "All") -> dict:
        slices = compute_pie_chart(pairs_by_status)

        return {
            "slices": [{"status": s.status, "count": s.count,
                         "percentage": s.percentage} for s in slices],
            "total": sum(s.count for s in slices),
            "metier_filter": metier_filter,
        }


class TimelineBuilder(Module):
    """Build timeline chart data (§7)."""

    def forward(self, timeline_data: list[dict],
                metier_filter: str = "All") -> dict:
        """
        Args:
            timeline_data: [{"date": "2026-01-01", "status_counts": {"to_do": 10, ...}}, ...]
            metier_filter: "All" or specific métier

        Returns:
            Processed timeline with one line per status
        """
        if not timeline_data:
            return {"lines": [], "data_points": 0, "metier_filter": metier_filter}

        # Build one series per status
        statuses = [s.value for s in LineStatus]
        lines = []

        for status in statuses:
            points = []
            for dp in timeline_data:
                counts = dp.get("status_counts", {})
                points.append({
                    "date": dp.get("date", ""),
                    "count": counts.get(status, 0),
                })
            lines.append({"status": status, "points": points})

        return {
            "lines": lines,
            "data_points": len(timeline_data),
            "metier_filter": metier_filter,
        }


class MetierFilter(Module):
    """Apply métier filter to (PL, Métier) pairs (§5)."""

    def forward(self, pairs: list[dict], metier: str = "All") -> list[dict]:
        if metier == "All":
            return [
                p for p in pairs
                if p.get("metier") not in MGMT_EXCLUDED_METIERS
            ]
        return [p for p in pairs if p.get("metier") == metier]

    def count_by_status(self, pairs: list[dict]) -> dict[str, int]:
        """Count pairs by status."""
        counts = {}
        for p in pairs:
            status = p.get("status", "to_do")
            counts[status] = counts.get(status, 0) + 1
        # Ensure all statuses are present
        for s in LineStatus:
            if s.value not in counts:
                counts[s.value] = 0
        return counts