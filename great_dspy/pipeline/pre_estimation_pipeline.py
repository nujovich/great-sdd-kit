"""
GREAT Pre-Estimation — Pipeline Orchestrator.

Orchestrates all modules in the correct order for the Pre-Estimation workflow.
Each stage maps to a section of the spec document.

Pipeline flow:
  1. Selection validation → 2. Permission check → 3. Workload standard loading
  → 4. Inductor/cran selection → 5. Estimation calculation → 6. Save validation
  → 7. Monthly distribution → 8. Summary generation

Usage:
    from great_dspy.pipeline.pre_estimation_pipeline import run_pipeline

    ctx = run_pipeline(
        selected_lines=[...],
        role="Engineer",
        current_user="Ana Martinez",
        metier="Backend",
    )
    print(ctx.can_save_draft)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import Module, LMClient
from great_dspy.modules.pre_estimation import (
    SelectionValidator,
    PermissionChecker,
    StatusTransitionValidator,
    InductorSelector,
    EstimationCalculator,
    SaveValidator,
    MonthDistributor,
    SummaryGenerator,
)
from great_dspy.specs.pre_estimation_specs import (
    WORKLOAD_STANDARDS,
    BUSINESS_RULES,
)

logger = logging.getLogger(__name__)


@dataclass
class PreEstimationContext:
    """Holds all state accumulated through the pipeline stages."""
    selected_lines: list[dict] = field(default_factory=list)
    selection_valid: bool = False
    incompatibility_reason: str = ""
    role: str = ""
    current_user: str = ""
    permission_allowed: bool = False
    permission_reason: str = ""
    metier: str = ""
    inductors: list = field(default_factory=list)
    no_standard_found: bool = False
    total_fte: float = 0.0
    total_bh: float = 0.0
    total_km: float = 0.0
    breakdown: list = field(default_factory=list)
    has_saved_draft_in_session: bool = False
    can_save_draft: bool = False
    can_save_definitive: bool = False
    validation_errors: list = field(default_factory=list)
    monthly_distribution: list = field(default_factory=list)
    yearly_aggregation: dict = field(default_factory=dict)
    summary_text: str = ""
    summary_json: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


class PreEstimationPipeline:
    """
    Full Pre-Estimation View pipeline.

    All 7 stages from the SDD spec, orchestrated in order.
    """

    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm
        self.selection_validator = SelectionValidator(lm)
        self.permission_checker = PermissionChecker(lm)
        self.status_validator = StatusTransitionValidator(lm)
        self.inductor_selector = InductorSelector(lm)
        self.estimation_calculator = EstimationCalculator(lm)
        self.save_validator = SaveValidator(lm)
        self.month_distributor = MonthDistributor(lm)
        self.summary_generator = SummaryGenerator(lm)

    def forward(
        self,
        selected_lines: list[dict],
        role: str,
        current_user: str,
        metier: str,
        has_saved_draft_in_session: bool = False,
        line_description: Optional[str] = None,
        sp_date: Optional[str] = None,
    ) -> PreEstimationContext:
        ctx = PreEstimationContext(
            selected_lines=selected_lines,
            role=role,
            current_user=current_user,
            metier=metier,
            has_saved_draft_in_session=has_saved_draft_in_session,
        )

        # ── Stage 1: Selection Validation (§5, §6) ──
        logger.info("Stage 1: Validating %d lines", len(selected_lines))
        selection = self.selection_validator.forward(selected_lines)
        ctx.selection_valid = selection["is_compatible"]
        ctx.incompatibility_reason = selection["incompatibility_reason"]

        if not ctx.selection_valid:
            ctx.errors.append(f"Selection incompatible: {ctx.incompatibility_reason}")
            return ctx

        # ── Stage 2: Permission Check (§2, BR-10) ──
        logger.info("Stage 2: Checking %s (%s)", current_user, role)
        first_line = selected_lines[0] if selected_lines else {}

        perm = self.permission_checker.forward(
            role=role,
            line_assignee=first_line.get("assignee", ""),
            current_user=current_user,
            action="view",
        )
        ctx.permission_allowed = perm["allowed"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(f"Permission denied: {ctx.permission_reason}")
            return ctx

        edit_perm = self.permission_checker.forward(
            role=role,
            line_assignee=first_line.get("assignee", ""),
            current_user=current_user,
            action="edit",
        )
        if not edit_perm["allowed"]:
            ctx.permission_reason += f" (Read-only: {edit_perm['reason']})"

        # ── Stage 3-4: Load Workload Standard + Select Inductors (§6-8) ──
        logger.info("Stage 3: Loading workload standard for %s", metier)
        line_desc = line_description or first_line.get("description", "")

        inductor_result = self.inductor_selector.forward(
            line_description=line_desc,
            metier=metier,
        )
        ctx.inductors = inductor_result["inductor_selections"]
        ctx.no_standard_found = inductor_result["no_standard_found"]

        # ── Stage 5: Calculate Estimation (§9) ──
        logger.info("Stage 4: Calculating estimation")
        if ctx.inductors:
            all_jus = []
            for ind in ctx.inductors:
                all_jus.extend(ind.get("job_units", []))

            if all_jus:
                calc = self.estimation_calculator.forward(all_jus)
                ctx.total_fte = calc["total_fte"]
                ctx.total_bh = calc["total_bh"]
                ctx.total_km = calc["total_km"]
                ctx.breakdown = calc["breakdown"]

        # ── Stage 6: Save Validation (§10, §17) ──
        logger.info("Stage 5: Validating save preconditions")
        line_for_save = dict(first_line)
        line_for_save["status"] = first_line.get("status", "to_do")
        line_for_save["inductors"] = ctx.inductors
        line_for_save["sp_date"] = sp_date or first_line.get("sp_date")

        draft_check = self.save_validator.forward(
            line=line_for_save,
            save_type="draft",
            has_saved_draft_in_session=has_saved_draft_in_session,
        )
        ctx.can_save_draft = draft_check["can_save"]
        ctx.validation_errors = draft_check["validation_errors"]

        if ctx.can_save_draft:
            definitive_check = self.save_validator.forward(
                line=line_for_save,
                save_type="definitive",
                has_saved_draft_in_session=True,
            )
            ctx.can_save_definitive = definitive_check["can_save"]

        # ── Stage 7: Monthly Distribution (§9.4, §9.5) ──
        logger.info("Stage 6: Distributing by month")
        sp = sp_date or first_line.get("sp_date") or "2026-01-01"
        if ctx.total_fte > 0 or ctx.total_bh > 0 or ctx.total_km > 0:
            dist = self.month_distributor.forward(
                total_fte=ctx.total_fte,
                total_bh=ctx.total_bh,
                total_km=ctx.total_km,
                sp_date=sp,
                project_duration_months=12,
            )
            ctx.monthly_distribution = dist["monthly_distribution"]
            ctx.yearly_aggregation = dist["yearly_aggregation"]

        return ctx

    def generate_summary(self, estimation: dict, lines_count: int = 1) -> dict:
        """Generate pre-save summary (called after Save as Draft click)."""
        return self.summary_generator.forward(estimation, lines_count)


def run_pipeline(
    selected_lines: list[dict],
    role: str,
    current_user: str,
    metier: str,
    lm: Optional[LMClient] = None,
    **kwargs,
) -> PreEstimationContext:
    """One-shot runner for the full Pre-Estimation pipeline."""
    pipeline = PreEstimationPipeline(lm)
    return pipeline.forward(
        selected_lines=selected_lines,
        role=role,
        current_user=current_user,
        metier=metier,
        **kwargs,
    )