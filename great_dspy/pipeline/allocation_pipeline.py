"""
GREAT Allocation — Pipeline Orchestrator.

Stages:
  1. Permission check
  2. Filter to Approved lines
  3. Auto-assign societes (rules + H-PROJECT routing)
  4. Diversity dropdown handling
  5. Calculate K€
  6. Handle manual edits (TC popup, split, bulk)
  7. Validate save
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.allocation import (
    AllocationPermissionChecker,
    AllocationEligibilityFilter,
    AllocationRuleMatcher,
    HProjectRouter,
    KECalculator,
    TCPopupHandler,
    SplitAllocationHandler,
    BulkAssigner,
    AllocationSaveValidator,
    DiversityDropdownHandler,
)

logger = logging.getLogger(__name__)


@dataclass
class AllocationContext:
    permission_allowed: bool = False
    permission_edit: bool = False
    permission_reason: str = ""
    eligible_jus: list = field(default_factory=list)
    auto_assigned_jus: list = field(default_factory=list)
    routed_jus: list = field(default_factory=list)
    diversity_flagged: list = field(default_factory=list)
    calculated_jus: list = field(default_factory=list)
    can_save: bool = False
    save_errors: list = field(default_factory=list)
    save_warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class AllocationPipeline:
    """Full Allocation pipeline."""

    def __init__(self, lm: Optional[LMClient] = None, rules: Optional[list[dict]] = None):
        self.lm = lm
        self.permission_checker = AllocationPermissionChecker(lm)
        self.eligibility_filter = AllocationEligibilityFilter(lm)
        self.rule_matcher = AllocationRuleMatcher(rules or [], lm)
        self.hproject_router = HProjectRouter(lm)
        self.ke_calculator = KECalculator(lm)
        self.tc_handler = TCPopupHandler(lm)
        self.split_handler = SplitAllocationHandler(lm)
        self.bulk_assigner = BulkAssigner(lm)
        self.save_validator = AllocationSaveValidator(lm)
        self.diversity_handler = DiversityDropdownHandler(lm)

    def forward(self, role: str, job_units: list[dict]) -> AllocationContext:
        ctx = AllocationContext()

        # Stage 1: Permission check
        perm = self.permission_checker.forward(role)
        ctx.permission_allowed = perm["can_view"]
        ctx.permission_edit = perm["can_edit"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(ctx.permission_reason)
            return ctx

        # Stage 2: Filter to Approved lines only
        ctx.eligible_jus = self.eligibility_filter.forward(job_units)

        # Stage 3: Auto-assign societes via rules + H-PROJECT routing
        ctx.auto_assigned_jus = self.rule_matcher.forward(ctx.eligible_jus)
        ctx.routed_jus = self.hproject_router.forward(ctx.auto_assigned_jus)

        # Stage 4: Diversity dropdown
        ctx.diversity_flagged = self.diversity_handler.forward(ctx.routed_jus)

        # Stage 5: Calculate K€
        ctx.calculated_jus = self.ke_calculator.forward(ctx.diversity_flagged)

        # Stage 6: Save validation
        save_check = self.save_validator.forward(ctx.calculated_jus)
        ctx.can_save = save_check["can_save"]
        ctx.save_errors = save_check["errors"]
        ctx.save_warnings = save_check["warnings"]

        return ctx

    # ── Manual action handlers ──

    def set_tc_ke(self, ju: dict, total_ke: float,
                  overrides: Optional[dict[str, float]] = None) -> dict:
        return self.tc_handler.forward(ju, total_ke, overrides)

    def split_ju(self, ju: dict, splits: list[dict]) -> list[dict]:
        return self.split_handler.forward(ju, splits)

    def bulk_assign(self, rows: list[dict], societe: str) -> list[dict]:
        return self.bulk_assigner.forward(rows, societe)

    def validate_save(self, job_units: list[dict]) -> dict:
        return self.save_validator.forward(job_units)


def run_allocation(
    role: str,
    job_units: list[dict],
    rules: Optional[list[dict]] = None,
    lm: Optional[LMClient] = None,
) -> AllocationContext:
    pipeline = AllocationPipeline(lm, rules)
    return pipeline.forward(role, job_units)