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

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.allocation import (
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
        perm = self.permission_checker.forward(role=role)
        ctx.permission_allowed = perm["can_view"]
        ctx.permission_edit = perm["can_edit"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(ctx.permission_reason)
            return ctx

        # Stage 2: Filter to Approved lines only
        result = self.eligibility_filter.forward(job_units_json=json.dumps(job_units))
        ctx.eligible_jus = json.loads(result["approved_jus_json"])

        # Stage 3: Auto-assign societes via rules + H-PROJECT routing
        rules = self.rule_matcher.rules
        result = self.rule_matcher.forward(
            job_units_json=json.dumps(ctx.eligible_jus),
            rules_json=json.dumps(rules),
        )
        ctx.auto_assigned_jus = json.loads(result["assigned_jus_json"])

        result = self.hproject_router.forward(job_units_json=json.dumps(ctx.auto_assigned_jus))
        ctx.routed_jus = json.loads(result["routed_jus_json"])

        # Stage 4: Diversity dropdown
        result = self.diversity_handler.forward(job_units_json=json.dumps(ctx.routed_jus))
        ctx.diversity_flagged = json.loads(result["flagged_jus_json"])

        # Stage 5: Calculate K€
        result = self.ke_calculator.forward(job_units_json=json.dumps(ctx.diversity_flagged))
        ctx.calculated_jus = json.loads(result["calculated_jus_json"])

        # Stage 6: Save validation
        save_check = self.save_validator.forward(job_units_json=json.dumps(ctx.calculated_jus))
        ctx.can_save = save_check["can_save"]
        ctx.save_errors = json.loads(save_check["errors_json"])
        ctx.save_warnings = json.loads(save_check["warnings_json"])

        return ctx

    # -- Manual action handlers --

    def set_tc_ke(self, ju: dict, total_ke: float,
                  overrides: Optional[dict[str, float]] = None) -> dict:
        return self.tc_handler.forward(
            job_unit_json=json.dumps(ju),
            total_ke=total_ke,
            overrides_json=json.dumps(overrides) if overrides else "{}",
        )

    def split_ju(self, ju: dict, splits: list[dict]) -> list[dict]:
        result = self.split_handler.forward(
            ju_json=json.dumps(ju),
            splits_json=json.dumps(splits),
        )
        if result.get("error"):
            return [{"error": result["error"]}]
        return json.loads(result["child_jus_json"])

    def bulk_assign(self, rows: list[dict], societe: str) -> list[dict]:
        result = self.bulk_assigner.forward(rows_json=json.dumps(rows), societe=societe)
        return json.loads(result["updated_rows_json"])

    def validate_save(self, job_units: list[dict]) -> dict:
        result = self.save_validator.forward(job_units_json=json.dumps(job_units))
        return {
            "can_save": result["can_save"],
            "errors": json.loads(result["errors_json"]),
            "warnings": json.loads(result["warnings_json"]),
        }


def run_allocation(
    role: str,
    job_units: list[dict],
    rules: Optional[list[dict]] = None,
    lm: Optional[LMClient] = None,
) -> AllocationContext:
    pipeline = AllocationPipeline(lm, rules)
    return pipeline.forward(role, job_units)
