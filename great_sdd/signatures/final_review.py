"""
GREAT Final Review — SDD-style Signatures.

Each Signature defines the input/output contract for one step of the
Final Review pipeline. Modules in modules/final_review.py honor these contracts.

Signatures map to business rules:
  CHECK_FINAL_REVIEW_PERMISSION  → FR-BR-01 (Read-only page)
  FILTER_FINAL_REVIEW_JUS        → FR-BR-03 (Approved lines only)
  AGGREGATE_FINAL_REVIEW         → FR-BR-02 (No approval columns, status-derived)
  EXPORT_FINAL_REVIEW_CSV        → FR-BR-10 (CSV flat export)
  SEND_STAGE3                    → FR-BR-06/07/08 (Stage 3 non-blocking, re-sendable, all lines)
  CALCULATE_SUBTOTALS            → Aggregation helper
"""
from __future__ import annotations

from great_sdd.signatures.pre_estimation import Signature, Field


CHECK_FINAL_REVIEW_PERMISSION = Signature(
    name="CheckFinalReviewPermission",
    description="Check if a role can view/export/send Stage 3 in Final Review. "
                "All roles can view. Only PMO/Admin can send Stage 3. "
                "All roles can export (FR-BR-01: read-only page).",
    inputs=[
        Field("role", "User role: Admin, Engineer, PMO, RCRC, or CPO"),
        Field("action", "Requested action: view, export, send_stage3"),
    ],
    outputs=[
        Field("allowed", "boolean: action permitted", field_type="boolean", is_output=True),
        Field("reason", "explanation", is_output=True),
    ],
)

FILTER_FINAL_REVIEW_JUS = Signature(
    name="FilterFinalReviewJUs",
    description="Filter job units to only Approved (PL, Metier) pairs. "
                "Lines with incomplete allocation are included with zero K€ (FR-BR-03).",
    inputs=[
        Field("job_units_json", "JSON array of all job units with status field"),
    ],
    outputs=[
        Field("approved_jus_json", "JSON array of approved JUs", is_output=True),
        Field("excluded_count", "number of JUs excluded", field_type="string", is_output=True),
    ],
)

AGGREGATE_FINAL_REVIEW = Signature(
    name="AggregateFinalReview",
    description="Compute aggregation levels for Final Review: by cost_type, "
                "by society, by metier, and PL total (FR-BR-02: no approval columns, "
                "all values derived from approved estimations + allocation data).",
    inputs=[
        Field("job_units_json", "JSON array of approved JUs with societe, cost_type, totals"),
    ],
    outputs=[
        Field("aggregations_json", "JSON with by_cost_type, by_society, by_metier, pl_total", is_output=True),
    ],
)

EXPORT_FINAL_REVIEW_CSV = Signature(
    name="ExportFinalReviewCSV",
    description="Export all JUs to flat CSV. One row per JU, no subtotal rows (FR-BR-10).",
    inputs=[
        Field("job_units_json", "JSON array of JUs to export"),
        Field("columns_json", "Optional JSON array of column names", optional=True),
    ],
    outputs=[
        Field("csv_content", "CSV-formatted string", is_output=True),
        Field("row_count", "number of rows exported", field_type="string", is_output=True),
    ],
)

SEND_STAGE3 = Signature(
    name="SendStage3",
    description="Send consolidated data to HVT Stage 3. "
                "Non-blocking: PMO can send even with incomplete allocation (FR-BR-06). "
                "Re-sendable: each send transmits current state (FR-BR-07). "
                "All lines: sends entire active cycle, no per-line send (FR-BR-08).",
    inputs=[
        Field("job_units_json", "JSON array of all approved JUs for the active cycle"),
        Field("confirmed", "boolean: user confirmed despite warnings", field_type="boolean"),
    ],
    outputs=[
        Field("success", "boolean: send completed", field_type="boolean", is_output=True),
        Field("needs_confirmation", "boolean: has unassigned JUs", field_type="boolean", is_output=True),
        Field("warning", "warning message about incomplete allocation", is_output=True),
        Field("payload_json", "JSON payload sent to HVT", is_output=True),
    ],
)

CALCULATE_SUBTOTALS = Signature(
    name="CalculateSubtotals",
    description="Sum specified fields across a list of rows. "
                "Used for aggregation at different levels (cost_type, society, metier, PL total).",
    inputs=[
        Field("rows_json", "JSON array of rows to sum"),
        Field("fields_json", "JSON array of field names to aggregate"),
    ],
    outputs=[
        Field("totals_json", "JSON object with sum per field", is_output=True),
    ],
)
