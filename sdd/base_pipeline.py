"""SDD Kit — Base Pipeline.

A minimal, domain-agnostic orchestration base. The GREAT view-pipelines predate
this class and are NOT required to inherit from it; it exists as the documented
extension point for new domains (referenced in AGENTS.md / README.md).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PipelineStage:
    """One step. Subclasses set `name` and implement `run(ctx) -> dict`."""
    name: str = "stage"

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class BasePipeline:
    """Runs stages in order, merging each stage's dict output into the context."""

    def __init__(self, stages: list[PipelineStage]):
        self.stages = stages

    def run(self, initial: dict[str, Any]) -> dict[str, Any]:
        ctx = dict(initial)
        for stage in self.stages:
            logger.info("pipeline stage: %s", stage.name)
            result = stage.run(ctx)
            if isinstance(result, dict):
                ctx.update(result)
        return ctx
