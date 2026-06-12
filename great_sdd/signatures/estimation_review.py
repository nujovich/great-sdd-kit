"""
GREAT System — Estimation Review Signatures.

SDD-style input/output contracts for the Estimation Review pipeline.
"""
from __future__ import annotations

from great_sdd.signatures.pre_estimation import Signature, Field


CHECK_ESTIMATION_REVIEW_PERMISSION = Signature(
    name="CheckEstimationReviewPermission",
    description="Check if a user role has permission to view or export in "
                "Estimation Review. Page is read-only for all roles. "
                "Engineers see only their own rows.",
    inputs=[
        Field("role", "User role: Admin, Engineer, PMO, RCRC, or CPO"),
        Field("action", "Requested action: view, export_selected, export_all_filtered"),
    ],
    outputs=[
        Field("allowed", "boolean: true if the action is permitted", field_type="boolean", is_output=True),
        Field("reason", "explanation of why allowed or denied", is_output=True),
    ],
)

DERIVE_APPROVAL_COLUMNS = Signature(
    name="DeriveApprovalColumns",
    description="Derive Engineer Approval and CPO Approval column values from status. "
                "Both are read-only and derived entirely from the status field.",
    inputs=[
        Field("status", "Current status: to_do, draft, estimated, sent, modification_requested, approved"),
    ],
    outputs=[
        Field("engineer_approval", "Engineer Approval display value"),
        Field("cpo_approval", "CPO Approval display value"),
    ],
)

PROCESS_HVT_CALLBACK_SIG = Signature(
    name="ProcessHVTCallback",
    description="Process an HVT callback for CPO approval or rejection. "
                "Approved → Sent→Approved. Rejected → Sent→Modification Requested with comment.",
    inputs=[
        Field("project_line", "PL Number"),
        Field("metier", "Métier of the estimation"),
        Field("approved", "boolean: true if CPO approved", field_type="boolean"),
        Field("comment", "Rejection reason from CPO (empty if approved)", optional=True),
    ],
    outputs=[
        Field("target_status", "New status: approved or modification_requested"),
        Field("transition_valid", "boolean", field_type="boolean", is_output=True),
        Field("error_message", "error if transition invalid", is_output=True),
        Field("notify_engineer", "bool: true if engineer should be notified (rejection)", field_type="boolean", is_output=True),
    ],
)

EXPORT_CSV = Signature(
    name="ExportCSV",
    description="Export estimation data to CSV format. "
                "Two modes: selected rows or all filtered rows. "
                "Includes JU-level detail with yearly FTE, BH, KM columns.",
    inputs=[
        Field("mode", "'selected' or 'all_filtered'"),
        Field("rows_json", "JSON array of rows to export"),
        Field("yearly_keys_json", "JSON array of year strings for yearly columns", optional=True),
    ],
    outputs=[
        Field("csv_content", "CSV-formatted string with all columns"),
        Field("row_count", "Number of rows exported", field_type="string"),
    ],
)