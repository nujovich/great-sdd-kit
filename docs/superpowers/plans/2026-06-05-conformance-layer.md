# Conformance Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fourth layer — *conformance* — that turns the SDD into a deterministic oracle, emits language-neutral golden fixtures, and lets any consumer (Python backend or TS frontend) verify it obeys the GREAT business rules in CI.

**Architecture:** A domain-agnostic engine in `sdd/base_conformance.py` (probes, tripwire-LM determinism guard, canonical JSON, coverage/skew math, runner). GREAT-specific wiring in `great_sdd/conformance/` (probe definitions per view → fixtures, rule inventory, coverage CLI, runner CLI, cross-language README). Fixtures are committed JSON and ARE the contract; the live oracle is only used to regenerate them. Determinism is *enforced*: fixtures are generated with a Tripwire LM injected, so any rule whose code path calls the LM aborts generation loudly. `InductorSelector` is refactored from LM-driven to a rule-based deterministic algorithm; genuinely LM-only capabilities go into a documented `NON_DETERMINISTIC_RULES` exclusion list.

**Tech Stack:** Python 3.11+ stdlib only (`json`, `dataclasses`, `pathlib`, `re`, `importlib`, `argparse`), `pytest` for tests, GitHub Actions for CI. No new runtime dependencies.

---

## Design Decisions (read before coding)

**D1 — The deterministic surface.** The oracle covers pure functions and deterministic module decisions only. Three mechanisms keep it honest:
- **Tripwire LM.** During fixture generation every module is constructed with `lm=TripwireLM()`, whose `.complete()` raises `NonDeterministicError`. If any covered code path calls the LM, generation aborts naming the offending probe/rule. This is the "fail loudly" guarantee.
- **Probe.** A `Probe` binds `rule_ids` → a deterministic `fn(input: dict) -> dict` + representative `cases`. `fn` calls into GREAT pure functions / deterministic modules and returns JSON-neutral output.
- **JSON normalization.** Module outputs carry `*_json` string fields. Probes (and the runner) normalize: any key ending in `_json` whose value is a JSON string is parsed into a real JSON value, so fixtures are neutral structures — not "Python str of JSON". Shared helper `normalize_output()` used by both generator and runner.

**D2 — Mixed-determinism modules.** `SelectionValidator` calls the LM only to phrase the *incompatibility_reason*; the `is_compatible` decision is pure (`are_lines_compatible`). Its probe targets the pure function `are_lines_compatible(lines) -> {"is_compatible": bool}` directly — the explanation text is never captured. So BR-06/BR-07 are covered; only the prose is excluded.

**D3 — Quarantine, two honest buckets** (`great_sdd/conformance/exclusions.py`, surfaced in every coverage report — never silently dropped):
- `NON_DETERMINISTIC_RULES: dict[str,str]` — capability → reason. LM-only outputs with no deterministic contract: `GENERATE_PRE_SAVE_SUMMARY` (summary prose), `SELECT_INDUCTOR_CRAN:semantic-ranking` (free-text best-fit ranking from arbitrary NL — the refactor covers keyword/substring matching + documented fallback, NOT semantic ranking), `VALIDATE_LINE_SELECTION:explanation` (prose only; decision is covered).
- `NO_FUNCTION_SURFACE_RULES: dict[str,str]` — business rule → reason. Deterministic but policy/UI-only, no pure-function to execute (e.g. `BR-01` no-deletion, `BR-09` occurrence-lock-default, `BR-10` assignment-read-only, `BR-14` comment scope, `BR-18`/`BR-19` prototype). These are excluded from the denominator with a written reason; the exact membership is finalized in Task 9 by inspecting each spec.

**D4 — Canonical number = 92.** `rule_inventory.business_rule_ids()` derives it programmatically (IDs matching `r"BR-\d+$"`), deduped across specs. 9 pending markers (`ALLOC-01`, `ERev-01..03`, `FINAL-01`, `MGMT-01`, `TRANS-01..03`) are NOT business rules. Docs are updated to "92".

**D5 — `sdd_version` source of truth = `pyproject.toml`**, with `package.json` fallback. A test asserts `__init__.__version__ == pyproject version == package.json version` so the field is never ambiguous. `bump_version.py` is extended to keep all three in sync.

**D6 — InductorSelector deterministic algorithm** (replaces the LM call entirely):
1. Resolve available inductors: parse `available_inductors_json`; if empty/invalid → `WORKLOAD_STANDARDS.get(metier, [])`. Support both `Inductor` dataclass and plain-dict shapes via small accessors (so consumers passing JSON work too).
2. If none → return `{"inductor_selections_json": "[]"}` (downstream BR-11 path).
3. **Selection rule:** lowercase the description into a token set. An inductor is *selected* if any keyword derived from it — tokens of its `name` + each JU `short_name` + tokens of each JU `description` — appears as a case-insensitive substring of the description. If the set is empty (generic/empty description, no hit) → **documented fallback: select all available inductors** (canonical default; guarantees non-empty when a standard exists). Declared order preserved → deterministic.
4. **Cran rule:** pick the first cran (declared order) whose `name.lower()` is a substring of the description; else `crans[0]` (canonical lowest); if no crans → `selected_cran=None` (BR-12: skipped downstream).
5. **Job units:** emit each JU as `{short_name, description, variable, fixed, occurrence, unit_type}` using the JU's own coefficients; `occurrence` default `1.0`. (Coefficients already live per-JU; cran is recorded at inductor level for traceability — we do not remap coefficients by cran.)
6. Output per inductor `{"name", "selected_cran", "job_units":[...]}`; return `{"inductor_selections_json": json.dumps(selections)}`. No `call_lm` anywhere.

**D7 — Keep `sdd/` domain-agnostic.** No `great_sdd` imports in `sdd/base_conformance.py`. All GREAT knowledge lives in `great_sdd/conformance/`.

---

## File Structure

**Create:**
- `sdd/base_conformance.py` — engine: `NonDeterministicError`, `TripwireLM`, `Probe`, `canonical_json`, `normalize_output`, `read_version`, `generate_fixtures`, `write_fixture_file`, `compute_coverage`, `compute_version_skew`, `run_conformance`.
- `great_sdd/conformance/__init__.py`
- `great_sdd/conformance/exclusions.py` — `NON_DETERMINISTIC_RULES`, `NO_FUNCTION_SURFACE_RULES`.
- `great_sdd/conformance/rule_inventory.py` — programmatic rule census (the canonical 92).
- `great_sdd/conformance/generate.py` — per-view probe builders + `main()` (`--check` for CI drift).
- `great_sdd/conformance/coverage.py` — coverage + skew CLI (`--report` | `--from-fixtures`, `--threshold`).
- `great_sdd/conformance/runner.py` — load fixtures → run `consumer_fn` → exact-match → emit exercised rule_ids + report; runnable example consumer.
- `great_sdd/conformance/README.md` — cross-language (TS) contract.
- `great_sdd/conformance/fixtures/*.json` — committed goldens (one per view + `_inventory.json`).
- `tests/test_conformance.py` — tests for every engine + GREAT conformance behavior.
- `.github/workflows/conformance.yml` — CI gate.

**Modify:**
- `great_sdd/modules/pre_estimation.py:177-239` — `InductorSelector.forward_impl` → deterministic.
- `scripts/bump_version.py` — also bump `package.json` + stage `CHANGELOG.md`.
- `.gitignore` — add `node_modules/`.
- `README.md`, `AGENTS.md`, `SDD-OVERVIEW.md` — reconcile rule count (→92), test count (derived), remove/fix `base_pipeline.py` + `test_pre_estimation.py` references.
- `CHANGELOG.md` — new MINOR entry.
- `great_sdd/__init__.py`, `pyproject.toml`, `package.json` — version bump + descriptions.

**Decide (Task 2):** `sdd/base_pipeline.py` — the plan CREATES it (a thin documented base the 6 pipelines *could* adopt), so the doc reference becomes true without forcing a risky refactor. (Alternative: delete the doc references. Chosen: create, because the doc promises it and it adds value as an extension point — existing pipelines are NOT migrated, honoring "no toques la lógica existente".)

---

## Task 0: Branch + baseline

**Files:** none (git only)

- [ ] **Step 1: Create a feature branch**

```bash
git checkout -b feat/conformance-layer
```

- [ ] **Step 2: Ensure pytest is available and capture baseline**

```bash
python3 -m pytest tests/ -q 2>&1 | tail -5 || echo "PYTEST MISSING — install pytest in a 3.11+ env before continuing"
```
Expected: a green baseline (record the number). If pytest/Python 3.11 is unavailable locally, all `pytest` steps below are validated in CI (Task 13) instead; do not claim local green without output.

---

## Task 1: Untrack `node_modules/` (isolated, quick win)

**Files:**
- Modify: `.gitignore`
- Remove from VCS: `node_modules/` (279 tracked files)

- [ ] **Step 1: Add ignore entry**

Append to `.gitignore`:
```
node_modules/
```

- [ ] **Step 2: Remove from index (keep on disk)**

```bash
git rm -r --cached node_modules >/dev/null
git status --short | grep -c "^D  node_modules" # expect 279
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: untrack node_modules and gitignore it"
```

---

## Task 2: `sdd/base_pipeline.py` (make the doc true)

**Files:**
- Create: `sdd/base_pipeline.py`
- Test: `tests/test_conformance.py` (shared file; add a small section)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_conformance.py (top of file)
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

def test_base_pipeline_runs_stages_in_order():
    from sdd.base_pipeline import BasePipeline, PipelineStage
    calls = []
    class A(PipelineStage):
        name = "a"
        def run(self, ctx): calls.append("a"); return {"x": 1}
    class B(PipelineStage):
        name = "b"
        def run(self, ctx): calls.append("b"); return {"y": ctx["x"] + 1}
    out = BasePipeline([A(), B()]).run({})
    assert calls == ["a", "b"]
    assert out["x"] == 1 and out["y"] == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_conformance.py::test_base_pipeline_runs_stages_in_order -v`
Expected: FAIL — `ModuleNotFoundError: sdd.base_pipeline`.

- [ ] **Step 3: Implement `sdd/base_pipeline.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_conformance.py::test_base_pipeline_runs_stages_in_order -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdd/base_pipeline.py tests/test_conformance.py
git commit -m "feat: add sdd/base_pipeline base class (documented extension point)"
```

---

## Task 3: `sdd/base_conformance.py` — canonical JSON, version, normalization

**Files:**
- Create: `sdd/base_conformance.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "canonical or read_version or normalize" -v`
Expected: FAIL — `ModuleNotFoundError: sdd.base_conformance`.

- [ ] **Step 3: Implement the module (part 1)**

```python
"""SDD Kit — Conformance Engine (domain-agnostic).

Turns a deterministic spec surface into language-neutral golden fixtures and
verifies consumers against them. NO domain imports. NO network. NO LLM.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


class NonDeterministicError(Exception):
    """Raised when fixture generation hits a non-deterministic path (e.g. the LM)."""


class TripwireLM:
    """Stand-in LM client. Any completion attempt aborts generation loudly."""

    def complete(self, system: str, prompt: str, **kwargs) -> str:
        raise NonDeterministicError(
            "LM call attempted during deterministic fixture generation. "
            "The covered rule depends on a non-deterministic module path. "
            "Refactor it to be deterministic or add it to NON_DETERMINISTIC_RULES."
        )


def canonical_json(obj: Any) -> str:
    """Deterministic, byte-stable JSON: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def normalize_output(result: dict) -> dict:
    """Parse any `*_json` string value into a real JSON value (language-neutral)."""
    out = {}
    for k, v in result.items():
        if k.endswith("_json") and isinstance(v, str):
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[k] = v
        else:
            out[k] = v
    return out


def read_version(repo_root: Path) -> str:
    """Read project version: pyproject.toml first, then package.json. Stdlib-only."""
    repo_root = Path(repo_root)
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', pyproject.read_text(), re.M)
        if m:
            return m.group(1)
    pkg = repo_root / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text())
        if "version" in data:
            return str(data["version"])
    raise RuntimeError(f"No version found under {repo_root}")
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "canonical or read_version or normalize" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdd/base_conformance.py tests/test_conformance.py
git commit -m "feat: conformance engine — canonical json, version reader, normalization"
```

---

## Task 4: `sdd/base_conformance.py` — Probe + generate_fixtures (tripwire enforced)

**Files:**
- Modify: `sdd/base_conformance.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "generate_fixtures" -v`
Expected: FAIL — `ImportError: cannot import name 'Probe'`.

- [ ] **Step 3: Implement (append to `sdd/base_conformance.py`)**

```python
@dataclass
class Probe:
    """Binds rule_ids to a deterministic fn over representative input cases."""
    rule_ids: list[str]
    name: str
    fn: Callable[[dict], dict]
    cases: list[dict] = field(default_factory=list)


def generate_fixtures(probes: list[Probe], sdd_version: str) -> list[dict]:
    """Run every probe case and emit sorted, normalized fixture entries.

    Raises NonDeterministicError (via TripwireLM inside fn) if a covered path
    is non-deterministic — callers MUST construct domain modules with TripwireLM.
    """
    entries: list[dict] = []
    for probe in probes:
        rule_ids = sorted(probe.rule_ids)
        for case in probe.cases:
            output = normalize_output(probe.fn(case))
            entries.append({
                "rule_ids": rule_ids,
                "input": case,
                "expected_output": output,
                "sdd_version": sdd_version,
            })
    entries.sort(key=lambda e: (e["rule_ids"], canonical_json(e["input"])))
    return entries


def write_fixture_file(path: Path, entries: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(entries))
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "generate_fixtures" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdd/base_conformance.py tests/test_conformance.py
git commit -m "feat: conformance engine — Probe + deterministic fixture generation"
```

---

## Task 5: `sdd/base_conformance.py` — coverage, version skew, runner

**Files:**
- Modify: `sdd/base_conformance.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "coverage or skew or run_conformance" -v`
Expected: FAIL — names not defined.

- [ ] **Step 3: Implement (append)**

```python
def compute_coverage(all_rule_ids: list[str], covered_rule_ids: list[str],
                     threshold: float) -> dict:
    all_set = set(all_rule_ids)
    covered = all_set & set(covered_rule_ids)
    total = len(all_set)
    coverage = (len(covered) / total) if total else 1.0
    return {
        "total": total,
        "covered_count": len(covered),
        "coverage": coverage,
        "threshold": threshold,
        "passed": coverage >= threshold,
        "missing": sorted(all_set - covered),
        "covered": sorted(covered),
    }


def compute_version_skew(consumer_version: str, oracle_version: str) -> dict:
    return {
        "consumer_version": consumer_version,
        "oracle_version": oracle_version,
        "skew": consumer_version != oracle_version,
    }


def run_conformance(fixtures: list[dict], consumer_fn: Callable[[dict], dict]) -> dict:
    """Run consumer_fn against each fixture; exact-match expected_output."""
    failures = []
    exercised: set[str] = set()
    for fx in fixtures:
        exercised.update(fx["rule_ids"])
        actual = normalize_output(consumer_fn(fx["input"]))
        if actual != fx["expected_output"]:
            failures.append({
                "rule_ids": fx["rule_ids"],
                "input": fx["input"],
                "expected": fx["expected_output"],
                "actual": actual,
            })
    return {
        "total": len(fixtures),
        "failed_count": len(failures),
        "passed": not failures,
        "failures": failures,
        "exercised_rule_ids": sorted(exercised),
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "coverage or skew or run_conformance" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sdd/base_conformance.py tests/test_conformance.py
git commit -m "feat: conformance engine — coverage, version skew, consumer runner"
```

---

## Task 6: Refactor `InductorSelector` to deterministic (per D6)

**Files:**
- Modify: `great_sdd/modules/pre_estimation.py:177-239`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
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
    assert api and api[0]["selected_cran"] == "Complex"   # "complex" keyword → Complex cran
    assert all("job_units" in s for s in sels)

def test_inductor_selector_empty_description_falls_back_to_all():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="", metier="Backend", available_inductors_json="[]")
    sels = json.loads(out["inductor_selections_json"])
    assert len(sels) == 3                            # all Backend inductors, canonical crans
    assert all(s["selected_cran"] == s["job_units"][0]["cran"] or s["selected_cran"]
               for s in sels)

def test_inductor_selector_unknown_metier_returns_empty():
    from sdd.base_conformance import TripwireLM
    from great_sdd.modules.pre_estimation import InductorSelector
    out = InductorSelector(TripwireLM()).forward(
        line_description="x", metier="Nonexistent", available_inductors_json="[]")
    assert json.loads(out["inductor_selections_json"]) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "inductor_selector" -v`
Expected: FAIL — current impl calls `self.call_lm` → `TripwireLM` raises `NonDeterministicError`.

- [ ] **Step 3: Replace `InductorSelector.forward_impl`**

Replace the body of `forward_impl` (lines ~188-239) with the deterministic algorithm. Add module-level helpers above the class:

```python
def _ind_attr(ind, attr, default=None):
    """Accessor that works for both Inductor dataclass and plain dict."""
    return getattr(ind, attr, None) if not isinstance(ind, dict) else ind.get(attr, default)

def _ju_fields(ju):
    g = (lambda a, d=None: ju.get(a, d)) if isinstance(ju, dict) else (lambda a, d=None: getattr(ju, a, d))
    return {
        "short_name": g("short_name", ""),
        "description": g("description", ""),
        "variable": g("variable", 0.0),
        "fixed": g("fixed", 0.0),
        "occurrence": 1.0,
        "unit_type": g("unit_type", "man_day"),
        "cran": g("cran", ""),
    }

def _inductor_keywords(ind):
    kws = set()
    for tok in str(_ind_attr(ind, "name", "")).lower().split():
        kws.add(tok)
    for ju in _ind_attr(ind, "job_units", []) or []:
        f = _ju_fields(ju)
        kws.add(str(f["short_name"]).lower())
        for tok in str(f["description"]).lower().split():
            kws.add(tok)
    return {k for k in kws if k}
```

```python
    def forward_impl(self, line_description: str, metier: str,
                     available_inductors_json: str = "[]") -> dict:
        # 1. Resolve available inductors (consumer JSON or workload standard).
        try:
            parsed = json.loads(available_inductors_json) if isinstance(
                available_inductors_json, str) else available_inductors_json
        except (json.JSONDecodeError, TypeError):
            parsed = []
        available = parsed if parsed else WORKLOAD_STANDARDS.get(metier, [])
        if not available:
            return {"inductor_selections_json": "[]"}

        desc = (line_description or "").lower()

        # 2. Deterministic selection: keyword/substring match, else full-standard fallback.
        matched = [ind for ind in available
                   if any(kw in desc for kw in _inductor_keywords(ind))]
        selected = matched if matched else list(available)

        # 3. Per inductor: deterministic cran + job units.
        selections = []
        for ind in selected:
            crans = _ind_attr(ind, "crans", []) or []
            cran_names = [_ind_attr(c, "name", "") if not isinstance(c, dict) else c.get("name", "")
                          for c in crans]
            chosen = next((n for n in cran_names if n and n.lower() in desc), None)
            if chosen is None and cran_names:
                chosen = cran_names[0]
            selections.append({
                "name": _ind_attr(ind, "name", ""),
                "selected_cran": chosen,
                "job_units": [_ju_fields(ju) for ju in (_ind_attr(ind, "job_units", []) or [])],
            })
        return {"inductor_selections_json": json.dumps(selections)}
```

Also update the class docstring: remove "LM: matches…"; state it is a deterministic rule-based selector. Remove the now-unused prompt-building code.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "inductor_selector" -v`
Expected: PASS.

- [ ] **Step 5: Verify existing pre-estimation tests still pass**

Run: `python -m pytest tests/test_pipeline.py -q`
Expected: PASS (no regression; pipeline Stage 3 now uses the deterministic selector). If any test asserted LM-driven inductor behavior, fix the test to assert the deterministic contract (note it in the commit).

- [ ] **Step 6: Commit**

```bash
git add great_sdd/modules/pre_estimation.py tests/test_conformance.py
git commit -m "refactor: deterministic rule-based InductorSelector (no LM)"
```

---

## Task 7: `great_sdd/conformance/rule_inventory.py` (canonical 92)

**Files:**
- Create: `great_sdd/conformance/__init__.py` (empty)
- Create: `great_sdd/conformance/rule_inventory.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
def test_rule_inventory_canonical_counts():
    from great_sdd.conformance.rule_inventory import business_rule_ids, pending_marker_ids, rule_count
    brs = business_rule_ids()
    assert rule_count() == 92
    assert len(brs) == 92
    assert "BR-01" in brs and "ALLOC-BR-17" in brs and "EMAIL-BR-04" in brs
    assert set(pending_marker_ids()) == {
        "ALLOC-01", "ERev-01", "ERev-02", "ERev-03",
        "FINAL-01", "MGMT-01", "TRANS-01", "TRANS-02", "TRANS-03"}
    assert brs == sorted(set(brs))    # deduped + sorted
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_conformance.py -k "rule_inventory" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `rule_inventory.py`**

```python
"""Programmatic census of GREAT business rules — the single source of truth.

Scans every great_sdd/specs/*.py module for module-level lists of dicts carrying
an "id" key, deduping across files (e.g. estimation_review re-exports BR-* into
ALL_BUSINESS_RULES). Business rules match r"BR-\\d+$"; everything else
(ALLOC-01, ERev-01, ...) is a pending/open-question marker, not a rule.
"""
from __future__ import annotations

import importlib
import pkgutil
import re

import great_sdd.specs as _specs_pkg

_BR_RE = re.compile(r"BR-\d+$")


def _all_rule_dicts() -> dict[str, dict]:
    """Map rule_id -> rule dict, deduped across all spec modules."""
    found: dict[str, dict] = {}
    for mod_info in pkgutil.iter_modules(_specs_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"great_sdd.specs.{mod_info.name}")
        for value in vars(mod).values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        found.setdefault(item["id"], item)
    return found


def all_rule_ids() -> list[str]:
    return sorted(_all_rule_dicts())


def business_rule_ids() -> list[str]:
    return sorted(rid for rid in _all_rule_dicts() if _BR_RE.search(rid))


def pending_marker_ids() -> list[str]:
    return sorted(rid for rid in _all_rule_dicts() if not _BR_RE.search(rid))


def rule_count() -> int:
    return len(business_rule_ids())


def rule_text(rule_id: str) -> str:
    return _all_rule_dicts().get(rule_id, {}).get("rule", "")
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_conformance.py -k "rule_inventory" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/__init__.py great_sdd/conformance/rule_inventory.py tests/test_conformance.py
git commit -m "feat: programmatic rule inventory (canonical 92 business rules)"
```

---

## Task 8: `exclusions.py` + consistency test against inventory

**Files:**
- Create: `great_sdd/conformance/exclusions.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
def test_exclusions_reference_real_or_capability_ids():
    from great_sdd.conformance.exclusions import (
        NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)
    from great_sdd.conformance.rule_inventory import business_rule_ids
    brs = set(business_rule_ids())
    # Every NO_FUNCTION_SURFACE entry must be a real business rule.
    assert set(NO_FUNCTION_SURFACE_RULES).issubset(brs)
    # Every value is a non-empty reason string.
    for d in (NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES):
        assert all(isinstance(v, str) and v for v in d.values())
    # The two buckets do not overlap.
    assert not (set(NON_DETERMINISTIC_RULES) & set(NO_FUNCTION_SURFACE_RULES))
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_conformance.py -k "exclusions" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `exclusions.py`** (membership finalized in Task 9; start with the certain entries)

```python
"""Documented conformance exclusions — surfaced in every coverage report.

NEVER silently drop a rule. If a rule is excluded, it is HERE with a reason.
"""

# Capabilities whose ONLY output is LM-generated (no deterministic contract).
# Keyed by capability tag, not always a business-rule id.
NON_DETERMINISTIC_RULES: dict[str, str] = {
    "GENERATE_PRE_SAVE_SUMMARY": "Summary prose is produced by the LM; the numeric "
        "data it summarizes is covered by EstimationCalculator/MonthDistributor.",
    "VALIDATE_LINE_SELECTION:explanation": "incompatibility_reason prose is LM-only; "
        "the is_compatible DECISION is covered via are_lines_compatible (BR-06/BR-07).",
    "SELECT_INDUCTOR_CRAN:semantic-ranking": "Free-text best-fit ranking from arbitrary "
        "natural language is LM-only. The deterministic refactor covers keyword/substring "
        "selection + documented full-standard fallback, not semantic ranking.",
}

# Deterministic business rules with no pure-function surface to execute
# (policy / UI / data-lifecycle). Each must be a real business-rule id.
# Finalized in Task 9 by inspecting each spec; reasons are mandatory.
NO_FUNCTION_SURFACE_RULES: dict[str, str] = {
    "BR-01": "No-deletion policy — enforced at persistence/UI layer; no callable.",
    "BR-09": "occurrence_locked defaults false — data default, not a function.",
    "BR-10": "Assignment read-only — sourced from HVT; UI/persistence policy.",
    "BR-14": "Comment scoped to (line, metier) — storage shape, no callable.",
    "BR-18": "Prototype data stored separately — persistence policy.",
    "BR-19": "Prototype categories pending definition (PRE-01).",
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_conformance.py -k "exclusions" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/exclusions.py tests/test_conformance.py
git commit -m "feat: documented conformance exclusion buckets"
```

---

## Task 9: `generate.py` — probe builders per view + `main()`

This is the largest task. Build one probe-builder per view, each returning `list[Probe]`. Every probe constructs its GREAT module with `TripwireLM()` (or calls a pure function directly). Work view-by-view, committing after each so coverage grows incrementally and visibly.

**Files:**
- Create: `great_sdd/conformance/generate.py`
- Create (output): `great_sdd/conformance/fixtures/*.json`
- Test: `tests/test_conformance.py`

**Probe authoring rules:**
- One `Probe` per business rule (or a small group) with `rule_ids=[...]`.
- `fn(inp)` calls a pure spec function or a deterministic module's `forward()` with a `TripwireLM`, returns its dict.
- `cases` = representative inputs (include the boundary that the rule is about, e.g. for BR-08 a line with and without `sp_date`).
- For rules with no callable → do NOT write a probe; they live in `exclusions.NO_FUNCTION_SURFACE_RULES`.
- For LM-only capabilities → do NOT write a probe; they live in `exclusions.NON_DETERMINISTIC_RULES`.

- [ ] **Step 1: Write failing tests**

```python
def test_build_probes_cover_expected_views():
    from great_sdd.conformance.generate import build_probes
    views = build_probes()
    assert set(views) == {"pre_estimation", "estimation_review", "allocation",
                          "final_review", "management_view", "transversal"}
    assert all(len(v) >= 1 for v in views.values())

def test_all_probes_run_without_lm_and_are_deterministic():
    from great_sdd.conformance.generate import build_probes
    from sdd.base_conformance import generate_fixtures
    for view, probes in build_probes().items():
        e1 = generate_fixtures(probes, "1.0.0")     # raises if any path hits the LM
        e2 = generate_fixtures(probes, "1.0.0")
        assert e1 == e2, f"{view} not deterministic"

def test_covered_rule_ids_are_real_business_rules():
    from great_sdd.conformance.generate import covered_rule_ids
    from great_sdd.conformance.rule_inventory import business_rule_ids
    assert set(covered_rule_ids()).issubset(set(business_rule_ids()))

def test_no_rule_is_both_covered_and_excluded():
    from great_sdd.conformance.generate import covered_rule_ids
    from great_sdd.conformance.exclusions import NO_FUNCTION_SURFACE_RULES
    assert not (set(covered_rule_ids()) & set(NO_FUNCTION_SURFACE_RULES))
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "probes or covered_rule" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `generate.py` scaffold + pre_estimation probes (template)**

```python
"""Generate GREAT golden conformance fixtures from the deterministic oracle.

Every probe runs against modules constructed with TripwireLM — if a covered
path calls the LM, generation aborts loudly (NonDeterministicError).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdd.base_conformance import (
    Probe, TripwireLM, generate_fixtures, write_fixture_file, read_version,
    canonical_json,
)
from great_sdd.conformance.rule_inventory import (
    business_rule_ids, pending_marker_ids, rule_count)
from great_sdd.conformance.exclusions import (
    NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _pre_estimation_probes() -> list[Probe]:
    from great_sdd.specs.pre_estimation_specs import are_lines_compatible, can_create_custom_ju
    from great_sdd.modules.pre_estimation import (
        PermissionChecker, StatusTransitionValidator, EstimationCalculator,
        SaveValidator, MonthDistributor, InductorSelector, CustomJUPermissionChecker)

    def compat(inp): return {"is_compatible": are_lines_compatible(inp["lines"])}

    probes = [
        # BR-06 / BR-07 — decision via pure function (LM explanation excluded by design).
        Probe(["BR-06", "BR-07"], "line_compatibility", compat, cases=[
            {"lines": [{"organ_type": "A"}, {"organ_type": "A"}]},
            {"lines": [{"organ_type": "A"}, {"organ_type": "B"}]},
            {"lines": [{"injection_system": None}, {"injection_system": None}]},
            {"lines": [{"injection_system": None}, {"injection_system": "X"}]},
        ]),
        # BR-02 / BR-04 — state machine via deterministic module.
        Probe(["BR-02", "BR-04"], "status_transition",
              lambda inp: StatusTransitionValidator(TripwireLM()).forward(**inp), cases=[
            {"current_status": "to_do", "target_status": "draft", "has_saved_draft_in_session": False},
            {"current_status": "draft", "target_status": "estimated", "has_saved_draft_in_session": False},
            {"current_status": "draft", "target_status": "estimated", "has_saved_draft_in_session": True},
            {"current_status": "approved", "target_status": "draft", "has_saved_draft_in_session": True},
        ]),
        # BR-08 / BR-11 / BR-12 — save validation.
        Probe(["BR-08", "BR-11", "BR-12"], "save_validation",
              lambda inp: SaveValidator(TripwireLM()).forward(**inp), cases=[
            {"line_json": json.dumps({"sp_date": "", "status": "to_do", "inductors": []}),
             "save_type": "draft", "has_saved_draft_in_session": False},
            {"line_json": json.dumps({"sp_date": "2026-01-01", "status": "to_do",
             "inductors": [{"selected_cran": "Simple"}]}),
             "save_type": "draft", "has_saved_draft_in_session": False},
            {"line_json": json.dumps({"sp_date": "2026-01-01", "status": "to_do",
             "inductors": [{"is_custom": True}]}),
             "save_type": "draft", "has_saved_draft_in_session": False},
        ]),
        # BR-13 — estimation formula incl. zero occurrence.
        Probe(["BR-13"], "estimation_calc",
              lambda inp: EstimationCalculator(TripwireLM()).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"short_name": "A", "variable": 2.0, "occurrence": 3, "fixed": 1.0, "unit_type": "man_day"},
                {"short_name": "B", "variable": 5.0, "occurrence": 0, "fixed": 0.0, "unit_type": "bench_hours"}])},
        ]),
        # BR-20 — custom JU permissions.
        Probe(["BR-20"], "custom_ju_permission",
              lambda inp: CustomJUPermissionChecker().forward(**inp), cases=[
            {"role": "Engineer"}, {"role": "PMO"}, {"role": "Admin"},
            {"role": "RCRC"}, {"role": "CPO"}]),
        # Permission scope (supports BR-03/BR-05 read-only semantics where applicable).
        Probe(["BR-03"], "permission_check",
              lambda inp: PermissionChecker(TripwireLM()).forward(**inp), cases=[
            {"role": "Engineer", "line_assignee": "u1", "current_user": "u1", "action": "edit"},
            {"role": "Engineer", "line_assignee": "u2", "current_user": "u1", "action": "edit"},
            {"role": "CPO", "line_assignee": "u1", "current_user": "u1", "action": "view"}]),
        # SELECT_INDUCTOR_CRAN deterministic surface (keyword/fallback) — BR-12 path.
        Probe(["BR-12"], "inductor_selection",
              lambda inp: InductorSelector(TripwireLM()).forward(**inp), cases=[
            {"line_description": "complex REST API", "metier": "Backend", "available_inductors_json": "[]"},
            {"line_description": "", "metier": "Frontend", "available_inductors_json": "[]"},
            {"line_description": "x", "metier": "Nonexistent", "available_inductors_json": "[]"}]),
        # MonthDistributor — distribution determinism.
        Probe(["BR-08"], "month_distribution",
              lambda inp: MonthDistributor(TripwireLM()).forward(**inp), cases=[
            {"total_fte": "12.0", "total_bh": "0.0", "total_km": "0.0",
             "sp_date": "2026-01-01", "project_duration_months": "12"}]),
    ]
    return probes


# --- Implement one builder per remaining view, same pattern. See the rule map
#     in the plan's Task 9 appendix for each rule_id -> callable. ---
def _estimation_review_probes() -> list[Probe]: ...
def _allocation_probes() -> list[Probe]: ...
def _final_review_probes() -> list[Probe]: ...
def _management_view_probes() -> list[Probe]: ...
def _transversal_probes() -> list[Probe]: ...


def build_probes() -> dict[str, list[Probe]]:
    return {
        "pre_estimation": _pre_estimation_probes(),
        "estimation_review": _estimation_review_probes(),
        "allocation": _allocation_probes(),
        "final_review": _final_review_probes(),
        "management_view": _management_view_probes(),
        "transversal": _transversal_probes(),
    }


def covered_rule_ids() -> list[str]:
    ids: set[str] = set()
    for probes in build_probes().values():
        for p in probes:
            ids.update(p.rule_ids)
    return sorted(ids)


def _emit(check: bool) -> int:
    version = read_version(REPO_ROOT)
    views = build_probes()
    drift = []
    for view, probes in views.items():
        entries = generate_fixtures(probes, version)
        path = FIXTURES_DIR / f"{view}.json"
        new = canonical_json(entries)
        if check:
            old = path.read_text() if path.exists() else ""
            if old != new:
                drift.append(view)
        else:
            write_fixture_file(path, entries)
    # Inventory snapshot — the reconciled numbers, committed.
    inv = {
        "sdd_version": version,
        "business_rule_count": rule_count(),
        "business_rule_ids": business_rule_ids(),
        "pending_marker_ids": pending_marker_ids(),
        "covered_rule_ids": covered_rule_ids(),
        "non_deterministic_rules": NON_DETERMINISTIC_RULES,
        "no_function_surface_rules": NO_FUNCTION_SURFACE_RULES,
    }
    inv_path = FIXTURES_DIR / "_inventory.json"
    new_inv = canonical_json(inv)
    if check:
        if (inv_path.read_text() if inv_path.exists() else "") != new_inv:
            drift.append("_inventory")
    else:
        write_fixture_file(inv_path, inv)
    if check and drift:
        print(f"FIXTURE DRIFT in: {', '.join(drift)}. Run: python -m great_sdd.conformance.generate", file=sys.stderr)
        return 1
    print(f"{'checked' if check else 'wrote'} fixtures for {len(views)} views @ v{version}; "
          f"{len(covered_rule_ids())}/{rule_count()} business rules covered.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate/verify GREAT conformance fixtures.")
    ap.add_argument("--check", action="store_true", help="Verify committed fixtures are in sync (exit 1 on drift).")
    args = ap.parse_args(argv)
    return _emit(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Implement the remaining 5 view builders**

For each view, write probes mapping each *coverable* business rule to a deterministic callable. Use this rule→callable map (derived from the module inventory; all modules in these 5 views are already deterministic, so call `Module(TripwireLM()).forward(**inp)` or the pure function):

- `estimation_review` → `great_sdd/modules/estimation_review.py`: `EstimationReviewPermissionChecker`, `ApprovalColumnDeriver`, `SendEligibilityChecker` (ERev-BR-02 sent-irreversible, ERev-BR-04 only-estimated-sends), `HVTCallbackProcessor`, `HVTPayloadGenerator`, `CSVExporter`. One probe per `ERev-BR-01..10` with boundary cases.
- `allocation` → `great_sdd/modules/allocation.py`: `AllocationEligibilityFilter` (ALLOC-BR-01 approved-only), `AllocationRuleMatcher` (ALLOC-BR-02 no-overwrite), `KECalculator` (rate formulas), `TCPopupHandler`, `SplitAllocationHandler` (ALLOC-BR-11 100%), `AllocationSaveValidator` (ALLOC-BR-06), `HProjectRouter`, `JUMetierRouter` (ALLOC-BR-17), `DiversityDropdownHandler`, `BulkAssigner`, `AllocationPermissionChecker`. One probe per `ALLOC-BR-01..17`.
- `final_review` → `great_sdd/modules/final_review.py`: `FinalReviewEligibilityFilter`, `AggregationEngine`, `CSVGlobalExporter`, `Stage3Sender` (FR-BR-06 warns-not-blocks), `FinalReviewPermissionChecker`. One probe per `FR-BR-01..10`.
- `management_view` → `great_sdd/modules/management_view.py`: `ManagementAccessChecker`, `PieChartBuilder`, `TimelineBuilder`, `MetierFilter`. One probe per `MGMT-BR-01..08`.
- `transversal` → `great_sdd/modules/transversal.py`: `CycleManager` (CYCLE-BR-01 one-active, CYCLE-BR-02 no-reactivation), `WorkloadStandardManager` (WL-BR-*), `BulkInductorDeleter` (DEL-BR-*), `TableStateManager` (TABLE-BR-*), `EmailAlertService` (EMAIL-BR-* — assert template structure, not any LM text). One probe per coverable id.

For each probe, read the module's `forward` signature and the matching `*_specs.py` rule text first, build inputs that exercise the rule's boundary. Any id with no callable surface → add to `NO_FUNCTION_SURFACE_RULES` (Task 8) with a reason instead of forcing a probe. Re-run `test_exclusions_*` and `test_no_rule_is_both_covered_and_excluded` after edits.

- [ ] **Step 5: Run determinism tests + generate fixtures**

```bash
python -m pytest tests/test_conformance.py -k "probes or covered_rule" -v
python -m great_sdd.conformance.generate          # writes fixtures/*.json
python -m great_sdd.conformance.generate --check   # exit 0 (in sync)
echo "exit: $?"
```
Expected: tests PASS; generator writes files; `--check` exits 0.

- [ ] **Step 6: Add a fixtures-in-sync test**

```python
def test_committed_fixtures_are_in_sync():
    from great_sdd.conformance.generate import main
    assert main(["--check"]) == 0
```
Run: `python -m pytest tests/test_conformance.py -k "in_sync" -v` → PASS.

- [ ] **Step 7: Commit (per view is fine; final commit includes fixtures)**

```bash
git add great_sdd/conformance/generate.py great_sdd/conformance/fixtures tests/test_conformance.py
git commit -m "feat: conformance fixture generator + committed golden fixtures (6 views)"
```

---

## Task 10: `coverage.py` CLI

**Files:**
- Create: `great_sdd/conformance/coverage.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
def test_coverage_cli_from_fixtures_passes_at_achieved_threshold(capsys):
    from great_sdd.conformance.coverage import main
    # Threshold 0.0 always passes; asserts JSON + exit 0.
    rc = main(["--from-fixtures", "--threshold", "0.0", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "coverage" in out and "version_skew" in out and out["coverage"]["passed"]

def test_coverage_cli_fails_below_threshold():
    from great_sdd.conformance.coverage import main
    assert main(["--from-fixtures", "--threshold", "1.0"]) == 1   # 100% impossible (exclusions)

def test_coverage_cli_detects_version_skew(tmp_path):
    from great_sdd.conformance.coverage import main
    rep = tmp_path / "consumer.json"
    rep.write_text(json.dumps({"sdd_version": "0.0.1", "exercised_rule_ids": ["BR-02"]}))
    assert main(["--report", str(rep), "--threshold", "0.0"]) == 1  # skew → nonzero
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "coverage_cli" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `coverage.py`**

```python
"""Coverage + version-skew gate for GREAT conformance.

Inputs (one of):
  --report PATH     consumer report: {"sdd_version": "...", "exercised_rule_ids": [...]}
  --from-fixtures   use the union of rule_ids in the committed fixtures (oracle self-check)

Exit code != 0 if coverage < threshold OR version skew detected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdd.base_conformance import compute_coverage, compute_version_skew, read_version
from great_sdd.conformance.rule_inventory import business_rule_ids
from great_sdd.conformance.exclusions import NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES
from great_sdd.conformance.generate import REPO_ROOT, FIXTURES_DIR, covered_rule_ids


def _denominator() -> list[str]:
    """Business rules minus deterministic-but-unprobeable ones (documented)."""
    excluded = set(NO_FUNCTION_SURFACE_RULES)
    return [r for r in business_rule_ids() if r not in excluded]


def _fixture_exercised_ids() -> list[str]:
    ids: set[str] = set()
    for fp in sorted(FIXTURES_DIR.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        for entry in json.loads(fp.read_text()):
            ids.update(entry["rule_ids"])
    return sorted(ids)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GREAT conformance coverage gate.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--report", help="Path to consumer report JSON.")
    src.add_argument("--from-fixtures", action="store_true", help="Use committed fixtures.")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(argv)

    oracle_version = read_version(REPO_ROOT)
    if args.from_fixtures:
        exercised = _fixture_exercised_ids()
        consumer_version = oracle_version
    else:
        data = json.loads(Path(args.report).read_text())
        exercised = data.get("exercised_rule_ids", [])
        consumer_version = data.get("sdd_version", "")

    cov = compute_coverage(_denominator(), exercised, args.threshold)
    skew = compute_version_skew(consumer_version, oracle_version)
    report = {
        "coverage": cov,
        "version_skew": skew,
        "excluded": {
            "non_deterministic": NON_DETERMINISTIC_RULES,
            "no_function_surface": NO_FUNCTION_SURFACE_RULES,
        },
    }
    if args.json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Coverage: {cov['covered_count']}/{cov['total']} "
              f"({cov['coverage']*100:.1f}%) threshold={cov['threshold']*100:.0f}% "
              f"-> {'PASS' if cov['passed'] else 'FAIL'}")
        if cov["missing"]:
            print(f"  Uncovered (no probe yet): {', '.join(cov['missing'])}")
        print(f"  Excluded (LM-only): {', '.join(sorted(NON_DETERMINISTIC_RULES))}")
        print(f"  Excluded (no surface): {', '.join(sorted(NO_FUNCTION_SURFACE_RULES))}")
        print(f"Version: consumer={skew['consumer_version']} oracle={skew['oracle_version']} "
              f"-> {'SKEW' if skew['skew'] else 'OK'}")
    return 0 if (cov["passed"] and not skew["skew"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "coverage_cli" -v`
Expected: PASS.

- [ ] **Step 5: Record achieved coverage (sets the CI threshold)**

```bash
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.0
```
Note the percentage; CI threshold (Task 13) = floor a few points below it.

- [ ] **Step 6: Commit**

```bash
git add great_sdd/conformance/coverage.py tests/test_conformance.py
git commit -m "feat: conformance coverage + version-skew gate CLI"
```

---

## Task 11: `runner.py` + example Python consumer

**Files:**
- Create: `great_sdd/conformance/runner.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing tests**

```python
def test_runner_against_oracle_consumer_is_all_green():
    from great_sdd.conformance.runner import run_against_fixtures, oracle_consumer_fn
    rep = run_against_fixtures(consumer_fn=oracle_consumer_fn)
    assert rep["passed"] is True, rep["failures"][:2]
    assert len(rep["exercised_rule_ids"]) >= 1

def test_runner_reports_mismatch():
    from great_sdd.conformance.runner import run_against_fixtures
    rep = run_against_fixtures(consumer_fn=lambda inp: {"bogus": True})
    assert rep["passed"] is False and rep["failed_count"] > 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_conformance.py -k "runner" -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `runner.py`**

The example `oracle_consumer_fn` dispatches by `rule_ids` to the same deterministic callables the generator used (proving an importing Python backend matches the contract). It builds a dispatch table mapping each probe's `name`/`rule_ids` to its `fn`. Simplest robust approach: reuse `build_probes()` to construct a lookup keyed by a stable signature of the input.

```python
"""Run a consumer against the committed GREAT fixtures (no network).

A consumer_fn(input: dict) -> dict re-implements the rule; the runner exact-matches
its output against expected_output and reports which rule_ids were exercised
(feed that to coverage.py).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdd.base_conformance import run_conformance, normalize_output
from great_sdd.conformance.generate import FIXTURES_DIR, build_probes


def load_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> list[dict]:
    entries: list[dict] = []
    for fp in sorted(Path(fixtures_dir).glob("*.json")):
        if fp.name.startswith("_"):
            continue
        entries.extend(json.loads(fp.read_text()))
    return entries


def _oracle_dispatch() -> dict[str, callable]:
    """Map a canonical input signature -> the probe fn that produced it."""
    table = {}
    for probes in build_probes().values():
        for p in probes:
            for case in p.cases:
                table[json.dumps(case, sort_keys=True)] = p.fn
    return table


def oracle_consumer_fn(inp: dict) -> dict:
    """Reference consumer: an importing Python backend re-running the oracle."""
    fn = _oracle_dispatch()[json.dumps(inp, sort_keys=True)]
    return normalize_output(fn(inp))


def run_against_fixtures(consumer_fn, fixtures_dir: Path = FIXTURES_DIR) -> dict:
    return run_conformance(load_fixtures(fixtures_dir), consumer_fn)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the reference consumer against committed fixtures.")
    ap.add_argument("--emit-report", help="Write a consumer report for coverage.py.")
    args = ap.parse_args(argv)
    rep = run_against_fixtures(oracle_consumer_fn)
    print(f"Conformance: {rep['total']-rep['failed_count']}/{rep['total']} passed; "
          f"{len(rep['exercised_rule_ids'])} rules exercised.")
    if args.emit_report:
        from sdd.base_conformance import read_version
        from great_sdd.conformance.generate import REPO_ROOT
        Path(args.emit_report).write_text(json.dumps({
            "sdd_version": read_version(REPO_ROOT),
            "exercised_rule_ids": rep["exercised_rule_ids"],
        }, sort_keys=True, indent=2))
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_conformance.py -k "runner" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/runner.py tests/test_conformance.py
git commit -m "feat: conformance runner + reference Python consumer"
```

---

## Task 12: Cross-language contract README

**Files:**
- Create: `great_sdd/conformance/README.md`

- [ ] **Step 1: Write the README**

Contents (no code-test step; this is documentation):
- **What conformance is:** the SDD as deterministic oracle; fixtures are the contract.
- **Fixture schema:** the four keys, with a real example entry copied from `fixtures/pre_estimation.json`. Note `*_json` fields are already parsed JSON values (language-neutral), thanks to `normalize_output`.
- **Python consumer:** 6-line snippet using `runner.run_against_fixtures(my_consumer_fn)`.
- **TypeScript consumer (FE cannot import Python):** worked example —
  ```ts
  import fixtures from "great-sdd-kit/great_sdd/conformance/fixtures/pre_estimation.json";
  // reimplement the rule in TS, then exact-match:
  for (const fx of fixtures) {
    const actual = myStatusTransition(fx.input);          // your TS impl
    expect(actual).toEqual(fx.expected_output);            // deep equal
  }
  ```
  Explain: FE re-implements the rule, loads the SAME JSON, asserts deep-equal; emits the union of `rule_ids` it ran as its own `exercised_rule_ids` report for `coverage.py`. Stress: never serialize Python objects into fixtures — only JSON-neutral values (enforced by `canonical_json` + `normalize_output`).
- **Version skew:** consumers pin a fixtures `sdd_version`; `coverage.py` flags mismatch vs the live oracle.
- **Regenerating:** `python -m great_sdd.conformance.generate`; CI fails on drift.

- [ ] **Step 2: Commit**

```bash
git add great_sdd/conformance/README.md
git commit -m "docs: cross-language conformance contract (Python + TypeScript)"
```

---

## Task 13: CI gate

**Files:**
- Create: `.github/workflows/conformance.yml`

- [ ] **Step 1: Write the workflow** (set `--threshold` to the value recorded in Task 10 Step 5, a few points below achieved)

```yaml
name: conformance
on:
  push: { branches: [master] }
  pull_request: {}
jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pytest
      - name: Fixtures in sync with oracle
        run: python -m great_sdd.conformance.generate --check
      - name: Unit + conformance tests
        run: python -m pytest tests/ -q
      - name: Coverage gate
        run: python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
```

- [ ] **Step 2: Validate locally (the three gate commands)**

```bash
python -m great_sdd.conformance.generate --check && echo "sync OK"
python -m pytest tests/ -q
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
```
Expected: all three exit 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/conformance.yml
git commit -m "ci: conformance gate — fixture sync, tests, coverage threshold"
```

---

## Task 14: Reconcile docs + counts (derived numbers)

**Files:**
- Modify: `README.md`, `AGENTS.md`, `SDD-OVERVIEW.md`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Add a guard test for the canonical number in docs**

```python
def test_docs_state_canonical_rule_count():
    from great_sdd.conformance.rule_inventory import rule_count
    n = str(rule_count())   # 92
    for doc in ("README.md", "AGENTS.md", "SDD-OVERVIEW.md"):
        text = open(doc, encoding="utf-8").read()
        assert "74 reglas" not in text and "78 reglas" not in text, f"{doc} stale rule count"
        assert n in text, f"{doc} missing canonical count {n}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_conformance.py -k "canonical_rule_count" -v`
Expected: FAIL — docs still say 74/78.

- [ ] **Step 3: Edit the three docs**

- Replace every "74 reglas" / "78 reglas" / "~84" with "92 reglas de negocio" (and "92 reglas" in tables/headers). Add one line where rules are introduced: "(92 reglas con ID, derivado por `great_sdd/conformance/rule_inventory.py`; +9 marcadores pendientes sin ID de regla)."
- Replace test-count claims (216 / 257) with the real collected count. Get it: `python -m pytest tests/ --collect-only -q | tail -1`; use that number consistently.
- `AGENTS.md:38` and `README.md:66,293` — the `base_pipeline.py` line is now TRUE (Task 2); leave the reference. (If Task 2 had been skipped, delete these lines instead.)
- `README.md:103,228` — `test_pre_estimation.py` does not exist. Fix to `tests/test_pipeline.py` and correct the per-file count, OR add a note that Pre-Estimation tests live in `test_pipeline.py`. Update the `(68 tests)` annotation to the real number for that file.
- Add a short "Conformance (4th layer)" subsection to `README.md` and `SDD-OVERVIEW.md` pointing at `great_sdd/conformance/README.md`.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_conformance.py -k "canonical_rule_count" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md SDD-OVERVIEW.md tests/test_conformance.py
git commit -m "docs: reconcile rule count (92, derived), test count, fix stale file refs"
```

---

## Task 15: Version sync fix + bump_version extension

**Files:**
- Modify: `scripts/bump_version.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write failing test**

```python
def test_versions_are_in_sync():
    import json, re
    init = open("great_sdd/__init__.py").read()
    iv = re.search(r'__version__ = "(\d+\.\d+\.\d+)"', init).group(1)
    pv = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', open("pyproject.toml").read(), re.M).group(1)
    jv = json.load(open("package.json"))["version"]
    assert iv == pv == jv, f"version drift: init={iv} pyproject={pv} package={jv}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_conformance.py -k "versions_are_in_sync" -v`
Expected: FAIL — init/pyproject=1.1.0, package.json=1.2.0.

- [ ] **Step 3: Extend `scripts/bump_version.py`**

Add `PACKAGE_FILE = REPO_ROOT / "package.json"` and, in `main()`, after updating init+pyproject:
```python
    # Keep package.json in sync (JSON-safe edit).
    import json as _json
    pkg = _json.loads(PACKAGE_FILE.read_text())
    pkg["version"] = new
    PACKAGE_FILE.write_text(_json.dumps(pkg, indent=2) + "\n")
    print(f"  updated {PACKAGE_FILE}")
```
And add `str(PACKAGE_FILE)` and `str(REPO_ROOT / "CHANGELOG.md")` to the `git add` list so the version commit includes them. Update the docstring's "Updates:" block accordingly.

- [ ] **Step 4: Bring the three files to the same current version (pre-bump)**

The bump in Task 16 will set the final number; first eliminate the existing drift by hand so the bump starts clean. Set `package.json` version back to `1.1.0` (matching init/pyproject) — the real release bump happens next.
Run: `python -m pytest tests/test_conformance.py -k "versions_are_in_sync" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/bump_version.py package.json tests/test_conformance.py
git commit -m "fix: sync versions; bump_version also updates package.json + stages CHANGELOG"
```

---

## Task 16: Full suite, CHANGELOG, MINOR bump

**Files:**
- Modify: `CHANGELOG.md`, `pyproject.toml` (description), `great_sdd/__init__.py` (docstring counts)

- [ ] **Step 1: Run the whole suite + the gate**

```bash
python -m pytest tests/ -q
python -m great_sdd.conformance.generate --check
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
```
Expected: all green. Fix anything red before proceeding (do not bump on red).

- [ ] **Step 2: Update prose counts in packaging**

- `pyproject.toml:8` description: change "78 business rules ... 257 tests" to the derived numbers (92 rules; real test count).
- `great_sdd/__init__.py:3` docstring: "92 business rules as executable specs, <N> tests".

- [ ] **Step 3: Add CHANGELOG entry**

Prepend a new section under the latest version header:
```markdown
## [1.3.0] - 2026-06-05
### Added
- Conformance layer (4th layer): deterministic oracle + golden fixtures.
  - `sdd/base_conformance.py` (engine), `sdd/base_pipeline.py` (base class).
  - `great_sdd/conformance/`: generate, coverage, runner, rule_inventory, exclusions, fixtures, README.
  - CI gate `.github/workflows/conformance.yml` (fixture sync + tests + coverage).
### Changed
- `InductorSelector` refactored from LM-driven to deterministic rule-based selection.
- Reconciled rule count to 92 (derived) across README/AGENTS/SDD-OVERVIEW; fixed stale `test_pre_estimation.py` reference; test count corrected.
- `bump_version.py` now syncs `package.json` and stages `CHANGELOG.md`.
### Fixed
- Version drift across `__init__`, `pyproject.toml`, `package.json`.
- Untracked committed `node_modules/`.
```

- [ ] **Step 4: Stage CHANGELOG + run the MINOR bump**

```bash
git add CHANGELOG.md pyproject.toml great_sdd/__init__.py
git commit -m "docs: changelog + packaging counts for 1.3.0"
```
**Target version LOCKED = 1.3.0** (clean MINOR above the historical 1.2.0 tag left in package.json). The script bumps from `__init__` (1.1.0) → 1.2.0, so to land on 1.3.0: first set all three files (init/pyproject/package.json) to `1.2.0`, commit, then run `python3 scripts/bump_version.py minor` → 1.3.0. Verify the resulting `v1.3.0` tag does not collide before pushing.

- [ ] **Step 5: Regenerate fixtures for the new version + re-verify sync**

The bump changes `sdd_version` baked into every fixture. Regenerate and amend:
```bash
python -m great_sdd.conformance.generate
python -m great_sdd.conformance.generate --check && echo "sync OK"
python -m pytest tests/ -q
git add great_sdd/conformance/fixtures
git commit -m "chore: regenerate fixtures for bumped sdd_version"
```

- [ ] **Step 6: Final summary**

Print the reconciliation report for the user:
```bash
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
```
Report: covered business rules (list), quarantined (`NON_DETERMINISTIC_RULES`), no-surface excluded (`NO_FUNCTION_SURFACE_RULES`), total 92, achieved coverage %, version, test count.

---

## Self-Review

**Spec coverage vs the 6 deliverables + secondary tasks:**
1. Oracle/generator → Tasks 3,4,9 (`base_conformance.generate_fixtures` + `generate.py`). ✓ (byte-stable: `canonical_json` sorted keys/no timestamps; `sdd_version` from pyproject — Task 3.)
2. Committed golden fixtures → Task 9 Step 5/7 (`fixtures/*.json`, neutral JSON via `normalize_output`). ✓
3. Coverage reporter (BR % + version skew, JSON + human, nonzero exit) → Task 10. ✓
4. Consumer runner (load pinned fixtures, consumer_fn, exact match, emit exercised ids, Python example) → Tasks 5,11. ✓
5. Cross-language TS contract README → Task 12. ✓
6. CI gate (regen+diff, pytest, coverage) → Task 13. ✓
- Determinism hard-constraint + fail-loud → `TripwireLM` (Task 3), enforced in every probe (Task 9), tested (Task 4). ✓
- `InductorSelector` deterministic refactor + `NON_DETERMINISTIC_RULES` → Tasks 6,8. ✓
- Rule-count reconciliation (derived) → Tasks 7,14. ✓
- `base_pipeline.py` exists → Task 2. ✓ test_pre_estimation doc fix → Task 14. ✓ node_modules untracked → Task 1. ✓
- stdlib+pytest only ✓; new code tested ✓; semver bump+CHANGELOG → Tasks 15,16 ✓; no business-logic change except InductorSelector ✓.

**Placeholder scan:** view builders for 5 views (Task 9 Step 4) are specified by rule→callable map rather than full inline code — intentional: each requires reading that module's `forward` signature + spec text first; the pre_estimation builder is the complete worked template. Flagged, not hidden.

**Type consistency:** `Probe(rule_ids,name,fn,cases)`, `generate_fixtures(probes,version)`, `compute_coverage(all,covered,threshold)->dict`, `run_conformance(fixtures,consumer_fn)->dict`, `normalize_output(dict)->dict` used consistently across Tasks 3–11. Fixture entry keys `{rule_ids,input,expected_output,sdd_version}` consistent generator↔runner↔coverage.

**Open execution-time decision:** final version number (1.2.0 vs 1.3.0) — Task 16 Step 4 flags it for confirmation before tagging/pushing.
