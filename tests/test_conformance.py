"""Tests for the conformance layer (4th layer).

Covers the domain-agnostic engine (sdd/base_conformance.py, sdd/base_pipeline.py)
and the GREAT-specific wiring (great_sdd/conformance/*): rule inventory, exclusions,
fixture generation, coverage gate, and the consumer runner.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ═══════════════════════════════════════════════════════════
# sdd/base_pipeline.py
# ═══════════════════════════════════════════════════════════

def test_base_pipeline_runs_stages_in_order():
    from sdd.base_pipeline import BasePipeline, PipelineStage
    calls = []

    class A(PipelineStage):
        name = "a"

        def run(self, ctx):
            calls.append("a")
            return {"x": 1}

    class B(PipelineStage):
        name = "b"

        def run(self, ctx):
            calls.append("b")
            return {"y": ctx["x"] + 1}

    out = BasePipeline([A(), B()]).run({})
    assert calls == ["a", "b"]
    assert out["x"] == 1 and out["y"] == 2
