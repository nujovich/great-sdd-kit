# Endpoint Conformance — `GET /project-lines` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an endpoint-conformance sub-layer that emits a deterministic golden fixture mirroring the external `GET /project-lines` contract, consumed cross-language (Python back + TS front), without touching the 92-rule census.

**Architecture:** A parallel `EndpointProbe` abstraction in `sdd/base_conformance.py` (engine, domain-agnostic) + a deterministic oracle in `great_sdd/conformance/endpoints/project_lines.py` that mirrors the FastAPI `list_lines` behavior over a fixed seed. Generation/runner/coverage are extended to handle endpoint fixtures alongside rule fixtures, reusing the byte-stable writer and the `--check` gate.

**Tech Stack:** Python 3.11+ (run with `python3` — the only interpreter here with pytest; `sdd/` and `great_sdd/conformance/` use `from __future__ import annotations` for 3.8 import-compat). pytest. No network/LLM/time/randomness.

**Spec:** `docs/superpowers/specs/2026-06-10-endpoint-conformance-project-lines-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `sdd/base_conformance.py` (modify) | + `EndpointProbe`, `generate_endpoint_fixtures`, `run_endpoint_conformance` — engine primitives, no domain knowledge |
| `great_sdd/conformance/endpoints/__init__.py` (create) | package marker |
| `great_sdd/conformance/endpoints/project_lines.py` (create) | SEED + `list_project_lines` oracle + `PROBE` — mirrors external contract |
| `great_sdd/conformance/generate.py` (modify) | emit endpoint fixtures; `--check` covers them |
| `great_sdd/conformance/runner.py` (modify) | `oracle_endpoint_consumer_fn` + endpoint runner |
| `great_sdd/conformance/coverage.py` (modify) | print a separate endpoints-covered block |
| `great_sdd/conformance/fixtures/endpoints/project_lines.json` (generated) | golden fixture |
| `tests/test_conformance.py` (modify) | endpoint-conformance tests |
| `great_sdd/conformance/README.md` (modify) | document the endpoints sub-layer |

---

### Task 1: Engine primitives in `base_conformance.py`

**Files:**
- Modify: `sdd/base_conformance.py` (append after `run_conformance`)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conformance.py`:

```python
# ═══════════════════════════════════════════════════════════
# endpoint conformance — engine primitives
# ═══════════════════════════════════════════════════════════
def test_endpoint_probe_generates_sorted_byte_stable_fixture():
    from sdd.base_conformance import EndpointProbe, generate_endpoint_fixtures
    probe = EndpointProbe(
        endpoint="GET /demo", name="demo",
        fn=lambda req: {"status": 200, "body": {"echo": req.get("q")}},
        cases=[{"q": "b"}, {"q": "a"}])
    seed = [{"id": "1"}]
    fx = generate_endpoint_fixtures(probe, seed, "9.9.9")
    assert fx["endpoint"] == "GET /demo"
    assert fx["sdd_version"] == "9.9.9"
    assert fx["seed"] == seed
    # cases sorted by canonical_json(request): {"q":"a"} before {"q":"b"}
    assert [c["request"]["q"] for c in fx["cases"]] == ["a", "b"]
    assert fx["cases"][0]["expected"] == {"status": 200, "body": {"echo": "a"}}


def test_run_endpoint_conformance_exact_match_and_never_passes_expected():
    from sdd.base_conformance import EndpointProbe, generate_endpoint_fixtures, run_endpoint_conformance
    probe = EndpointProbe(
        endpoint="GET /demo", name="demo",
        fn=lambda req: {"status": 200, "body": {"echo": req["q"]}},
        cases=[{"q": "a"}])
    fx = generate_endpoint_fixtures(probe, [], "9.9.9")

    seen_keys = []
    def consumer(req):
        seen_keys.append(set(req))
        return {"status": 200, "body": {"echo": req["request"]["q"]}}
    rep = run_endpoint_conformance(fx, consumer)
    assert rep["passed"] and rep["failed_count"] == 0 and rep["total"] == 1
    # consumer receives endpoint/request/seed, never "expected"
    assert seen_keys[0] == {"endpoint", "request", "seed"}

    bad = run_endpoint_conformance(fx, lambda req: {"status": 500, "body": None})
    assert not bad["passed"] and bad["failures"][0]["actual"]["status"] == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_endpoint_probe_generates_sorted_byte_stable_fixture tests/test_conformance.py::test_run_endpoint_conformance_exact_match_and_never_passes_expected -v`
Expected: FAIL with `ImportError: cannot import name 'EndpointProbe'`

- [ ] **Step 3: Write minimal implementation**

Append to `sdd/base_conformance.py` (after `run_conformance`, end of file):

```python
# ── Endpoint conformance ──

@dataclass
class EndpointProbe:
    """Binds an HTTP endpoint to a deterministic fn over representative requests.

    fn(request: dict) -> {"status": int, "body": dict | None}. One probe per
    fixture file (one endpoint per file).
    """
    endpoint: str
    name: str
    fn: Callable[[dict], dict]
    cases: list[dict] = field(default_factory=list)


def generate_endpoint_fixtures(probe: EndpointProbe, seed: list, sdd_version: str) -> dict:
    """Run every request case; emit one byte-stable fixture dict.

    Shape: {endpoint, sdd_version, seed, cases:[{request, expected}]}, cases sorted
    by canonical_json(request). fn runs under the caller-injected determinism guard.
    """
    cases = [{"request": req, "expected": probe.fn(req)} for req in probe.cases]
    cases.sort(key=lambda c: canonical_json(c["request"]))
    return {
        "endpoint": probe.endpoint,
        "sdd_version": sdd_version,
        "seed": seed,
        "cases": cases,
    }


def run_endpoint_conformance(fixture: dict, consumer_fn: Callable[[dict], dict]) -> dict:
    """Run consumer_fn against each case; exact-match {status, body}.

    consumer_fn receives {"endpoint", "request", "seed"} — never "expected", so it
    cannot cheat. A backend uses "seed" to set up identical state before calling.
    """
    endpoint = fixture.get("endpoint", "")
    seed = fixture.get("seed", [])
    failures = []
    for case in fixture["cases"]:
        actual = consumer_fn({"endpoint": endpoint, "request": case["request"], "seed": seed})
        if actual != case["expected"]:
            failures.append({
                "request": case["request"],
                "expected": case["expected"],
                "actual": actual,
            })
    return {
        "endpoint": endpoint,
        "total": len(fixture["cases"]),
        "failed_count": len(failures),
        "passed": not failures,
        "failures": failures,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_endpoint_probe_generates_sorted_byte_stable_fixture tests/test_conformance.py::test_run_endpoint_conformance_exact_match_and_never_passes_expected -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add sdd/base_conformance.py tests/test_conformance.py
git commit -m "feat(conformance): EndpointProbe + endpoint fixture/runner primitives"
```

---

### Task 2: Project-lines oracle (`endpoints/project_lines.py`)

**Files:**
- Create: `great_sdd/conformance/endpoints/__init__.py`
- Create: `great_sdd/conformance/endpoints/project_lines.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conformance.py`:

```python
# ═══════════════════════════════════════════════════════════
# endpoint conformance — GET /project-lines oracle
# ═══════════════════════════════════════════════════════════
def test_project_lines_engineer_is_scoped_to_own_lines():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    out = list_project_lines({"role": "Engineer", "user_oid": "oid-engineer-1",
                              "query": {}, "active_cycle": True})
    assert out["status"] == 200
    pls = [r["pl_number"] for r in out["body"]["data"]]
    assert pls == ["PL-001", "PL-003"]                       # only engineer-1's lines, sorted
    assert out["body"]["filterOptions"]["assignees"] == ["oid-engineer-1"]
    assert out["body"]["filterOptions"]["metiers"] == ["H-NP", "H-SOFTWARE"]


def test_project_lines_engineer_ignores_assignee_query():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    out = list_project_lines({"role": "Engineer", "user_oid": "oid-engineer-1",
                              "query": {"assignee": "oid-engineer-2"}, "active_cycle": True})
    assert [r["pl_number"] for r in out["body"]["data"]] == ["PL-001", "PL-003"]


def test_project_lines_pmo_sees_all_and_can_filter_metier():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    all_out = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                                  "query": {}, "active_cycle": True})
    assert [r["pl_number"] for r in all_out["body"]["data"]] == ["PL-001", "PL-002", "PL-003", "PL-004"]
    assert all_out["body"]["filterOptions"]["metiers"] == ["H-DESIGN", "H-NP", "H-PROJECT", "H-SOFTWARE"]

    filtered = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                                   "query": {"metier": "H-DESIGN"}, "active_cycle": True})
    assert [r["pl_number"] for r in filtered["body"]["data"]] == ["PL-002"]
    # filterOptions ignore active filters -> still the full set
    assert filtered["body"]["filterOptions"]["metiers"] == ["H-DESIGN", "H-NP", "H-PROJECT", "H-SOFTWARE"]


def test_project_lines_status_codes():
    from great_sdd.conformance.endpoints.project_lines import list_project_lines
    assert list_project_lines({"role": "CPO", "active_cycle": True})["status"] == 403
    assert list_project_lines({"role": "PMO", "active_cycle": False})["status"] == 404
    assert list_project_lines({"role": None, "active_cycle": True})["status"] == 401
    for code in (403, 404, 401):
        pass  # bodies are null on non-200
    assert list_project_lines({"role": "CPO", "active_cycle": True})["body"] is None


def test_project_lines_rows_have_24_contract_fields_and_no_h_testing():
    from great_sdd.conformance.endpoints.project_lines import (
        list_project_lines, PROJECT_LINE_FIELDS)
    out = list_project_lines({"role": "PMO", "user_oid": "oid-pmo",
                              "query": {}, "active_cycle": True})
    assert len(PROJECT_LINE_FIELDS) == 24
    for row in out["body"]["data"]:
        assert set(row) == set(PROJECT_LINE_FIELDS)
        assert row["metier"] != "H-TESTING"
        assert row["total_days"] is None and row["total_keuro"] is None
    assert "H-TESTING" not in out["body"]["filterOptions"]["metiers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py -k project_lines -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'great_sdd.conformance.endpoints'`

- [ ] **Step 3: Write minimal implementation**

Create `great_sdd/conformance/endpoints/__init__.py`:

```python
"""Endpoint-conformance oracles — deterministic mirrors of external API contracts."""
```

Create `great_sdd/conformance/endpoints/project_lines.py`:

```python
"""Endpoint conformance oracle for GET /project-lines.

MIRRORS THE EXTERNAL CONTRACT (cap_horse_great/docs/open-api/pev-openapi.yaml +
the FastAPI service list_lines). The SDD is NOT the source of truth here — this
re-implements the documented endpoint behavior deterministically so a Python
backend and a TypeScript frontend can both prove conformance against ONE golden
fixture. No view/rules are added to the business-rule census.

Deterministic: fixed UUIDs/OIDs, no network/LLM/time/randomness.
"""
from __future__ import annotations

from sdd.base_conformance import EndpointProbe

# Métier enum MIRRORED FROM THE EXTERNAL CONTRACT (ProjectLineMetier). This
# intentionally EXCLUDES H-TESTING and therefore differs from the SDD métier
# taxonomy in great_sdd/specs/pre_estimation_specs.py. Do NOT "fix" it toward the
# SDD set — the endpoint contract is the source of truth here.
PROJECT_LINE_METIERS = [
    "H-DESIGN", "H-TUNING", "H-SOFTWARE", "H-CUSTOMER", "H-PROJECT", "H-NP",
]
STATUSES = ["To do", "Draft", "Estimated", "Sent", "Rejected", "Approved"]
ROLES_ALLOWED = {"Admin", "PMO", "RCRC", "Engineer"}

# The 24 response fields in the contract's order (ProjectLine DTO). `assignee`
# maps from the DB column assignee_oid.
PROJECT_LINE_FIELDS = [
    "id", "pl_number", "pl_name", "status", "request_type", "client", "metier",
    "organ_type", "project_ranking", "market", "alliance_code", "vehicle_code",
    "energy", "injection_system", "standard_emissions", "engineering",
    "estimate_type", "sp_date", "pc_date", "co_date", "sop_date", "assignee",
    "total_days", "total_keuro",
]


def _row(uuid: str, pl_number: str, pl_name: str, metier: str,
         status: str, assignee_oid: str) -> dict:
    """A full 24-field project-line row; every unset field is null."""
    row = {field: None for field in PROJECT_LINE_FIELDS}
    row.update({
        "id": uuid, "pl_number": pl_number, "pl_name": pl_name,
        "metier": metier, "status": status, "assignee": assignee_oid,
    })
    return row


# Deterministic seed — fixed UUIDs/OIDs. Includes H-NP and H-PROJECT (the contract
# returns them); never H-TESTING (not a valid project-line métier).
SEED = [
    _row("11111111-1111-4111-8111-111111111111", "PL-001", "Auth refactor",
         "H-SOFTWARE", "Rejected", "oid-engineer-1"),
    _row("22222222-2222-4222-8222-222222222222", "PL-002", "OAuth integration",
         "H-DESIGN", "To do", "oid-engineer-2"),
    _row("33333333-3333-4333-8333-333333333333", "PL-003", "NP line",
         "H-NP", "To do", "oid-engineer-1"),
    _row("44444444-4444-4444-8444-444444444444", "PL-004", "Infra deploy",
         "H-PROJECT", "Draft", "oid-pmo"),
]


def list_project_lines(request: dict) -> dict:
    """Deterministic reference for GET /project-lines.

    request -> {"status": int, "body": dict | None}. Mirrors list_lines + the
    openapi access rules:
      - no active cycle -> 404; no role/JWT -> 401; CPO (or other) -> 403
      - Engineer hard-scoped to own assignee_oid (the assignee query is ignored)
      - PMO/Admin/RCRC honor the assignee/metier query
      - filterOptions reflect the role-scoped set, ignoring active filters
    """
    role = request.get("role")
    if not request.get("active_cycle", True):
        return {"status": 404, "body": None}
    if role is None:
        return {"status": 401, "body": None}
    if role not in ROLES_ALLOWED:                       # CPO and anything else
        return {"status": 403, "body": None}

    query = request.get("query") or {}
    user_oid = request.get("user_oid")

    if role == "Engineer":
        scope_oid = user_oid
        effective_assignee = user_oid                   # ignore the assignee query
    else:
        scope_oid = None
        effective_assignee = query.get("assignee")

    # Role-scoped set drives filterOptions (ignores active filters).
    scoped = [r for r in SEED if scope_oid is None or r["assignee"] == scope_oid]

    metier_filter = query.get("metier")
    data = sorted(
        (r for r in scoped
         if (effective_assignee is None or r["assignee"] == effective_assignee)
         and (metier_filter is None or r["metier"] == metier_filter)),
        key=lambda r: r["pl_number"],
    )
    filter_options = {
        "assignees": sorted({r["assignee"] for r in scoped if r["assignee"] is not None}),
        "metiers": sorted({r["metier"] for r in scoped}),
    }
    return {"status": 200, "body": {"data": data, "filterOptions": filter_options}}


PROBE = EndpointProbe(
    endpoint="GET /project-lines",
    name="project_lines_list",
    fn=list_project_lines,
    cases=[
        {"role": "Engineer", "user_oid": "oid-engineer-1", "query": {}, "active_cycle": True},
        {"role": "Engineer", "user_oid": "oid-engineer-1",
         "query": {"assignee": "oid-engineer-2"}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {"metier": "H-DESIGN"}, "active_cycle": True},
        {"role": "CPO", "user_oid": "oid-cpo", "query": {}, "active_cycle": True},
        {"role": "PMO", "user_oid": "oid-pmo", "query": {}, "active_cycle": False},
        {"role": None, "user_oid": None, "query": {}, "active_cycle": True},
    ],
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py -k project_lines -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/endpoints/ tests/test_conformance.py
git commit -m "feat(conformance): GET /project-lines deterministic oracle + seed"
```

---

### Task 3: Wire generation + emit the golden fixture

**Files:**
- Modify: `great_sdd/conformance/generate.py:18-31` (imports + dirs) and `_emit`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conformance.py` (note `os` and `json` are already imported at the top of this file):

```python
def test_endpoint_fixture_is_generated_and_byte_stable():
    from great_sdd.conformance.generate import ENDPOINTS_DIR, build_endpoint_fixtures
    from sdd.base_conformance import canonical_json, read_version
    from great_sdd.conformance.generate import REPO_ROOT
    path = os.path.join(str(ENDPOINTS_DIR), "project_lines.json")
    assert os.path.exists(path), "run `python3 -m great_sdd.conformance.generate` first"
    on_disk = open(path, encoding="utf-8").read()
    version = read_version(REPO_ROOT)
    regenerated = canonical_json(build_endpoint_fixtures(version)["project_lines"])
    assert on_disk == regenerated, "endpoint fixture drift — regenerate"

    fx = json.loads(on_disk)
    assert fx["endpoint"] == "GET /project-lines"
    assert len(fx["cases"]) == 7
    assert len(fx["seed"]) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_endpoint_fixture_is_generated_and_byte_stable -v`
Expected: FAIL with `ImportError: cannot import name 'ENDPOINTS_DIR'`

- [ ] **Step 3: Write minimal implementation**

In `great_sdd/conformance/generate.py`, extend the import block (lines 18-21) to add `generate_endpoint_fixtures`:

```python
from sdd.base_conformance import (
    Probe, TripwireLM, generate_fixtures, write_fixture_file, read_version,
    canonical_json, generate_endpoint_fixtures,
)
```

Add an import for the endpoint module and an `ENDPOINTS_DIR` constant right after the `FIXTURES_DIR` line (currently line 28):

```python
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
ENDPOINTS_DIR = FIXTURES_DIR / "endpoints"

from great_sdd.conformance.endpoints import project_lines as _project_lines_ep
```

Add a builder next to `build_probes` (after the `build_probes` function):

```python
def build_endpoint_fixtures(version: str) -> dict:
    """name -> endpoint fixture dict. One file per endpoint under fixtures/endpoints/."""
    return {
        "project_lines": generate_endpoint_fixtures(
            _project_lines_ep.PROBE, _project_lines_ep.SEED, version),
    }
```

In `_emit`, immediately after the `for view, probes in views.items():` loop (before the `inv = {` block), insert the endpoint emission:

```python
    for name, fixture in build_endpoint_fixtures(version).items():
        ep_path = ENDPOINTS_DIR / f"{name}.json"
        new_ep = canonical_json(fixture)
        if check:
            old_ep = ep_path.read_text() if ep_path.exists() else ""
            if old_ep != new_ep:
                drift.append(f"endpoints/{name}")
        else:
            write_fixture_file(ep_path, fixture)
```

- [ ] **Step 4: Generate the fixture, then run the test**

Run: `python3 -m great_sdd.conformance.generate`
Expected: `wrote fixtures for 6 views @ v2.0.0; 55/92 business rules covered.` and a new file `great_sdd/conformance/fixtures/endpoints/project_lines.json`.

Run: `python3 -m pytest tests/test_conformance.py::test_endpoint_fixture_is_generated_and_byte_stable -v`
Expected: PASS

- [ ] **Step 5: Verify `--check` covers the endpoint (no drift)**

Run: `python3 -m great_sdd.conformance.generate --check`
Expected: exit 0, `checked fixtures for 6 views ...` (no FIXTURE DRIFT).

- [ ] **Step 6: Commit**

```bash
git add great_sdd/conformance/generate.py great_sdd/conformance/fixtures/endpoints/project_lines.json tests/test_conformance.py
git commit -m "feat(conformance): emit GET /project-lines golden fixture; --check covers it"
```

---

### Task 4: Runner — reference endpoint consumer + self-check

**Files:**
- Modify: `great_sdd/conformance/runner.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conformance.py`:

```python
def test_oracle_endpoint_consumer_passes_all_cases():
    from great_sdd.conformance.runner import (
        run_endpoints_against_fixtures, oracle_endpoint_consumer_fn)
    reports = run_endpoints_against_fixtures(oracle_endpoint_consumer_fn)
    assert reports, "no endpoint fixtures found"
    for rep in reports:
        assert rep["passed"], rep["failures"][:2]
    assert any(r["endpoint"] == "GET /project-lines" for r in reports)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_oracle_endpoint_consumer_passes_all_cases -v`
Expected: FAIL with `ImportError: cannot import name 'run_endpoints_against_fixtures'`

- [ ] **Step 3: Write minimal implementation**

In `great_sdd/conformance/runner.py`, extend the imports:

```python
from sdd.base_conformance import run_conformance, normalize_output, read_version, run_endpoint_conformance
from great_sdd.conformance.generate import FIXTURES_DIR, REPO_ROOT, build_probes, ENDPOINTS_DIR
from great_sdd.conformance.endpoints import project_lines as _project_lines_ep
```

Append at the end of `runner.py` (before the `def main` / `if __name__` block — place these functions just above `def main`):

```python
# ── Endpoint conformance ──

_ENDPOINT_ORACLES = {
    "GET /project-lines": _project_lines_ep.list_project_lines,
}


def oracle_endpoint_consumer_fn(req: dict) -> dict:
    """Reference endpoint consumer: re-run the oracle.

    req = {"endpoint", "request", "seed"} — dispatches on endpoint. A real backend
    would instead seed its store from req["seed"] and call its own handler.
    """
    return _ENDPOINT_ORACLES[req["endpoint"]](req["request"])


def load_endpoint_fixtures(endpoints_dir: Path = ENDPOINTS_DIR) -> list:
    return [json.loads(fp.read_text())
            for fp in sorted(Path(endpoints_dir).glob("*.json"))]


def run_endpoints_against_fixtures(consumer_fn, endpoints_dir: Path = ENDPOINTS_DIR) -> list:
    return [run_endpoint_conformance(fx, consumer_fn)
            for fx in load_endpoint_fixtures(endpoints_dir)]
```

Also surface endpoint results in `main` — add these lines right before `return 0 if rep["passed"] else 1`:

```python
    ep_reports = run_endpoints_against_fixtures(oracle_endpoint_consumer_fn)
    for er in ep_reports:
        print(f"Endpoint {er['endpoint']}: {er['total'] - er['failed_count']}/{er['total']} cases passed.")
    ep_ok = all(er["passed"] for er in ep_reports)
    return 0 if (rep["passed"] and ep_ok) else 1
```

(Delete the original `return 0 if rep["passed"] else 1` line so the new block replaces it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_oracle_endpoint_consumer_passes_all_cases -v`
Expected: PASS

Run: `python3 -m great_sdd.conformance.runner`
Expected: rule conformance line + `Endpoint GET /project-lines: 7/7 cases passed.`

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/runner.py tests/test_conformance.py
git commit -m "feat(conformance): endpoint runner + reference oracle consumer"
```

---

### Task 5: Coverage — separate endpoints block

**Files:**
- Modify: `great_sdd/conformance/coverage.py` (in `main`, after the rules report)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conformance.py`:

```python
def test_coverage_lists_endpoints_separately_from_rule_census():
    from great_sdd.conformance.coverage import endpoint_coverage_lines
    lines = endpoint_coverage_lines()
    joined = "\n".join(lines)
    assert "GET /project-lines" in joined
    assert "7" in joined            # 7 cases
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_coverage_lists_endpoints_separately_from_rule_census -v`
Expected: FAIL with `ImportError: cannot import name 'endpoint_coverage_lines'`

- [ ] **Step 3: Write minimal implementation**

In `great_sdd/conformance/coverage.py`, add this function (top-level, after the imports) — it reads endpoint fixtures directly so it never touches the 55/92 rule computation:

```python
def endpoint_coverage_lines() -> list:
    """Human-readable endpoint coverage, SEPARATE from the business-rule census."""
    from great_sdd.conformance.runner import load_endpoint_fixtures
    lines = []
    for fx in load_endpoint_fixtures():
        lines.append(f"Endpoint {fx['endpoint']}: {len(fx['cases'])} cases (mirrored contract)")
    return lines
```

In `coverage.py`'s `main`, print these lines after the existing rule-coverage output (just before `return`):

```python
    for line in endpoint_coverage_lines():
        print(f"  {line}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_coverage_lists_endpoints_separately_from_rule_census -v`
Expected: PASS

Run: `python3 -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70`
Expected: rule coverage line (`55/55 ... PASS`) unchanged, plus `Endpoint GET /project-lines: 7 cases (mirrored contract)`.

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/coverage.py tests/test_conformance.py
git commit -m "feat(conformance): report endpoints separately in coverage gate"
```

---

### Task 6: Document the sub-layer + full verification

**Files:**
- Modify: `great_sdd/conformance/README.md` (append a section)
- Test: full suite

- [ ] **Step 1: Append documentation**

Add to the end of `great_sdd/conformance/README.md`:

```markdown
## Endpoint conformance (mirroring an external API contract)

Beyond per-rule fixtures, the layer can mirror a full **HTTP endpoint contract** as
golden fixtures. Unlike rule fixtures (where the SDD is the oracle), an endpoint
fixture MIRRORS an external contract (OpenAPI + backend DTO + frontend types) — the
external API is the source of truth; the SDD reflects it for a cross-language test.
Endpoint fixtures do NOT enter the business-rule census.

- Oracle: `great_sdd/conformance/endpoints/<name>.py` — a deterministic reference
  (fixed seed, no network/LLM/time) that re-implements the documented behavior.
- Fixture: `fixtures/endpoints/<name>.json` — `{endpoint, sdd_version, seed, cases:[{request, expected:{status, body}}]}`, byte-stable.
- Runner: `run_endpoints_against_fixtures(consumer_fn)` passes `{endpoint, request, seed}`
  (never `expected`) and exact-matches `{status, body}`.

Implemented: `GET /project-lines` (mirrors `cap_horse_great` pev-openapi + `list_lines`).
The frontend loads the same JSON as its mock + contract test; the backend can seed
`fixture.seed` and run its handler against each `request`.
```

- [ ] **Step 2: Full verification — generate, check, run, coverage, suite**

Run each and confirm:

```bash
python3 -m great_sdd.conformance.generate --check     # exit 0, no drift (rules + endpoints)
python3 -m great_sdd.conformance.runner                # rules pass + "Endpoint GET /project-lines: 7/7 cases passed."
python3 -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70   # 55/55 PASS + endpoint line
python3 -m pytest tests/ -q                            # whole suite green
```

Expected: all green; `pytest tests/` shows the prior count plus the new endpoint tests, 0 failures.

- [ ] **Step 3: Byte-stability double-check**

```bash
python3 -m great_sdd.conformance.generate && python3 -m great_sdd.conformance.generate
git diff --stat -- great_sdd/conformance/fixtures/endpoints/
```

Expected: empty diff (regenerating twice produces identical bytes).

- [ ] **Step 4: Commit**

```bash
git add great_sdd/conformance/README.md
git commit -m "docs(conformance): document endpoint-conformance sub-layer"
```

---

## Self-Review

**Spec coverage:**
- Mirror external contract → Task 2 oracle uses the contract's enums/fields verbatim; README (Task 6) states external is the source of truth. ✓
- Full behavior (role scoping, filters, 401/403/404, filterOptions) → Task 2 oracle + tests cover all 7 cases. ✓
- Conformance-only, no census change → Task 5 reads endpoint fixtures separately; no rule_ids added. ✓
- Seed determinism (fixed UUIDs/OIDs) → Task 2 SEED. ✓
- New fixture format `{seed, cases}` → Task 1 `generate_endpoint_fixtures`. ✓
- Cross-language consumption → Task 4 runner passes `{endpoint, request, seed}`, never `expected`; README documents FE/BE use. ✓
- Tripwire/byte-stability → engine reuses `canonical_json`; Task 3 Step 5 + Task 6 Step 3 verify. ✓ (Oracle is pure filter/projection, so no LM injection is needed; if a future endpoint oracle calls a module, construct it with `TripwireLM`.)
- 24-field contract parity → Task 2 `PROJECT_LINE_FIELDS` + test asserting `set(row) == set(PROJECT_LINE_FIELDS)`. ✓
- Métier divergence documented → Task 2 module docstring + comment; test asserts no `H-TESTING`. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. The empty-loop `for code in (403,404,401): pass` in the status test is intentional (kept minimal) — bodies asserted explicitly after.

**Type consistency:** `EndpointProbe(endpoint, name, fn, cases)`, `generate_endpoint_fixtures(probe, seed, version)`, `run_endpoint_conformance(fixture, consumer_fn)`, `list_project_lines(request)->{status,body}`, `PROJECT_LINE_FIELDS`, `build_endpoint_fixtures(version)`, `ENDPOINTS_DIR`, `oracle_endpoint_consumer_fn`, `run_endpoints_against_fixtures`, `endpoint_coverage_lines` — names used consistently across Tasks 1-6. ✓
