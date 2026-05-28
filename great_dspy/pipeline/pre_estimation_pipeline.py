"""
GREAT Pre-Estimation — Signature-Driven Pipeline.

Orchestrates SignatureModules in the correct order.
Each stage maps to a Signature contract that validates inputs/outputs.

Pipeline flow:
  1. SelectionValidation(VALIDATE_LINE_SELECTION)
  2. PermissionCheck(CHECK_ROLE_PERMISSION)
  3. InductorSelection(SELECT_INDUCTOR_CRAN)
  4. EstimationCalculation(GENERATE_ESTIMATE)
  5. SaveValidation(VALIDATE_BEFORE_SAVE)
  6. MonthlyDistribution(DISTRIBUTE_BY_MONTH)
  7. SummaryGeneration(GENERATE_PRE_SAVE_SUMMARY)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.signature_module import SignatureModule, SignatureContractError
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
from great_dspy.signatures.pre_estimation import (
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


@dataclass
class PreEstimationContext:
    """Holds all state accumulated through the pipeline stages.
    
    Each field maps declared by one or more Signature contracts.
    This makes the context self-documenting: you can see exactly
    what data flows between stages.
    """
    # Inputs
    selected_lines: list[dict] = field(default_factory=list)
    role: str = ""
    current_user: str = ""
    metier: str = ""
    has_saved_draft_in_session: bool = False
    line_description: str = ""
    sp_date: str = ""
    project_duration_months: int = 12

    # Stage outputs — named after their Signature
    # VALIDATE_LINE_SELECTION
    selection_valid: bool = False
    incompatibility_reason: str = ""

    # CHECK_ROLE_PERMISSION
    permission_allowed: bool = False
    permission_reason: str = ""

    # SELECT_INDUCTOR_CRAN
    inductor_selections_json: str = "[]"

    # GENERATE_ESTIMATE
    total_fte: str = "0.0"
    total_bh: str = "0.0"
    total_km: str = "0.0"
    breakdown_json: str = "[]"

    # VALIDATE_BEFORE_SAVE
    can_save_draft: bool = False
    can_save_definitive: bool = False
    validation_errors_json: str = "[]"

    # DISTRIBUTE_BY_MONTH
    monthly_distribution_json: str = "[]"
    yearly_aggregation_json: str = "{}"

    # GENERATE_PRE_SAVE_SUMMARY
    summary_text: str = ""
    summary_json: str = "{}"

    # Metadata
    errors: list = field(default_factory=list)

    @property
    def inductors(self) -> list:
        return json.loads(self.inductor_selections_json)

    @property
    def breakdown(self) -> list:
        return json.loads(self.breakdown_json)

    @property
    def validation_errors(self) -> list:
        return json.loads(self.validation_errors_json)

    @property
    def monthly_distribution(self) -> list:
        return json.loads(self.monthly_distribution_json)

    @property
    def yearly_aggregation(self) -> dict:
        return json.loads(self.yearly_aggregation_json)


class PreEstimationPipeline:
    """
    Full Pre-Estimation View pipeline — Signature-driven.

    Each stage is a SignatureModule that honors a Signature contract.
    The pipeline orchestrates them in order, passing outputs from one
    stage as inputs to the next.

    This makes the pipeline self-documenting:
    - Each stage has a named Signature
    - Inputs/outputs are validated at each step
    - If a signature changes, the pipeline breaks visibly (not silently)
    """

    def __init__(self, lm: Optional[LMClient] = None):
        # All modules are SignatureModules now
        self.selection_validator = SelectionValidator(lm)
        self.permission_checker = PermissionChecker(lm)
        self.status_validator = StatusTransitionValidator(lm)
        self.inductor_selector = InductorSelector(lm)
        self.estimation_calculator = EstimationCalculator(lm)
        self.save_validator = SaveValidator(lm)
        self.month_distributor = MonthDistributor(lm)
        self.summary_generator = SummaryGenerator(lm)

        # Expose the signatures each stage uses (for introspection)
        self.stage_signatures = {
            "selection": VALIDATE_LINE_SELECTION,
            "permission": CHECK_ROLE_PERMISSION,
            "status": VALIDATE_STATUS_TRANSITION,
            "inductor": SELECT_INDUCTOR_CRAN,
            "estimation": GENERATE_ESTIMATE,
            "save": VALIDATE_BEFORE_SAVE,
            "distribution": DISTRIBUTE_BY_MONTH,
            "summary": GENERATE_PRE_SAVE_SUMMARY,
        }

    def forward(
        self,
        selected_lines: list[dict],
        role: str,
        current_user: str,
        metier: str,
        has_saved_draft_in_session: bool = False,
        line_description: Optional[str] = None,
        sp_date: Optional[str] = None,
        project_duration_months: int = 12,
    ) -> PreEstimationContext:
        ctx = PreEstimationContext(
            selected_lines=selected_lines,
            role=role,
            current_user=current_user,
            metier=metier,
            has_saved_draft_in_session=has_saved_draft_in_session,
            line_description=line_description or "",
            sp_date=sp_date or "",
            project_duration_months=project_duration_months,
        )

        # ── Stage 1: Selection Validation ──
        logger.info("Stage 1: Validating %d lines", len(selected_lines))
        try:
            sel = self.selection_validator.forward(
                lines_json=json.dumps(selected_lines),
            )
            ctx.selection_valid = sel["is_compatible"]
            ctx.incompatibility_reason = sel["incompatibility_reason"]
        except SignatureContractError as e:
            ctx.errors.append(f"Signature contract violation: {e}")
            return ctx

        if not ctx.selection_valid:
            ctx.errors.append(f"Selection incompatible: {ctx.incompatibility_reason}")
            return ctx

        # ── Stage 2: Permission Check ──
        logger.info("Stage 2: Checking %s (%s)", current_user, role)
        try:
            perm = self.permission_checker.forward(
                role=role,
                line_assignee=selected_lines[0].get("assignee", "") if selected_lines else "",
                current_user=current_user,
                action="view",
            )
            ctx.permission_allowed = perm["allowed"]
            ctx.permission_reason = perm["reason"]
        except SignatureContractError as e:
            ctx.errors.append(f"Permission contract violation: {e}")
            return ctx

        if not ctx.permission_allowed:
            ctx.errors.append(f"Permission denied: {ctx.permission_reason}")
            return ctx

        # ── Stage 3: Inductor Selection ──
        logger.info("Stage 3: Selecting inductors for %s", metier)
        try:
            ind_result = self.inductor_selector.forward(
                line_description=ctx.line_description or (selected_lines[0].get("description", "") if selected_lines else ""),
                metier=metier,
                available_inductors_json="[]",
            )
            ctx.inductor_selections_json = ind_result["inductor_selections_json"]
        except SignatureContractError as e:
            ctx.errors.append(f"Inductor contract violation: {e}")

        # ── Stage 4: Estimation Calculation ──
        logger.info("Stage 4: Calculating estimation")
        all_jus = []
        for ind in ctx.inductors:
            all_jus.extend(ind.get("job_units", []))

        if all_jus:
            try:
                calc = self.estimation_calculator.forward(
                    job_units_json=json.dumps(all_jus),
                )
                ctx.total_fte = calc["total_fte"]
                ctx.total_bh = calc["total_bh"]
                ctx.total_km = calc["total_km"]
                ctx.breakdown_json = calc["breakdown_json"]
            except SignatureContractError as e:
                ctx.errors.append(f"Estimation contract violation: {e}")

        # ── Stage 5: Save Validation ──
        logger.info("Stage 5: Validating save preconditions")
        line_data = dict(selected_lines[0]) if selected_lines else {}
        line_data["status"] = line_data.get("status", "to_do")
        line_data["inductors"] = ctx.inductors
        line_data["sp_date"] = ctx.sp_date or line_data.get("sp_date")

        try:
            draft_check = self.save_validator.forward(
                line_json=json.dumps(line_data),
                save_type="draft",
                has_saved_draft_in_session=has_saved_draft_in_session,
            )
            ctx.can_save_draft = draft_check["can_save"]
            ctx.validation_errors_json = draft_check["validation_errors_json"]
        except SignatureContractError as e:
            ctx.errors.append(f"Save contract violation: {e}")

        if ctx.can_save_draft:
            try:
                def_check = self.save_validator.forward(
                    line_json=json.dumps(line_data),
                    save_type="definitive",
                    has_saved_draft_in_session=True,
                )
                ctx.can_save_definitive = def_check["can_save"]
                if not def_check["can_save"]:
                    ctx.validation_errors_json = def_check["validation_errors_json"]
            except SignatureContractError as e:
                ctx.errors.append(f"Definitive save contract violation: {e}")

        # ── Stage 6: Monthly Distribution ──
        logger.info("Stage 6: Distributing by month")
        sp = ctx.sp_date or "2026-01-01"
        try:
            dist = self.month_distributor.forward(
                total_fte=ctx.total_fte,
                total_bh=ctx.total_bh,
                total_km=ctx.total_km,
                sp_date=sp,
                project_duration_months=str(project_duration_months),
            )
            ctx.monthly_distribution_json = dist["monthly_distribution_json"]
            ctx.yearly_aggregation_json = dist["yearly_aggregation_json"]
        except SignatureContractError as e:
            ctx.errors.append(f"Distribution contract violation: {e}")

        return ctx

    def generate_summary(self, estimation: dict, lines_count: int = 1) -> dict:
        """Generate pre-save summary — delegates to SummaryGenerator."""
        return self.summary_generator.forward(
            estimation_json=json.dumps(estimation),
            lines_count=str(lines_count),
        )

    def describe_pipeline(self) -> str:
        """Human-readable description of the entire pipeline."""
        lines = ["Pre-Estimation Pipeline (Signature-Driven)", "=" * 50]
        for stage_name, sig in self.stage_signatures.items():
            module = getattr(self, stage_name + "_validator", None) or \
                     getattr(self, stage_name + "_checker", None) or \
                     getattr(self, stage_name + "_selector", None) or \
                     getattr(self, stage_name + "_calculator", None) or \
                     getattr(self, stage_name + "_generator", None) or \
                     getattr(self, stage_name + "_distributor", None)
            if module:
                lines.append(f"  {stage_name}: {module.describe()}")
        return "\n".join(lines)


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
