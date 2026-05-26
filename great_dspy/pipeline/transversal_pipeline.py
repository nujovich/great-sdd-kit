"""
GREAT Transversal Features — Pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from great_dspy.modules.base import LMClient
from great_dspy.modules.transversal import (
    CycleManager,
    WorkloadStandardManager,
    TableStateManager,
    EmailAlertService,
)

logger = logging.getLogger(__name__)


@dataclass
class TransversalContext:
    active_cycle: Optional[dict] = None
    active_workload_version: Optional[dict] = None
    version_count: int = 0
    cycle_count: int = 0
    email_log_count: int = 0
    errors: list = field(default_factory=list)


class TransversalPipeline:
    def __init__(self, lm: Optional[LMClient] = None):
        self.lm = lm
        self.cycle_manager = CycleManager(lm)
        self.workload_manager = WorkloadStandardManager(lm)
        self.table_manager = TableStateManager(lm)
        self.email_service = EmailAlertService(lm)


def run_transversal(
    cycles: Optional[list] = None,
    lm: Optional[LMClient] = None,
) -> TransversalContext:
    pipeline = TransversalPipeline(lm)
    ctx = TransversalContext()

    if cycles:
        pipeline.cycle_manager.set_cycles(cycles)

    active = pipeline.cycle_manager.get_active_cycle()
    if active:
        ctx.active_cycle = {"name": active.name, "start_date": active.start_date}

    active_wl = pipeline.workload_manager.get_active_version()
    if active_wl:
        ctx.active_workload_version = {
            "version_id": active_wl.version_id,
            "filename": active_wl.filename,
        }

    ctx.cycle_count = len(pipeline.cycle_manager.list_cycles())
    ctx.version_count = len(pipeline.workload_manager.list_versions())
    ctx.email_log_count = len(pipeline.email_service.get_log())

    return ctx