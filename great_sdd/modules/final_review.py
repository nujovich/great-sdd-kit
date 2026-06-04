"""
GREAT Final Review — Signature-Driven Pipeline Modules.

Read-only consolidation of approved estimations with allocation data.
Last step of the WP5 cycle before Stage 3 transmission to HVT.

Each module inherits from SignatureModule and honors a Signature contract
from signatures/final_review.py.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.signature_module import SignatureModule
from great_sdd.specs.pre_estimation_specs import LineStatus, Role
from great_sdd.specs.final_review_specs import (
    FINAL_REVIEW_PERMISSIONS,
    FINAL_REVIEW_ELIGIBLE_STATUSES,
    AGGREGATION_LEVELS,
    FINAL_REVIEW_JU_COLUMNS,
    aggregate_at_level,
    calculate_subtotals,
    STAGE3_SEND_CONFIG,
)
from great_sdd.signatures.final_review import (
    CHECK_FINAL_REVIEW_PERMISSION,
    FILTER_FINAL_REVIEW_JUS,
    AGGREGATE_FINAL_REVIEW,
    EXPORT_FINAL_REVIEW_CSV,
    SEND_STAGE3,
    CALCULATE_SUBTOTALS,
)

logger = logging.getLogger(__name__)


class FinalReviewPermissionChecker(SignatureModule):
    """Check if role can view/export/send Stage 3 in Final Review (§2).
    Signature: CHECK_FINAL_REVIEW_PERMISSION
    """

    signature = CHECK_FINAL_REVIEW_PERMISSION

    def forward_impl(self, role: str, action: str = "view") -> dict:
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


class FinalReviewEligibilityFilter(SignatureModule):
    """Filter to only Approved (PL, Metier) pairs (§3).
    Signature: FILTER_FINAL_REVIEW_JUS
    """

    signature = FILTER_FINAL_REVIEW_JUS

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        approved = [ju for ju in job_units if ju.get("status") == "approved"]
        excluded = len(job_units) - len(approved)

        return {
            "approved_jus_json": json.dumps(approved),
            "excluded_count": str(excluded),
        }


class AggregationEngine(SignatureModule):
    """Compute aggregation levels for Final Review (§5.2).
    Signature: AGGREGATE_FINAL_REVIEW
    """

    signature = AGGREGATE_FINAL_REVIEW

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        agg_fields = ["total_fte", "total_ke", "total_bh", "total_km"]

        aggregations = {
            "by_cost_type": aggregate_at_level(job_units, ["metier", "societe", "cost_type"], agg_fields),
            "by_society": aggregate_at_level(job_units, ["metier", "societe"], agg_fields),
            "by_metier": aggregate_at_level(job_units, ["metier"], agg_fields),
            "pl_total": calculate_subtotals(job_units, agg_fields),
        }

        return {"aggregations_json": json.dumps(aggregations)}


class CSVGlobalExporter(SignatureModule):
    """Export all JUs to flat CSV (§7).
    Signature: EXPORT_FINAL_REVIEW_CSV
    """

    signature = EXPORT_FINAL_REVIEW_CSV

    def forward_impl(self, job_units_json: str, columns_json: str = "[]") -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        if not job_units:
            return {"csv_content": "", "row_count": "0"}

        try:
            columns = json.loads(columns_json) if isinstance(columns_json, str) else columns_json
        except (json.JSONDecodeError, TypeError):
            columns = []

        if not columns:
            columns = [
                "PL Number", "PL Name", "Metier", "Owner N2", "Societe",
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

        return {"csv_content": output.getvalue(), "row_count": str(len(job_units))}


class Stage3Sender(SignatureModule):
    """Handle Stage 3 send to HVT (§8).
    Signature: SEND_STAGE3
    """

    signature = SEND_STAGE3

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

    def forward_impl(self, job_units_json: str, confirmed: bool = False) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        warning = self.prepare_warning(job_units)

        if warning["unassigned_count"] > 0 and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "warning": warning["warning"],
                "payload_json": "{}",
            }

        payload = {
            "cycle": "",
            "project_lines": [],
            "total_fte": sum(ju.get("total_fte", 0) for ju in job_units),
            "total_ke": sum(ju.get("total_ke", 0) for ju in job_units),
            "incomplete_count": warning["unassigned_count"],
        }

        return {
            "success": True,
            "needs_confirmation": False,
            "warning": warning["warning"],
            "payload_json": json.dumps(payload),
        }
