"""
GREAT Pre-Estimation — SDD-style Signatures.

NOTE: The real Stanford DSPy (sdd-kit) cannot be installed in this environment
due to corporate proxy restrictions. We implement a lightweight SDD-compatible
layer using OpenAI-compatible API calls directly.

Each Signature defines the input/output contract for one step of the pipeline.
In DSPy, a Signature IS the specification — it declares:
  - What goes in (InputField)
  - What comes out (OutputField)
  - Constraints via descriptions

When DSPy is available (pip install sdd-kit), these can be trivially converted
to real Signature subclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Field:
    """A lightweight DSPy InputField/OutputField equivalent."""
    name: str
    description: str = ""
    field_type: str = "string"  # string, boolean, json
    is_output: bool = False
    optional: bool = False  # If True, not required in forward() kwargs


@dataclass
class Signature:
    """
    A specification contract: inputs → outputs.

    In Stanford DSPy, this becomes:
        class MySig(Signature):
            input = dspy.InputField(desc="...")
            output = dspy.OutputField(desc="...")
    """
    name: str
    description: str
    inputs: list[Field] = field(default_factory=list)
    outputs: list[Field] = field(default_factory=list)


# ── Signature Definitions ──

VALIDATE_LINE_SELECTION = Signature(
    name="ValidateLineSelection",
    description="Validate that a set of project lines can be selected together. "
                "All lines must share Organ Type, Energy/Fuel Type, Project Ranking, "
                "and Injection System. null vs null = compatible. null vs value = incompatible.",
    inputs=[
        Field("lines_json", "JSON array of selected project lines with compatibility fields"),
    ],
    outputs=[
        Field("is_compatible", "boolean: true if all lines are compatible", field_type="boolean", is_output=True),
        Field("incompatibility_reason", "human-readable explanation if not compatible", is_output=True),
    ],
)

CHECK_ROLE_PERMISSION = Signature(
    name="CheckRolePermission",
    description="Check if a user role has permission to view or edit a project line. "
                "Engineer: can edit only assigned lines. Admin: can edit any line. "
                "PMO/RCRC: read-only. CPO: no access.",
    inputs=[
        Field("role", "User role: Admin, Engineer, PMO, RCRC, or CPO"),
        Field("line_assignee", "Name of engineer assigned to this line"),
        Field("current_user", "Name of the current user"),
        Field("action", "Requested action: view or edit"),
    ],
    outputs=[
        Field("allowed", "boolean: true if the action is permitted", field_type="boolean", is_output=True),
        Field("reason", "explanation of why allowed or denied", is_output=True),
    ],
)

VALIDATE_STATUS_TRANSITION = Signature(
    name="ValidateStatusTransition",
    description="Validate a status transition following the GREAT state machine.",
    inputs=[
        Field("current_status", "Current status: to_do, draft, estimated, sent, modification_requested, approved"),
        Field("target_status", "Desired target status"),
        Field("has_saved_draft_in_session", "Has 'Save as Draft' been clicked in current session", field_type="boolean"),
    ],
    outputs=[
        Field("is_valid", "boolean: true if transition is allowed", field_type="boolean", is_output=True),
        Field("error_message", "error message if invalid", is_output=True),
    ],
)

SELECT_INDUCTOR_CRAN = Signature(
    name="SelectInductorCran",
    description="Given a project line description and métier, select the appropriate "
                "inductors and cran variants from the workload standard.",
    inputs=[
        Field("line_description", "Description of the project line task"),
        Field("metier", "Métier: Backend, Frontend, Data, DevOps, QA, or Mobile"),
        Field("available_inductors_json", "JSON array of available inductors with crans and JUs"),
    ],
    outputs=[
        Field("inductor_selections_json", "JSON: each inductor with selected_cran and occurrence values"),
    ],
)

GENERATE_ESTIMATE = Signature(
    name="GenerateEstimate",
    description="Calculate estimation total for each JU. "
                "Formula: Total = (Variable × Occurrence) + Fixed. "
                "man_day → FTE = total/209. bench_hours → BH. kilometres → KM. k_euros excluded.",
    inputs=[
        Field("job_units_json", "JSON array of JUs with variable, fixed, occurrence, unit_type"),
    ],
    outputs=[
        Field("total_fte", "Total Full-Time Equivalents", field_type="string", is_output=True),
        Field("total_bh", "Total Bench Hours", field_type="string", is_output=True),
        Field("total_km", "Total Kilometres", field_type="string", is_output=True),
        Field("breakdown_json", "JSON: per-inductor breakdown with totals", is_output=True),
    ],
)

VALIDATE_BEFORE_SAVE = Signature(
    name="ValidateBeforeSave",
    description="Validate all preconditions before saving: "
                "SP date present, at least one inductor/cran, status transition valid.",
    inputs=[
        Field("line_json", "JSON: project line data"),
        Field("save_type", "'draft' or 'definitive'"),
        Field("has_saved_draft_in_session", "boolean", field_type="boolean", optional=True),
    ],
    outputs=[
        Field("can_save", "boolean: all preconditions met", field_type="boolean", is_output=True),
        Field("validation_errors_json", "JSON array of error messages", is_output=True),
    ],
)

DISTRIBUTE_BY_MONTH = Signature(
    name="DistributeByMonth",
    description="Distribute totals across months from SP date. SP date is always 1st of month.",
    inputs=[
        Field("total_fte", "Total FTE to distribute"),
        Field("total_bh", "Total BH to distribute"),
        Field("total_km", "Total KM to distribute"),
        Field("sp_date", "Project start date (YYYY-MM-DD)"),
        Field("project_duration_months", "Number of months", field_type="string"),
    ],
    outputs=[
        Field("monthly_distribution_json", "JSON array: monthly fte, bh, km", is_output=True),
        Field("yearly_aggregation_json", "JSON: yearly sums by calendar year", is_output=True),
    ],
)

GENERATE_PRE_SAVE_SUMMARY = Signature(
    name="GeneratePreSaveSummary",
    description="Generate pre-save summary: Total FTE, BH, KM, annual breakdown.",
    inputs=[
        Field("estimation_json", "JSON: full estimation data"),
        Field("lines_count", "Number of lines", field_type="string"),
    ],
    outputs=[
        Field("summary_text", "Human-readable summary", is_output=True),
        Field("summary_json", "JSON: structured summary", is_output=True),
    ],
)