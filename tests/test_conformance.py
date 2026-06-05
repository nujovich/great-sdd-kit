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


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — canonical json, version, normalize
# ═══════════════════════════════════════════════════════════

def test_canonical_json_is_byte_stable_and_key_order_independent():
    from sdd.base_conformance import canonical_json
    a = canonical_json({"b": 1, "a": [3, 2, 1]})
    b = canonical_json({"a": [3, 2, 1], "b": 1})
    assert a == b
    assert a.endswith("\n")
    assert a == '{\n  "a": [\n    3,\n    2,\n    1\n  ],\n  "b": 1\n}\n'


def test_read_version_prefers_pyproject(tmp_path):
    from sdd.base_conformance import read_version
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "9.8.7"\n')
    assert read_version(tmp_path) == "9.8.7"


def test_normalize_output_parses_json_suffixed_keys():
    from sdd.base_conformance import normalize_output
    out = normalize_output({"can_save": True, "errors_json": '["a","b"]', "name": "x"})
    assert out == {"can_save": True, "errors_json": ["a", "b"], "name": "x"}


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — Probe + generate_fixtures (tripwire)
# ═══════════════════════════════════════════════════════════

def test_generate_fixtures_shape_and_sorting():
    from sdd.base_conformance import Probe, generate_fixtures
    p = Probe(rule_ids=["R-2", "R-1"], name="echo",
              fn=lambda inp: {"echoed": inp["v"]},
              cases=[{"v": 2}, {"v": 1}])
    entries = generate_fixtures([p], sdd_version="1.0.0")
    assert all(set(e) == {"rule_ids", "input", "expected_output", "sdd_version"} for e in entries)
    assert entries[0]["rule_ids"] == ["R-1", "R-2"]          # rule_ids sorted
    assert [e["input"]["v"] for e in entries] == [1, 2]      # entries sorted by input
    assert entries[0]["expected_output"] == {"echoed": 1}
    assert entries[0]["sdd_version"] == "1.0.0"


def test_generate_fixtures_normalizes_json_keys():
    from sdd.base_conformance import Probe, generate_fixtures
    p = Probe(["R-1"], "j", lambda inp: {"items_json": '[1,2]'}, [{}])
    entries = generate_fixtures([p], "1.0.0")
    assert entries[0]["expected_output"] == {"items_json": [1, 2]}


def test_generate_fixtures_aborts_loudly_on_lm_path():
    from sdd.base_conformance import Probe, generate_fixtures, NonDeterministicError, TripwireLM

    def bad(inp):
        TripwireLM().complete("s", "p")   # simulates a module hitting the LM
        return {}

    with pytest.raises(NonDeterministicError):
        generate_fixtures([Probe(["R-X"], "bad", bad, [{}])], "1.0.0")


# ═══════════════════════════════════════════════════════════
# sdd/base_conformance.py — coverage, skew, runner
# ═══════════════════════════════════════════════════════════

def test_compute_coverage_threshold():
    from sdd.base_conformance import compute_coverage
    r = compute_coverage(all_rule_ids=["A", "B", "C", "D"],
                         covered_rule_ids=["A", "B", "C"], threshold=0.70)
    assert r["covered_count"] == 3 and r["total"] == 4
    assert abs(r["coverage"] - 0.75) < 1e-9
    assert r["passed"] is True and r["missing"] == ["D"]
    r2 = compute_coverage(["A", "B", "C", "D"], ["A"], 0.70)
    assert r2["passed"] is False


def test_compute_version_skew():
    from sdd.base_conformance import compute_version_skew
    assert compute_version_skew("1.2.0", "1.2.0")["skew"] is False
    assert compute_version_skew("1.1.0", "1.2.0")["skew"] is True


def test_run_conformance_exact_match_and_exercised_ids():
    from sdd.base_conformance import run_conformance
    fixtures = [
        {"rule_ids": ["R-1"], "input": {"v": 1}, "expected_output": {"r": 2}, "sdd_version": "1.0.0"},
        {"rule_ids": ["R-2"], "input": {"v": 5}, "expected_output": {"r": 6}, "sdd_version": "1.0.0"},
    ]
    rep = run_conformance(fixtures, consumer_fn=lambda inp: {"r": inp["v"] + 1})
    assert rep["passed"] is True and rep["failed_count"] == 0
    assert sorted(rep["exercised_rule_ids"]) == ["R-1", "R-2"]
    bad = run_conformance(fixtures, consumer_fn=lambda inp: {"r": 0})
    assert bad["passed"] is False and bad["failed_count"] == 2
    assert bad["failures"][0]["input"] == {"v": 1}


# ═══════════════════════════════════════════════════════════
# InductorSelector — deterministic, LM-free refactor
# ═══════════════════════════════════════════════════════════

def test_inductor_selector_is_deterministic_and_lm_free():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    sel = InductorSelector(TripwireLM())            # tripwire: must NOT call LM
    out1 = sel.forward(line_description="Build a complex REST API endpoint",
                       metier="Backend", available_inductors_json="[]")
    out2 = sel.forward(line_description="Build a complex REST API endpoint",
                       metier="Backend", available_inductors_json="[]")
    assert out1 == out2                              # deterministic
    sels = json.loads(out1["inductor_selections_json"])
    assert isinstance(sels, list) and len(sels) >= 1
    api = [s for s in sels if s["name"] == "API endpoints"]
    assert api and api[0]["selected_cran"] == "Complex"   # "complex" keyword -> Complex cran
    assert all("job_units" in s for s in sels)


def test_inductor_selector_empty_description_falls_back_to_all():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="", metier="Backend", available_inductors_json="[]")
    sels = json.loads(out["inductor_selections_json"])
    assert len(sels) == 3                            # all Backend inductors, canonical crans
    assert all(s["selected_cran"] for s in sels)


def test_inductor_selector_unknown_metier_returns_empty():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="x", metier="Nonexistent", available_inductors_json="[]")
    assert json.loads(out["inductor_selections_json"]) == []
