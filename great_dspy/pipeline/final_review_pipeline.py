"""
GREAT Final Review — Pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.final_review import (
    FinalReviewPermissionChecker,
    FinalReviewEligibilityFilter,
    AggregationEngine,
    CSVGlobalExporter,
    Stage3Sender,
)

logger = logging.getLogger(__name__)


@dataclass
class FinalReviewContext:
    permission_allowed: bool = False
    permission_reason: str = ""
    eligible_jus: list = field(default_factory=list)
    aggregations: dict = field(default_factory=dict)
    can_send_stage3: bool = False
    errors: list = field(default_factory=list)


class FinalReviewPipeline:
    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm
        self.permission_checker = FinalReviewPermissionChecker(lm)
        self.eligibility_filter = FinalReviewEligibilityFilter(lm)
        self.aggregation_engine = AggregationEngine(lm)
        self.csv_exporter = CSVGlobalExporter(lm)
        self.stage3_sender = Stage3Sender(lm)

    def forward(self, role: str, job_units: list[dict]) -> FinalReviewContext:
        ctx = FinalReviewContext()

        perm = self.permission_checker.forward(role, "view")
        ctx.permission_allowed = perm["allowed"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(ctx.permission_reason)
            return ctx

        ctx.can_send_stage3 = self.permission_checker.forward(role, "send_stage3")["allowed"]
        ctx.eligible_jus = self.eligibility_filter.forward(job_units)
        ctx.aggregations = self.aggregation_engine.forward(ctx.eligible_jus)

        return ctx

    def export_csv(self, job_units: list[dict], columns: Optional[list[str]] = None) -> dict:
        return self.csv_exporter.forward(job_units, columns)

    def send_stage3(self, job_units: list[dict], confirmed: bool = False) -> dict:
        """Send consolidated data to HVT Stage 3."""
        return self.stage3_sender.forward(job_units, confirmed)


def run_final_review(role: str, job_units: list[dict],
                     lm: Optional[LMClient] = None) -> FinalReviewContext:
    pipeline = FinalReviewPipeline(lm)
    return pipeline.forward(role, job_units)