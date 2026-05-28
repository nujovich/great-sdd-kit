"""
GREAT Estimation Review — Signature-Driven Modules.

Each module honors a Signature contract from signatures/estimation_review.py.
All modules are read-only by spec. The only write actions are:
- PMO/Admin: "Send all eligible to HVT"
- PMO/Admin: CSV export
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.signature_module import SignatureModule
from great_dspy.modules.pre_estimation import StatusTransitionValidator
from great_dspy.specs.pre_estimation_specs import (
    LineStatus,
    Role,
    STATUS_TRANSITIONS,
    TERMINAL_STATUSES,
)
from great_dspy.specs.estimation_review_specs import (
    ESTIMATION_REVIEW_PERMISSIONS,
    SEND_ELIGIBLE_STATUSES,
    ENGINEER_APPROVAL_MAP,
    CPO_APPROVAL_MAP,
    process_hvt_callback,
    CSV_EXPORT_COLUMNS,
    HVTCallback,
)
from great_dspy.signatures.estimation_review import (
    CHECK_ESTIMATION_REVIEW_PERMISSION,
    DERIVE_APPROVAL_COLUMNS,
    CHECK_SEND_ELIGIBILITY,
    PROCESS_HVT_CALLBACK_SIG,
    GENERATE_HVT_PAYLOAD,
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

        if action == "send_to_hvt" and not perm.can_send_to_hvt:
            return {"allowed": False, "reason": f"Only PMO/Admin can send to HVT. {role} cannot."}

        if action == "export_csv" and not perm.can_export_csv:
            return {"allowed": False, "reason": f"{role} cannot export CSV"}

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


class SendEligibilityChecker(SignatureModule):
    """Check if rows are eligible for Send to HVT.
    Signature: CHECK_SEND_ELIGIBILITY
    """

    signature = CHECK_SEND_ELIGIBILITY

    def forward_impl(self, status: str, role: str) -> dict:
        # Check role permission
        perm_check = EstimationReviewPermissionChecker(self.lm).forward(role=role, action="send_to_hvt")
        if not perm_check["allowed"]:
            return {"eligible": False, "reason": perm_check["reason"]}

        # Check status
        try:
            status_enum = LineStatus(status)
        except ValueError:
            return {"eligible": False, "reason": f"Invalid status: {status}"}

        if status_enum not in SEND_ELIGIBLE_STATUSES:
            return {
                "eligible": False,
                "reason": f"Only Estimated rows are eligible. Current status: {status}",
            }

        return {"eligible": True, "reason": ""}

    def find_eligible_rows(self, rows: list[dict], role: str) -> tuple[list[dict], list[dict]]:
        """Split rows into eligible and ineligible for Send to HVT."""
        eligible = []
        skipped = []
        for row in rows:
            result = self.forward(status=row.get("status", "to_do"), role=role)
            if result["eligible"]:
                eligible.append(row)
            else:
                skipped.append({"row": row, "reason": result["reason"]})
        return eligible, skipped


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


class HVTPayloadGenerator(SignatureModule):
    """Generate HVT payload for a (PL, Métier) pair.
    Signature: GENERATE_HVT_PAYLOAD
    """

    signature = GENERATE_HVT_PAYLOAD

    def forward_impl(self, project_line: str, metier: str,
                     yearly_summary_json: str = "{}") -> dict:
        try:
            yearly_summary = json.loads(yearly_summary_json) if isinstance(yearly_summary_json, str) else yearly_summary_json
        except (json.JSONDecodeError, TypeError):
            yearly_summary = {}

        payload = {
            "project_line": project_line,
            "metier": metier,
            "workload_summary": yearly_summary,
        }

        return {"payload_json": json.dumps(payload, indent=2)}


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
