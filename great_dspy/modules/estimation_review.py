"""
GREAT Estimation Review — Pipeline Modules.

All modules are read-only (by spec). The only write actions are:
- PMO/Admin: "Send all eligible to HVT"
- PMO/Admin: CSV export
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import Optional

from great_dspy.modules.base import Module, LMClient
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

logger = logging.getLogger(__name__)


class EstimationReviewPermissionChecker(Module):
    """Check if a role can perform actions in Estimation Review (§2)."""

    def forward(self, role: str, action: str = "view") -> dict:
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


class ApprovalColumnDeriver(Module):
    """Derive approval column values from status (§5). Pure Python."""

    def forward(self, status: str) -> dict:
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
        approvals = self.forward(row.get("status", "to_do"))
        return {
            **row,
            "engineer_approval": approvals["engineer_approval"],
            "cpo_approval": approvals["cpo_approval"],
        }


class SendEligibilityChecker(Module):
    """Check if rows are eligible for Send to HVT (§6)."""

    def forward(self, status: str, role: str) -> dict:
        # Check role permission
        perm_check = EstimationReviewPermissionChecker(self.lm).forward(role, "send_to_hvt")
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
        """
        Split rows into eligible and ineligible for Send to HVT.

        Returns:
            (eligible_rows, skipped_rows)
        """
        eligible = []
        skipped = []

        for row in rows:
            result = self.forward(row.get("status", "to_do"), role)
            if result["eligible"]:
                eligible.append(row)
            else:
                skipped.append({"row": row, "reason": result["reason"]})

        return eligible, skipped


class HVTCallbackProcessor(Module):
    """Process HVT callback for CPO approval/rejection (§7)."""

    def forward(self, project_line: str, metier: str,
                approved: bool, comment: str = "") -> dict:
        callback = HVTCallback(
            project_line=project_line,
            metier=metier,
            approved=approved,
            comment=comment,
        )

        result = process_hvt_callback(callback)

        # Validate the transition is valid in the state machine
        from great_dspy.modules.pre_estimation import StatusTransitionValidator
        validator = StatusTransitionValidator(self.lm)
        transition_result = validator.forward("sent", result["target_status"].value)

        if not transition_result["is_valid"]:
            return {
                "target_status": result["target_status"].value,
                "transition_valid": False,
                "error_message": transition_result["error_message"],
                "notify_engineer": False,
            }

        return {
            "target_status": result["target_status"].value,
            "transition_valid": True,
            "error_message": "",
            "notify_engineer": result["notify_engineer"],
            "comment": result["comment"],
        }


class CSVExporter(Module):
    """Generate CSV export of estimation data (§9). Pure Python."""

    def build_rows(self, grid_rows: list[dict], yearly_keys: Optional[list[str]] = None) -> list[dict]:
        """
        Convert grid rows to JU-level CSV rows.

        Args:
            grid_rows: List of (PL, Métier) rows with estimation data
            yearly_keys: List of year strings (e.g. ["2024", "2025"])

        Returns:
            List of dicts, one per JU, with CSV columns
        """
        if yearly_keys is None:
            yearly_keys = []

        csv_rows = []
        for grid_row in grid_rows:
            pl_number = grid_row.get("id", "")
            pl_name = grid_row.get("name", "")
            metier = grid_row.get("metier", "")

            # Get job units from estimation breakdown
            inductors = grid_row.get("inductors", [])
            if not inductors:
                # Flat row without inductor detail
                csv_rows.append({
                    "PL Number": pl_number,
                    "PL Name": pl_name,
                    "Métier": metier,
                    "Inductor": "",
                    "JU Code": "",
                    "FMM Description": "",
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
                            "PL Number": pl_number,
                            "PL Name": pl_name,
                            "Métier": metier,
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

    def forward(self, grid_rows: list[dict], mode: str = "all_filtered",
                yearly_keys: Optional[list[str]] = None) -> dict:
        csv_rows = self.build_rows(grid_rows, yearly_keys)
        csv_content = self.export_to_csv(csv_rows)

        return {
            "csv_content": csv_content,
            "row_count": len(csv_rows),
            "mode": mode,
        }


class HVTPayloadGenerator(Module):
    """Generate HVT payload for a (PL, Métier) pair (§6.4)."""

    def forward(self, project_line: str, metier: str,
                yearly_summary: dict) -> dict:
        payload = {
            "project_line": project_line,
            "metier": metier,
            "workload_summary": yearly_summary,
        }

        # LM could be used to validate or enrich the payload
        return {
            "payload": payload,
            "payload_json": json.dumps(payload, indent=2),
        }