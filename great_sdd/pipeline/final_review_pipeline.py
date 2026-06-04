"""
GREAT Final Review — Pipeline.

Stages:
  1. Permission check
  2. Filter to Approved lines
  3. Aggregation (by cost_type, society, metier, PL total)
  4. CSV export
  5. Stage 3 send (non-blocking, re-sendable, all lines)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.final_review import (
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

        perm = self.permission_checker.forward(role=role, action="view")
        ctx.permission_allowed = perm["allowed"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(ctx.permission_reason)
            return ctx

        ctx.can_send_stage3 = self.permission_checker.forward(role=role, action="send_stage3")["allowed"]

        result = self.eligibility_filter.forward(job_units_json=json.dumps(job_units))
        ctx.eligible_jus = json.loads(result["approved_jus_json"])

        result = self.aggregation_engine.forward(job_units_json=json.dumps(ctx.eligible_jus))
        ctx.aggregations = json.loads(result["aggregations_json"])

        return ctx

    def export_csv(self, job_units: list[dict], columns: Optional[list[str]] = None) -> dict:
        return self.csv_exporter.forward(
            job_units_json=json.dumps(job_units),
            columns_json=json.dumps(columns) if columns else "[]",
        )

    def send_stage3(self, job_units: list[dict], confirmed: bool = False) -> dict:
        return self.stage3_sender.forward(
            job_units_json=json.dumps(job_units),
            confirmed=confirmed,
        )


def run_final_review(role: str, job_units: list[dict],
                     lm: Optional[LMClient] = None) -> FinalReviewContext:
    pipeline = FinalReviewPipeline(lm)
    return pipeline.forward(role, job_units)
