"""
GREAT Pre-Estimation — Pipeline Modules.

Each module wraps business logic from the spec registry.
Pure Python for deterministic rules (state machine, compatibility, formulas).
LM calls for reasoning tasks (inductor selection, summary generation).

This is the core idea of DSPy+SDD: you decide what the LM does and what
code does. The LM handles ambiguity; code handles math and state.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from great_dspy.modules.base import Module, LMClient
from great_dspy.specs.pre_estimation_specs import (
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

logger = logging.getLogger(__name__)


class SelectionValidator(Module):
    """
    Validates multi-line selection compatibility.

    Pure Python: are_lines_compatible() from specs.
    LM: generates human-readable explanation for incompatibilities.
    """

    def forward(self, lines: list[dict]) -> dict:
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


class PermissionChecker(Module):
    """
    Checks role-based access. Pure Python — permission matrix from specs.
    """

    def forward(self, role: str, line_assignee: str, current_user: str,
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


class StatusTransitionValidator(Module):
    """
    Validates state machine transitions. Pure Python — transition table from specs.
    """

    def forward(self, current_status: str, target_status: str,
                has_saved_draft_in_session: bool = False) -> dict:
        try:
            current = LineStatus(current_status)
            target = LineStatus(target_status)
        except ValueError:
            return {"is_valid": False, "error_message": f"Invalid status: {current_status} or {target_status}"}

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


class InductorSelector(Module):
    """
    Selects inductors and crans for a project line.

    Python: loads workload standard from specs registry.
    LM: matches line description to inductors and selects appropriate crans.
    """

    def forward(self, line_description: str, metier: str,
                available_inductors: Optional[list] = None) -> dict:
        if available_inductors is None:
            available = WORKLOAD_STANDARDS.get(metier, [])
        else:
            available = available_inductors

        if not available:
            return {
                "inductor_selections": [],
                "no_standard_found": True,
                "message": "No workload standard found for this combination. "
                           "Estimation via Custom JUs only (BR-11)."
            }

        # Build prompt for LM
        inductors_text = json.dumps([
            {
                "name": ind.name,
                "group": ind.group_name,
                "crans": [{"name": c.name, "variable": c.variable_coeff, "fixed": c.fixed_coeff} for c in ind.crans],
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

        return {"inductor_selections": selections, "no_standard_found": False, "message": ""}


class EstimationCalculator(Module):
    """
    Calculates estimation totals. Pure Python formula engine.
    Total = (Variable × Occurrence) + Fixed
    """

    def forward(self, job_units: list[dict]) -> dict:
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
            "total_fte": round(total_fte, 2),
            "total_bh": round(total_bh, 2),
            "total_km": round(total_km, 2),
            "total_man_days": round(total_man_days, 2),
            "breakdown": breakdown,
        }


class SaveValidator(Module):
    """
    Validates pre-save conditions. Pure Python for deterministic checks
    (SP date, status, Draft gate, inductors/cran presence).
    """

    def __init__(self, lm=None):
        super().__init__(lm)
        self.status_validator = StatusTransitionValidator(lm)

    def forward(self, line: dict, save_type: str,
                has_saved_draft_in_session: bool = False) -> dict:
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

        can_save = len(errors) == 0
        return {"can_save": can_save, "validation_errors": errors}


class MonthDistributor(Module):
    """
    Distributes totals across months from SP date. Pure Python.
    """

    def forward(self, total_fte: float, total_bh: float, total_km: float,
                sp_date: str, project_duration_months: int = 12) -> dict:
        monthly_fte = distribute_monthly(total_fte, sp_date, project_duration_months)
        monthly_bh = distribute_monthly(total_bh, sp_date, project_duration_months)
        monthly_km = distribute_monthly(total_km, sp_date, project_duration_months)

        monthly = []
        for i in range(12):
            monthly.append({
                "month": i + 1,
                "fte": round(monthly_fte[i], 2) if i < len(monthly_fte) else 0.0,
                "bh": round(monthly_bh[i], 2) if i < len(monthly_bh) else 0.0,
                "km": round(monthly_km[i], 2) if i < len(monthly_km) else 0.0,
            })

        return {
            "monthly_distribution": monthly,
            "yearly_aggregation": aggregate_yearly(
                [m["fte"] for m in monthly],
                int(sp_date[:4]) if sp_date else 2026,
            ),
        }


class SummaryGenerator(Module):
    """
    Generates pre-save summary content using LM for human-readable text.
    """

    def forward(self, estimation: dict, lines_count: int = 1) -> dict:
        prompt = (
            f"Generate a pre-save summary for this estimation:\n\n"
            f"{json.dumps(estimation, indent=2)}\n\n"
            f"Lines count: {lines_count}\n\n"
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
            "summary_json": estimation,
        }