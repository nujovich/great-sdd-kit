"""
SDD Kit — Base Module.

Base class for business logic modules in an SDD pipeline.
Each module does ONE thing and does it well.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseModule:
    """
    Base class for all SDD modules.

    Each module implements a single business operation.
    Modules are composable: pipeline orchestration calls them in order.

    Usage:
        class MyValidator(BaseModule):
            def forward(self, data: dict) -> dict:
                # Pure Python business logic
                return {"valid": True, "errors": []}
    """

    def forward(self, **kwargs) -> dict:
        """Execute the module's business logic. Override in subclasses."""
        raise NotImplementedError

    def __call__(self, **kwargs) -> dict:
        return self.forward(**kwargs)


class BaseLMModule(BaseModule):
    """
    Base class for modules that may use an LLM.

    The LM client is swappable. Uses OpenAI-compatible API by default.

    Usage:
        class MyAnalyzer(BaseLMModule):
            def forward(self, text: str) -> dict:
                response = self.call_lm("Analyze this", text)
                return {"analysis": response}
    """

    def __init__(self, lm_client: Optional[Any] = None):
        super().__init__()
        self._lm = lm_client

    def set_lm(self, lm_client: Any):
        """Set or swap the LM client."""
        self._lm = lm_client

    def call_lm(self, system: str, prompt: str, **kwargs) -> str:
        """Call the LM. Override if using a different client."""
        if self._lm is None:
            logger.warning("No LM client configured. Returning empty response.")
            return ""

        if hasattr(self._lm, "complete"):
            return self._lm.complete(system, prompt, **kwargs)

        return str(self._lm)


class ModulePipeline:
    """
    Orchestrates multiple modules in sequence.

    Each module's output is passed as input to the next module.
    Modules can be pure Python or LM-based.

    Usage:
        pipeline = ModulePipeline([
            ("validate", MyValidator()),
            ("calculate", MyCalculator()),
            ("save", MySaveValidator()),
        ])
        result = pipeline.run(data)
    """

    def __init__(self, stages: list[tuple[str, BaseModule]]):
        self.stages = stages

    def run(self, initial_data: dict) -> dict:
        """Run all stages in order, passing results forward."""
        data = dict(initial_data)
        results = {"stages": {}}

        for name, module in self.stages:
            logger.info("Pipeline stage: %s", name)
            stage_result = module.forward(**data)
            results["stages"][name] = stage_result
            if isinstance(stage_result, dict):
                data.update(stage_result)

        results["final"] = data
        return results

    def run_until(self, initial_data: dict, stop_at: str) -> dict:
        """Run pipeline stages until a named stage (inclusive)."""
        data = dict(initial_data)
        results = {"stages": {}}

        for name, module in self.stages:
            stage_result = module.forward(**data)
            results["stages"][name] = stage_result
            if isinstance(stage_result, dict):
                data.update(stage_result)
            if name == stop_at:
                break

        results["final"] = data
        return results