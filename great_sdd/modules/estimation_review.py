"""
GREAT Estimation Review — Signature-Driven Modules.

Each module honors a Signature contract from signatures/estimation_review.py.
All modules are read-only by spec. The only write action is CSV export.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.signature_module import SignatureModule
from great_sdd.modules.pre_estimation import StatusTransitionValidator
from great_sdd.specs.pre_estimation_specs import (
    LineStatus,
    Role,
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
)
from great_sdd.specs.estimation_review_specs import (
    ESTIMATION_REVIEW_PERMISSIONS,
    ENGINEER_APPROVAL_MAP,
    CPO_APPROVAL_MAP,
    process_hvt_callback,
    CSV_EXPORT_COLUMNS,
    HVTCallback,
)
from great_sdd.signatures.estimation_review import (
    CHECK_ESTIMATION_REVIEW_PERMISSION,
    DERIVE_APPROVAL_COLUMNS,
    PROCESS_HVT_CALLBACK_SIG,
    EXPORT_CSV,
)

logger = logging.getLogger(__name__)


class EstimationReviewPermissionChecker(SignatureModule):
    """Check role permissions for Estimation Review.
    Signature: CHECK_ESTIMATION_REVIEW_PERMISSION
    """

    signature = CHECK_ESTIMATION_REVIEW_PERMISSION

    def forward_impl(self, role: str, action: str = "view") -> dict:
        try:
            role_enum = Role(role)
        except ValueError:
            return {"allowed": False, "reason": f"Unknown role: {role}"}

        perm = ESTIMATION_REVIEW_PERMISSIONS.get(role_enum)
        if not perm:
            return {"allowed": False, "reason": f"No permissions defined for {role}"}

        if not perm.can_view:
            return {"allowed": False, "reason": f"{role} has no access to Estimation Review"}

        if action == "export_selected" and not perm.can_export_selected:
            return {"allowed": False, "reason": f"{role} cannot export selected rows"}

        if action == "export_all_filtered" and not perm.can_export_all_filtered:
            return {"allowed": False, "reason": f"{role} cannot export all filtered rows"}

        return {"allowed": True, "reason": f"{role} is authorized to {action} in Estimation Review"}


class ApprovalColumnDeriver(SignatureModule):
    """Derive approval column values from status.
    Signature: DERIVE_APPROVAL_COLUMNS
    """

    signature = DERIVE_APPROVAL_COLUMNS

    def forward_impl(self, status: str) -> dict:
        try:
            status_enum = LineStatus(status)
        except ValueError:
            return {"engineer_approval": "—", "cpo_approval": "—"}

        return {
            "engineer_approval": ENGINEER_APPROVAL_MAP.get(status_enum, "—"),
            "cpo_approval": CPO_APPROVAL_MAP.get(status_enum, "—"),
        }

    def derive_row(self, row: dict) -> dict:
        """Add derived approval columns to a grid row."""
        approvals = self.forward(status=row.get("status", "to_do"))
        return {
            **row,
            "engineer_approval": approvals["engineer_approval"],
            "cpo_approval": approvals["cpo_approval"],
        }


class HVTCallbackProcessor(SignatureModule):
    """Process HVT callback for CPO approval/rejection.
    Signature: PROCESS_HVT_CALLBACK_SIG
    """

    signature = PROCESS_HVT_CALLBACK_SIG

    def __init__(self, lm=None):
        super().__init__(lm)
        self.status_validator = StatusTransitionValidator(lm)

    def forward_impl(self, project_line: str, metier: str,
                     approved: bool, comment: str = "") -> dict:
        callback = HVTCallback(
            project_line=project_line,
            metier=metier,
            approved=approved,
            comment=comment,
        )

        result = process_hvt_callback(callback)

        # Validate the transition via Signature-driven StatusTransitionValidator
        transition_result = self.status_validator.forward(
            current_status="sent",
            target_status=result["target_status"].value,
            has_saved_draft_in_session=False,
        )

        if not transition_result["is_valid"]:
            return {
                "target_status": result["target_status"].value,
                "transition_valid": False,
                "error_message": transition_result["error_message"],
                "notify_engineer": result["notify_engineer"],
            }

        return {
            "target_status": result["target_status"].value,
            "transition_valid": True,
            "error_message": "",
            "notify_engineer": result["notify_engineer"],
        }


class CSVExporter(SignatureModule):
    """Generate CSV export of estimation data.
    Signature: EXPORT_CSV
    """

    signature = EXPORT_CSV

    def build_rows(self, grid_rows: list[dict], yearly_keys: Optional[list[str]] = None) -> list[dict]:
        """Convert grid rows to JU-level CSV rows."""
        if yearly_keys is None:
            yearly_keys = []

        csv_rows = []
        for grid_row in grid_rows:
            pl_number = grid_row.get("id", "")
            pl_name = grid_row.get("name", "")
            metier = grid_row.get("metier", "")

            inductors = grid_row.get("inductors", [])
            if not inductors:
                csv_rows.append({
                    "PL Number": pl_number, "PL Name": pl_name, "Métier": metier,
                    "Inductor": "", "JU Code": "", "FMM Description": "",
                    "JU Description": "",
                    "Total FTE": grid_row.get("total_fte", 0),
                    "Total BH": grid_row.get("total_bh", 0),
                    "Total KM": grid_row.get("total_km", 0),
                    **{f"FTE {y}": "" for y in yearly_keys},
                    **{f"BH {y}": "" for y in yearly_keys},
                    **{f"KM {y}": "" for y in yearly_keys},
                })
            else:
                for ind in inductors:
                    for ju in ind.get("job_units", []):
                        yearly = ju.get("yearly", {})
                        csv_rows.append({
                            "PL Number": pl_number, "PL Name": pl_name, "Métier": metier,
                            "Inductor": ind.get("name", ""),
                            "JU Code": ju.get("short_name", ""),
                            "FMM Description": ju.get("fmm", ""),
                            "JU Description": ju.get("description", ""),
                            "Total FTE": ju.get("fte", 0),
                            "Total BH": ju.get("bh", 0),
                            "Total KM": ju.get("km", 0),
                            **{f"FTE {y}": yearly.get(y, {}).get("fte", "") for y in yearly_keys},
                            **{f"BH {y}": yearly.get(y, {}).get("bh", "") for y in yearly_keys},
                            **{f"KM {y}": yearly.get(y, {}).get("km", "") for y in yearly_keys},
                        })

        return csv_rows

    def export_to_csv(self, csv_rows: list[dict]) -> str:
        """Generate CSV string from list of dicts."""
        if not csv_rows:
            return ""

        output = io.StringIO()
        fieldnames = list(csv_rows[0].keys()) if csv_rows else CSV_EXPORT_COLUMNS
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
        return output.getvalue()

    def forward_impl(self, rows_json: str = "[]", mode: str = "all_filtered",
                     yearly_keys_json: str = "[]") -> dict:
        try:
            grid_rows = json.loads(rows_json) if isinstance(rows_json, str) else rows_json
        except (json.JSONDecodeError, TypeError):
            grid_rows = []

        try:
            yearly_keys = json.loads(yearly_keys_json) if isinstance(yearly_keys_json, str) else yearly_keys_json
        except (json.JSONDecodeError, TypeError):
            yearly_keys = []

        csv_rows = self.build_rows(grid_rows, yearly_keys if yearly_keys else None)
        csv_content = self.export_to_csv(csv_rows)

        return {
            "csv_content": csv_content,
            "row_count": str(len(csv_rows)),
        }
