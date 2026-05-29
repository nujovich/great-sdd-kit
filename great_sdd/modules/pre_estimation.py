"""
GREAT Pre-Estimation — Signature-Driven Modules (SDD Kit).

Each module now inherits from SignatureModule and honors a Signature contract.
The module's forward() is split into:
  - forward()      → handled by SignatureModule (input/output validation)
  - forward_impl() → actual business logic (replaces old forward())

This makes the connection explicit: Signature declares WHAT goes in and out,
Module declares HOW. The tests verify that both match.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.signature_module import SignatureModule
from great_sdd.specs.pre_estimation_specs import (
    LineStatus,
    Role,
    ROLE_PERMISSIONS,
    STATUS_TRANSITIONS,
    LOCKED_STATUSES,
    EDITABLE_STATUSES,
    TERMINAL_STATUSES,
    are_lines_compatible,
    COMPATIBILITY_FIELDS,
    WORKLOAD_STANDARDS,
    calculate_ju_total,
    calculate_fte,
    distribute_monthly,
    aggregate_yearly,
    MAN_DAY_FTE_DIVISOR,
)
from great_sdd.signatures.pre_estimation import (
    VALIDATE_LINE_SELECTION,
    CHECK_ROLE_PERMISSION,
    VALIDATE_STATUS_TRANSITION,
    SELECT_INDUCTOR_CRAN,
    GENERATE_ESTIMATE,
    VALIDATE_BEFORE_SAVE,
    DISTRIBUTE_BY_MONTH,
    GENERATE_PRE_SAVE_SUMMARY,
)

logger = logging.getLogger(__name__)


class SelectionValidator(SignatureModule):
    """
    Validates multi-line selection compatibility.
    Signature: VALIDATE_LINE_SELECTION

    Pure Python for compatibility check. LM for human-readable explanation.
    """

    signature = VALIDATE_LINE_SELECTION

    def forward_impl(self, lines_json: str) -> dict:
        # Parse input
        lines = json.loads(lines_json) if isinstance(lines_json, str) else lines_json

        compatible = are_lines_compatible(lines)

        if compatible:
            return {"is_compatible": True, "incompatibility_reason": ""}

        # Find incompatibility details (pure Python)
        issues = []
        for field in COMPATIBILITY_FIELDS:
            vals = {line.get(field) for line in lines}
            if len(vals) > 1:
                has_null = any(line.get(field) is None for line in lines)
                if has_null:
                    issues.append(f"{field}: mixed null and values")
                else:
                    issues.append(f"{field}: {vals}")

        # LM for human-readable explanation
        details = "; ".join(issues)
        prompt = (
            f"The following project lines have incompatible selections:\n{details}\n\n"
            f"Explain why these lines cannot be selected together according to GREAT rules."
        )
        explanation = self.call_lm(
            system="You are a project estimation system explaining compatibility rules.",
            prompt=prompt,
        )

        return {"is_compatible": False, "incompatibility_reason": explanation or details}


class PermissionChecker(SignatureModule):
    """
    Checks role-based access. Pure Python — permission matrix from specs.
    Signature: CHECK_ROLE_PERMISSION
    """

    signature = CHECK_ROLE_PERMISSION

    def forward_impl(self, role: str, line_assignee: str, current_user: str,
                     action: str = "view") -> dict:
        try:
            role_enum = Role(role)
        except ValueError:
            return {"allowed": False, "reason": f"Unknown role: {role}"}

        perm = ROLE_PERMISSIONS[role_enum]

        if perm.scope == "none":
            return {"allowed": False, "reason": f"{role} has no access to Pre-Estimation view"}

        if action == "edit" and not perm.can_edit:
            return {"allowed": False, "reason": f"{role} is read-only in Pre-Estimation view"}

        if action == "view" and not perm.can_view:
            return {"allowed": False, "reason": f"{role} cannot view Pre-Estimation"}

        if perm.scope == "assigned_only" and line_assignee != current_user:
            return {
                "allowed": False,
                "reason": f"Engineers can only access their assigned lines. "
                          f"This line is assigned to {line_assignee}."
            }

        return {"allowed": True, "reason": f"{role} is authorized to {action} this line"}


class StatusTransitionValidator(SignatureModule):
    """
    Validates state machine transitions. Pure Python — transition table from specs.
    Signature: VALIDATE_STATUS_TRANSITION
    """

    signature = VALIDATE_STATUS_TRANSITION

    def forward_impl(self, current_status: str, target_status: str,
                     has_saved_draft_in_session: bool = False) -> dict:
        try:
            current = LineStatus(current_status)
            target = LineStatus(target_status)
        except ValueError:
            return {"is_valid": False,
                    "error_message": f"Invalid status: {current_status} or {target_status}"}

        # Check transition table
        allowed_targets = STATUS_TRANSITIONS.get(current, [])
        if target not in allowed_targets:
            return {
                "is_valid": False,
                "error_message": f"Cannot transition from '{current.value}' to '{target.value}'"
            }

        # Draft gate (BR-02)
        if target == LineStatus.ESTIMATED and not has_saved_draft_in_session:
            return {
                "is_valid": False,
                "error_message": "Draft gate (BR-02): 'Save as Definitive' requires "
                                 "'Save as Draft' first in this session"
            }

        # Terminal state (BR-04)
        if current in TERMINAL_STATUSES:
            return {
                "is_valid": False,
                "error_message": f"Line is in terminal state ({current.value}). "
                                 f"No transitions allowed (BR-04)."
            }

        return {"is_valid": True, "error_message": ""}


class InductorSelector(SignatureModule):
    """
    Selects inductors and crans for a project line.
    Signature: SELECT_INDUCTOR_CRAN

    Python: loads workload standard from specs registry.
    LM: matches line description to inductors and selects appropriate crans.
    """

    signature = SELECT_INDUCTOR_CRAN

    def forward_impl(self, line_description: str, metier: str,
                     available_inductors_json: str = "[]") -> dict:
        try:
            available = json.loads(available_inductors_json) if isinstance(available_inductors_json, str) else available_inductors_json
        except (json.JSONDecodeError, TypeError):
            available = WORKLOAD_STANDARDS.get(metier, [])

        if not available:
            return {
                "inductor_selections_json": "[]",
            }

        # Build prompt for LM
        inductors_text = json.dumps([
            {
                "name": ind.name,
                "group": ind.group_name,
                "crans": [{"name": c.name, "variable": c.variable_coeff, "fixed": c.fixed_coeff}
                          for c in ind.crans],
                "j_us": [
                    {"name": ju.short_name, "desc": ju.description, "unit_type": ju.unit_type}
                    for ju in ind.job_units
                ],
            }
            for ind in available
        ], indent=2)

        system = (
            "You are a GREAT System estimator. Given a project line description and métier, "
            "select the appropriate inductors and cran variants from the workload standard. "
            "Return ONLY a JSON array. Each item: {'name': str, 'selected_cran': str, "
            "'job_units': [{'short_name': str, 'variable': float, 'fixed': float, "
            "'occurrence': int, 'unit_type': str}]}"
        )

        prompt = (
            f"Project line: {line_description}\n"
            f"Métier: {metier}\n\n"
            f"Available workload standard inductors:\n{inductors_text}\n\n"
            "Select the most relevant inductors and for each, choose the appropriate cran "
            "variant based on the task complexity. Set reasonable occurrence values (1-10)."
        )

        response = self.call_lm(system=system, prompt=prompt, max_tokens=1000, temperature=0.2)

        try:
            selections = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse LM response: {response[:200]}")
            selections = []

        return {"inductor_selections_json": json.dumps(selections)}


class EstimationCalculator(SignatureModule):
    """
    Calculates estimation totals. Pure Python formula engine.
    Signature: GENERATE_ESTIMATE
    Formula: Total = (Variable × Occurrence) + Fixed
    """

    signature = GENERATE_ESTIMATE

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        total_man_days = 0.0
        total_bh = 0.0
        total_km = 0.0
        breakdown = []

        for ju in job_units:
            ju_total = calculate_ju_total(
                variable=ju.get("variable", 0),
                occurrence=ju.get("occurrence", 0),
                fixed=ju.get("fixed", 0),
            )

            unit_type = ju.get("unit_type", "man_day")
            if unit_type == "man_day":
                total_man_days += ju_total
            elif unit_type == "bench_hours":
                total_bh += ju_total
            elif unit_type == "kilometres":
                total_km += ju_total

            breakdown.append({
                "short_name": ju.get("short_name", ""),
                "description": ju.get("description", ""),
                "variable": ju.get("variable", 0),
                "occurrence": ju.get("occurrence", 0),
                "fixed": ju.get("fixed", 0),
                "total": round(ju_total, 2),
                "unit_type": unit_type,
            })

        total_fte = calculate_fte(total_man_days)

        return {
            "total_fte": str(round(total_fte, 2)),
            "total_bh": str(round(total_bh, 2)),
            "total_km": str(round(total_km, 2)),
            "breakdown_json": json.dumps(breakdown),
        }


class SaveValidator(SignatureModule):
    """
    Validates pre-save conditions. Pure Python for deterministic checks.
    Signature: VALIDATE_BEFORE_SAVE
    """

    signature = VALIDATE_BEFORE_SAVE

    def __init__(self, lm=None):
        super().__init__(lm)
        self.status_validator = StatusTransitionValidator(lm)

    def forward_impl(self, line_json: str, save_type: str,
                     has_saved_draft_in_session: bool = False) -> dict:
        try:
            line = json.loads(line_json) if isinstance(line_json, str) else line_json
        except (json.JSONDecodeError, TypeError):
            line = {}

        errors = []

        # BR-08: SP date mandatory
        sp_date = line.get("sp_date")
        if not sp_date:
            errors.append("SP date is mandatory (BR-08). Saving is blocked.")

        # Status transition check
        current_status = line.get("status", "to_do")
        target_status = "draft" if save_type == "draft" else "estimated"
        status_result = self.status_validator.forward(
            current_status=current_status,
            target_status=target_status,
            has_saved_draft_in_session=has_saved_draft_in_session,
        )
        if not status_result["is_valid"]:
            errors.append(status_result["error_message"])

        # At least one inductor with cran or Custom JUs (BR-11)
        inductors = line.get("inductors", [])
        has_selected_cran = any(ind.get("selected_cran") for ind in inductors)
        has_custom_jus = any(ind.get("is_custom") for ind in inductors)
        if not has_selected_cran and not has_custom_jus:
            errors.append("No inductors with selected cran or Custom JUs found. "
                         "Add at least one.")

        return {"can_save": len(errors) == 0, "validation_errors_json": json.dumps(errors)}


class MonthDistributor(SignatureModule):
    """
    Distributes totals across months from SP date. Pure Python.
    Signature: DISTRIBUTE_BY_MONTH
    """

    signature = DISTRIBUTE_BY_MONTH

    def forward_impl(self, total_fte: str, total_bh: str, total_km: str,
                     sp_date: str, project_duration_months: str = "12") -> dict:
        fte = float(total_fte) if total_fte else 0.0
        bh = float(total_bh) if total_bh else 0.0
        km = float(total_km) if total_km else 0.0
        duration = int(project_duration_months) if project_duration_months else 12

        monthly_fte = distribute_monthly(fte, sp_date, duration)
        monthly_bh = distribute_monthly(bh, sp_date, duration)
        monthly_km = distribute_monthly(km, sp_date, duration)

        monthly = []
        for i in range(duration):
            monthly.append({
                "month": i + 1,
                "fte": round(monthly_fte[i], 2) if i < len(monthly_fte) else 0.0,
                "bh": round(monthly_bh[i], 2) if i < len(monthly_bh) else 0.0,
                "km": round(monthly_km[i], 2) if i < len(monthly_km) else 0.0,
            })

        return {
            "monthly_distribution_json": json.dumps(monthly),
            "yearly_aggregation_json": json.dumps(aggregate_yearly(
                [m["fte"] for m in monthly],
                int(sp_date[:4]) if sp_date else 2026,
            )),
        }


class SummaryGenerator(SignatureModule):
    """
    Generates pre-save summary content.
    Signature: GENERATE_PRE_SAVE_SUMMARY
    """

    signature = GENERATE_PRE_SAVE_SUMMARY

    def forward_impl(self, estimation_json: str, lines_count: str = "1") -> dict:
        try:
            estimation = json.loads(estimation_json) if isinstance(estimation_json, str) else estimation_json
        except (json.JSONDecodeError, TypeError):
            estimation = {}

        lines = int(lines_count) if lines_count else 1

        prompt = (
            f"Generate a pre-save summary for this estimation:\n\n"
            f"{json.dumps(estimation, indent=2)}\n\n"
            f"Lines count: {lines}\n\n"
            f"Include: Total FTE, Total BH, Total KM, "
            f"and annual breakdown per calendar year."
        )

        summary_text = self.call_lm(
            system="You are the GREAT System summary generator. "
                   "Format the estimation summary clearly.",
            prompt=prompt,
            max_tokens=500,
        )

        return {
            "summary_text": summary_text or "Summary generation unavailable.",
            "summary_json": estimation_json,
        }
