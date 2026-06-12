"""
GREAT Estimation Review — Pipeline.

Read-only governance pipeline for WP5. Orchestrates:
  1. Permission check → 2. Grid rendering (with derived approval columns)
  → 3. HVT callback processing → 4. CSV export
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.estimation_review import (
    EstimationReviewPermissionChecker,
    ApprovalColumnDeriver,
    HVTCallbackProcessor,
    CSVExporter,
)
from great_sdd.specs.estimation_review_specs import (
    ESTIMATION_REVIEW_RULES,
    ALL_BUSINESS_RULES,
    ESTIMATION_REVIEW_GRID_COLUMNS,
    GRID_FILTERS,
)

logger = logging.getLogger(__name__)


@dataclass
class EstimationReviewContext:
    """Holds all state from the Estimation Review pipeline."""
    # Stage 1
    permission_allowed: bool = False
    permission_reason: str = ""

    # Stage 2
    grid_rows: list = field(default_factory=list)
    derived_columns: list = field(default_factory=list)

    # Stage 3
    callback_results: list = field(default_factory=list)

    # Stage 4
    csv_content: str = ""
    csv_row_count: int = 0

    # Errors
    errors: list = field(default_factory=list)


class EstimationReviewPipeline:
    """
    Full Estimation Review View pipeline.
    """

    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm
        self.permission_checker = EstimationReviewPermissionChecker(lm)
        self.column_deriver = ApprovalColumnDeriver(lm)
        self.callback_processor = HVTCallbackProcessor(lm)
        self.csv_exporter = CSVExporter(lm)

    def forward(
        self,
        role: str,
        grid_rows: Optional[list[dict]] = None,
    ) -> EstimationReviewContext:
        """Run the full Estimation Review pipeline."""
        ctx = EstimationReviewContext()

        if grid_rows is None:
            grid_rows = []

        # ── Stage 1: Permission Check (§2) ──
        logger.info("ER Stage 1: Checking %s permissions", role)
        perm = self.permission_checker.forward(role=role, action="view")
        ctx.permission_allowed = perm["allowed"]
        ctx.permission_reason = perm["reason"]

        if not ctx.permission_allowed:
            ctx.errors.append(f"Permission denied: {ctx.permission_reason}")
            return ctx

        # ── Stage 2: Render Grid with Derived Columns (§4, §5) ──
        logger.info("ER Stage 2: Processing %d grid rows", len(grid_rows))
        ctx.grid_rows = grid_rows
        ctx.derived_columns = [
            self.column_deriver.derive_row(row) for row in grid_rows
        ]

        return ctx

    def process_callback(self, project_line: str, metier: str,
                          approved: bool, comment: str = "") -> dict:
        """Process an HVT callback for CPO approval/rejection."""
        return self.callback_processor.forward(
            project_line=project_line,
            metier=metier,
            approved=approved,
            comment=comment,
        )

    def export_csv(self, rows: list[dict], mode: str = "all_filtered",
                   yearly_keys: Optional[list[str]] = None) -> dict:
        """Export rows to CSV."""
        return self.csv_exporter.forward(
            rows_json=json.dumps(rows), mode=mode,
            yearly_keys_json=json.dumps(yearly_keys) if yearly_keys else "[]",
        )


def run_estimation_review(
    role: str,
    grid_rows: Optional[list[dict]] = None,
    lm: Optional[LMClient] = None,
) -> EstimationReviewContext:
    """One-shot runner for the Estimation Review pipeline."""
    pipeline = EstimationReviewPipeline(lm)
    return pipeline.forward(role=role, grid_rows=grid_rows)