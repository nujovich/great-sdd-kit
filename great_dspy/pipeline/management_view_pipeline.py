"""
GREAT Management View — Pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.management_view import (
    ManagementAccessChecker,
    PieChartBuilder,
    TimelineBuilder,
    MetierFilter,
)

logger = logging.getLogger(__name__)


@dataclass
class ManagementViewContext:
    access_allowed: bool = False
    access_reason: str = ""
    pie_chart: dict = field(default_factory=dict)
    timeline: dict = field(default_factory=dict)
    total_pairs: int = 0
    metier: str = "All"
    errors: list = field(default_factory=list)


class ManagementViewPipeline:
    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm
        self.access_checker = ManagementAccessChecker(lm)
        self.pie_builder = PieChartBuilder(lm)
        self.timeline_builder = TimelineBuilder(lm)
        self.metier_filter = MetierFilter(lm)

    def forward(self, role: str, pairs: list[dict],
                timeline_data: Optional[list[dict]] = None,
                metier: str = "All") -> ManagementViewContext:
        ctx = ManagementViewContext(metier=metier)

        access = self.access_checker.forward(role)
        ctx.access_allowed = access["allowed"]
        ctx.access_reason = access["reason"]

        if not ctx.access_allowed:
            ctx.errors.append(ctx.access_reason)
            return ctx

        # Apply metier filter
        filtered = self.metier_filter.forward(pairs, metier)
        ctx.total_pairs = len(filtered)

        # Build pie chart
        status_counts = self.metier_filter.count_by_status(filtered)
        ctx.pie_chart = self.pie_builder.forward(status_counts, metier)

        # Build timeline (if data available)
        if timeline_data:
            # Apply metier filter to timeline data too
            filtered_timeline = []
            for dp in timeline_data:
                filtered_counts = {}
                for status, count in dp.get("status_counts", {}).items():
                    filtered_counts[status] = count
                filtered_timeline.append({"date": dp["date"], "status_counts": filtered_counts})

            ctx.timeline = self.timeline_builder.forward(filtered_timeline, metier)

        return ctx


def run_management_view(role: str, pairs: list[dict],
                         timeline_data: Optional[list[dict]] = None,
                         metier: str = "All",
                         lm: Optional[LMClient] = None) -> ManagementViewContext:
    pipeline = ManagementViewPipeline(lm)
    return pipeline.forward(role, pairs, timeline_data, metier)