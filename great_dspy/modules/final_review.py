"""
GREAT Final Review — Pipeline Modules.

Read-only consolidation of approved estimations with allocation data.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from great_dspy.modules.base import Module
from great_dspy.specs.pre_estimation_specs import LineStatus, Role
from great_dspy.specs.final_review_specs import (
    FINAL_REVIEW_PERMISSIONS,
    FINAL_REVIEW_ELIGIBLE_STATUSES,
    AGGREGATION_LEVELS,
    FINAL_REVIEW_JU_COLUMNS,
    aggregate_at_level,
    calculate_subtotals,
    STAGE3_SEND_CONFIG,
)

logger = logging.getLogger(__name__)


class FinalReviewPermissionChecker(Module):
    """Check if role can view/export/send Stage 3 in Final Review (§2)."""

    def forward(self, role: str, action: str = "view") -> dict:
        try:
            role_enum = Role(role)
        except ValueError:
            return {"allowed": False, "reason": f"Unknown role: {role}"}

        perm = FINAL_REVIEW_PERMISSIONS.get(role_enum)
        if not perm or not perm.can_view:
            return {"allowed": False, "reason": f"{role} has no access to Final Review"}

        if action == "send_stage3" and not perm.can_send_stage3:
            return {"allowed": False, "reason": f"Only PMO/Admin can send Stage 3"}

        if action == "export" and not perm.can_export:
            return {"allowed": False, "reason": f"{role} cannot export"}

        return {"allowed": True, "reason": f"{role} authorized for {action}"}


class FinalReviewEligibilityFilter(Module):
    """Filter to only Approved (PL, Métier) pairs (§3)."""

    def forward(self, job_units: list[dict]) -> list[dict]:
        return [ju for ju in job_units if ju.get("status") == "approved"]


class AggregationEngine(Module):
    """Compute aggregation levels for Final Review (§5.2)."""

    def forward(self, job_units: list[dict]) -> dict:
        agg_fields = ["total_fte", "total_ke", "total_bh", "total_km"]

        return {
            "by_cost_type": aggregate_at_level(job_units, ["metier", "societe", "cost_type"], agg_fields),
            "by_society": aggregate_at_level(job_units, ["metier", "societe"], agg_fields),
            "by_metier": aggregate_at_level(job_units, ["metier"], agg_fields),
            "pl_total": calculate_subtotals(job_units, agg_fields),
        }


class CSVGlobalExporter(Module):
    """Export all JUs to flat CSV (§7)."""

    def forward(self, job_units: list[dict],
                columns: Optional[list[str]] = None) -> dict:
        if not job_units:
            return {"csv_content": "", "row_count": 0}

        if columns is None:
            columns = [
                "PL Number", "PL Name", "Métier", "Owner N2", "Societe",
                "Cost Type", "FMM Description", "JU Description", "JU Code",
                "Total FTE", "Total K€", "Total BH", "Total KM",
            ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)

        for ju in job_units:
            writer.writerow([
                ju.get("pl_number", ""),
                ju.get("pl_name", ""),
                ju.get("metier", ""),
                ju.get("owner_n2", ""),
                ju.get("societe", ""),
                ju.get("cost_type", ""),
                ju.get("fmm_description", ""),
                ju.get("ju_description", ""),
                ju.get("ju_code", ""),
                ju.get("total_fte", 0),
                ju.get("total_ke", 0),
                ju.get("total_bh", 0),
                ju.get("total_km", 0),
            ])

        return {"csv_content": output.getvalue(), "row_count": len(job_units)}


class Stage3Sender(Module):
    """Handle Stage 3 send to HVT (§8)."""

    def prepare_warning(self, job_units: list[dict]) -> dict:
        """Check for incomplete allocation before Stage 3 send."""
        unassigned = [ju for ju in job_units if not ju.get("societe")]
        pls_with_unassigned = set(ju.get("pl_number") for ju in unassigned)

        return {
            "unassigned_count": len(unassigned),
            "pls_affected": len(pls_with_unassigned),
            "warning": (
                f"{len(unassigned)} job units across {len(pls_with_unassigned)} "
                f"project lines have no societe assigned. "
                f"Their K€ will be zero in the transmission."
            ) if unassigned else "",
        }

    def forward(self, job_units: list[dict], confirmed: bool = False) -> dict:
        warning = self.prepare_warning(job_units)

        if warning["unassigned_count"] > 0 and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "warning": warning["warning"],
            }

        # Build consolidated payload
        payload = {
            "cycle": "",
            "project_lines": [],
            "total_fte": sum(ju.get("total_fte", 0) for ju in job_units),
            "total_ke": sum(ju.get("total_ke", 0) for ju in job_units),
            "incomplete_count": warning["unassigned_count"],
        }

        return {"success": True, "payload": payload, "warning": warning["warning"]}