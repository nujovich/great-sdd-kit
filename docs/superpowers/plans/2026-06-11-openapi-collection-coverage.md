# Full-API Collection Coverage from Vendored OpenAPI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate Bruno + Postman collections + `examples.json` covering ALL 43 OpenAPI operations, grouped into 6 view folders, with synthesized examples for every response code (incl. 4xx) — merging in the richer per-scenario examples for any endpoint that has a conformance oracle.

**Architecture:** Vendor the external `pev-openapi.yaml` as a committed JSON snapshot. A new `openapi.py` loads it, resolves `$ref`s, synthesizes deterministic examples from JSON Schema, and iterates operations into a unified per-endpoint descriptor. `collection.py` merges openapi descriptors with oracle-fixture descriptors (fixture wins) and the Postman/Bruno/examples builders consume that unified shape, grouping by the 6 SDD views.

**Tech Stack:** Python 3.11+ (run with `python3`; modules use `from __future__ import annotations`). stdlib only at runtime (`json`, `re`, `argparse`, `zipfile`, `io`, `pathlib`). PyYAML used ONLY by the dev refresh script. pytest. Reuses `sdd.base_conformance.canonical_json`.

**Spec:** `docs/superpowers/specs/2026-06-11-openapi-collection-coverage-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/refresh_openapi_snapshot.py` (create) | dev-only yaml→json converter (PyYAML) |
| `great_sdd/conformance/contracts/pev-openapi.json` (generated, committed) | pinned snapshot of the external contract |
| `great_sdd/conformance/contracts/REFRESH.md` (create) | how to refresh the snapshot |
| `great_sdd/conformance/openapi.py` (create) | loader + `deref` + `synthesize_example` + `iter_operations` + `TAG_TO_VIEW` |
| `great_sdd/conformance/collection.py` (modify) | unified descriptors, openapi⊕fixture merge, builders consume descriptors + 6 view folders |
| `great_sdd/conformance/fixtures/endpoints/collections/*` (regenerated, committed) | full-API collection (43 ops, 6 folders) |
| `tests/test_conformance.py` (modify) | tests for loader/synth/iter/merge/folders/4xx |
| `great_sdd/conformance/README.md` (modify) | document full-API coverage + refresh |

---

### Task 1: Vendor the OpenAPI snapshot + refresh script

**Files:**
- Create: `scripts/refresh_openapi_snapshot.py`
- Create: `great_sdd/conformance/contracts/REFRESH.md`
- Generate: `great_sdd/conformance/contracts/pev-openapi.json`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
# ═══════════════════════════════════════════════════════════
# openapi collection coverage — vendored snapshot
# ═══════════════════════════════════════════════════════════
def test_openapi_snapshot_is_vendored_and_complete():
    import json as _json
    path = os.path.join(os.path.dirname(__file__), "..",
                        "great_sdd", "conformance", "contracts", "pev-openapi.json")
    assert os.path.exists(path), "run scripts/refresh_openapi_snapshot.py"
    spec = _json.loads(open(path, encoding="utf-8").read())
    assert spec["openapi"].startswith("3.")
    # 43 operations across the paths
    ops = sum(1 for methods in spec["paths"].values()
              for m in methods if m in ("get", "post", "put", "patch", "delete"))
    assert ops == 43
    assert len(spec["components"]["schemas"]) == 71
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_openapi_snapshot_is_vendored_and_complete -v`
Expected: FAIL (`run scripts/refresh_openapi_snapshot.py` assertion — file missing)

- [ ] **Step 3: Create the refresh script** `scripts/refresh_openapi_snapshot.py`:

```python
"""Dev-only: convert the external pev-openapi.yaml to a committed JSON snapshot.

PyYAML is a DEV dependency used here only; the runtime collection generator reads
the committed JSON with stdlib json. Re-run when the external contract changes.

    python3 scripts/refresh_openapi_snapshot.py [path/to/pev-openapi.yaml]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml  # dev-only

DEFAULT_SRC = Path("/home/nujovich/cap_horse_great/docs/open-api/pev-openapi.yaml")
DEST = Path(__file__).resolve().parents[1] / \
    "great_sdd/conformance/contracts/pev-openapi.json"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    src = Path(argv[0]) if argv else DEFAULT_SRC
    if not src.exists():
        print(f"source openapi not found: {src}", file=sys.stderr)
        return 1
    spec = yaml.safe_load(src.read_text())
    DEST.parent.mkdir(parents=True, exist_ok=True)
    # byte-stable: sorted keys, 2-space indent, trailing newline
    DEST.write_text(json.dumps(spec, sort_keys=True, indent=2,
                               ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote snapshot -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the snapshot**

Run: `python3 scripts/refresh_openapi_snapshot.py`
Expected: `wrote snapshot -> .../great_sdd/conformance/contracts/pev-openapi.json` and the file exists.

- [ ] **Step 5: Create `great_sdd/conformance/contracts/REFRESH.md`:**

```markdown
# OpenAPI snapshot

`pev-openapi.json` is a **pinned JSON snapshot** of the external GREAT contract
(`cap_horse_great/docs/open-api/pev-openapi.yaml`). The collection generator reads
this committed snapshot with stdlib `json` (no YAML dependency at runtime).

Refresh it when the external contract changes:

```bash
python3 scripts/refresh_openapi_snapshot.py [path/to/pev-openapi.yaml]
python3 -m great_sdd.conformance.collection generate   # regenerate collections
```

The snapshot is byte-stable (sorted keys, indent 2). PyYAML is required only to run
the refresh script, not by the runtime generator.
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_openapi_snapshot_is_vendored_and_complete -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/refresh_openapi_snapshot.py great_sdd/conformance/contracts/ tests/test_conformance.py
git commit -m "feat(conformance): vendor pev-openapi.json snapshot + dev refresh script"
```

---

### Task 2: `openapi.py` — loader + `$ref` resolver

**Files:**
- Create: `great_sdd/conformance/openapi.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_openapi_load_and_deref():
    from great_sdd.conformance.openapi import load_openapi, deref
    spec = load_openapi()
    assert "paths" in spec and "components" in spec
    # deref a schema ref
    s = deref(spec, {"$ref": "#/components/schemas/ProjectLinesResponse"})
    assert s["type"] == "object" and "data" in s["properties"]
    # deref a response ref (components/responses)
    r = deref(spec, {"$ref": "#/components/responses/Unauthorized"})
    assert "content" in r
    # non-ref passes through unchanged
    assert deref(spec, {"type": "string"}) == {"type": "string"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_openapi_load_and_deref -v`
Expected: FAIL `ModuleNotFoundError: No module named 'great_sdd.conformance.openapi'`

- [ ] **Step 3: Write minimal implementation** — create `great_sdd/conformance/openapi.py`:

```python
"""Read the vendored OpenAPI snapshot and turn it into collection descriptors.

Pure, stdlib-only, deterministic. The snapshot (contracts/pev-openapi.json) is a
pinned mirror of the external GREAT contract; this module never touches the network
or YAML. It resolves $refs, synthesizes example values from JSON Schema, and
iterates operations grouped into the 6 SDD views.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

OPENAPI_PATH = Path(__file__).resolve().parent / "contracts" / "pev-openapi.json"

# openapi tag -> SDD view (collection folder). Unknown tags fall to "Other".
TAG_TO_VIEW = {
    "ProjectLines": "Pre-Estimation",
    "Estimation": "Pre-Estimation",
    "Prototype": "Pre-Estimation",
    "EstimationReview": "Estimation Review",
    "HVT": "Estimation Review",
    "Allocation": "Allocation",
    "AllocationConfig": "Allocation",
    "FinalReview": "Final Review",
    "ManagementView": "Management View",
    "Transversal": "Transversal",
}
# Fixed display order of the 6 view folders.
VIEW_ORDER = ["Pre-Estimation", "Estimation Review", "Allocation",
              "Final Review", "Management View", "Transversal", "Other"]


def load_openapi() -> dict:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


def deref(spec: dict, node):
    """Resolve a one-level {$ref: '#/components/<kind>/<name>'} against the spec.

    Non-ref nodes pass through unchanged. Nested $refs inside the resolved node are
    left for the caller (synthesize_example resolves them recursively).
    """
    if isinstance(node, dict) and "$ref" in node:
        parts = node["$ref"].lstrip("#/").split("/")   # ['components','schemas','X']
        target = spec
        for p in parts:
            target = target[p]
        return target
    return node
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_openapi_load_and_deref -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/openapi.py tests/test_conformance.py
git commit -m "feat(conformance): openapi snapshot loader + \$ref resolver"
```

---

### Task 3: `openapi.py` — `synthesize_example`

**Files:**
- Modify: `great_sdd/conformance/openapi.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_synthesize_example_covers_schema_shapes():
    from great_sdd.conformance.openapi import synthesize_example, load_openapi
    spec = load_openapi()
    # object: only required props
    obj = {"type": "object", "required": ["a"],
           "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
    assert synthesize_example(obj, spec) == {"a": "string"}
    # array of 1
    assert synthesize_example({"type": "array", "items": {"type": "integer"}}, spec) == [0]
    # enum -> first
    assert synthesize_example({"type": "string", "enum": ["X", "Y"]}, spec) == "X"
    # formats
    assert synthesize_example({"type": "string", "format": "uuid"}, spec) \
        == "00000000-0000-4000-8000-000000000000"
    assert synthesize_example({"type": "string", "format": "date"}, spec) == "2026-01-01"
    # nullable union -> typed value, not null
    assert synthesize_example({"type": ["string", "null"]}, spec) == "string"
    # $ref resolves recursively (ProjectLinesResponse -> object with data/filterOptions)
    out = synthesize_example({"$ref": "#/components/schemas/ProjectLinesResponse"}, spec)
    assert set(out) >= {"data", "filterOptions"}
    # cycle-safe: a self-referential schema terminates
    cyc = {"type": "object", "required": ["self"],
           "properties": {"self": {"$ref": "#/components/schemas/__cyc"}}}
    spec2 = dict(spec); spec2["components"] = dict(spec["components"])
    spec2["components"]["schemas"] = dict(spec["components"]["schemas"], __cyc=cyc)
    res = synthesize_example({"$ref": "#/components/schemas/__cyc"}, spec2)
    assert res == {"self": None}      # cycle cut to None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_synthesize_example_covers_schema_shapes -v`
Expected: FAIL `ImportError: cannot import name 'synthesize_example'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/openapi.py`:

```python
_FORMAT_SAMPLES = {
    "uuid": "00000000-0000-4000-8000-000000000000",
    "date": "2026-01-01",
    "date-time": "2026-01-01T00:00:00Z",
}


def _types(schema: dict) -> list:
    """Normalize `type` to a list (handles nullable unions like ['string','null'])."""
    t = schema.get("type")
    if isinstance(t, list):
        return [x for x in t if x != "null"]
    return [t] if t else []


def synthesize_example(schema, spec: dict, _seen: tuple = ()):
    """Deterministic sample JSON value for a JSON Schema node. Cycle-safe via _seen."""
    if isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        if ref in _seen:
            return None                       # cut cycles
        return synthesize_example(deref(spec, schema), spec, _seen + (ref,))
    if not isinstance(schema, dict):
        return None
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    types = _types(schema)
    t = types[0] if types else ("object" if "properties" in schema else None)
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = schema.get("required", list(props))
        return {k: synthesize_example(props[k], spec, _seen)
                for k in props if k in required}
    if t == "array":
        return [synthesize_example(schema.get("items", {}), spec, _seen)]
    if t == "string":
        return _FORMAT_SAMPLES.get(schema.get("format"), "string")
    if t == "integer":
        return 0
    if t == "number":
        return 0
    if t == "boolean":
        return False
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_synthesize_example_covers_schema_shapes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/openapi.py tests/test_conformance.py
git commit -m "feat(conformance): deterministic JSON-Schema example synthesizer"
```

---

### Task 4: `openapi.py` — `iter_operations` + view grouping

**Files:**
- Modify: `great_sdd/conformance/openapi.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_iter_operations_maps_views_and_schemas():
    from great_sdd.conformance.openapi import iter_operations, load_openapi
    ops = iter_operations(load_openapi())
    assert len(ops) == 43
    names = {o["name"] for o in ops}
    assert "GET /project-lines" in names
    assert "PUT /project-lines/{id}/allocation" in names
    # views assigned from TAG_TO_VIEW
    pl = next(o for o in ops if o["name"] == "GET /project-lines")
    assert pl["view"] == "Pre-Estimation"
    alloc = next(o for o in ops if o["name"] == "PUT /project-lines/{id}/allocation")
    assert alloc["view"] == "Allocation"
    assert alloc["path_params"] == ["id"]
    assert alloc["request_schema"] is not None        # mutation has a body schema
    assert alloc["method"] == "PUT"
    # every op exposes at least one response code
    assert all(o["response_schemas"] for o in ops)
    # a GET with query params surfaces them
    plq = pl["query_params"]
    assert "assignee" in plq and "metier" in plq
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_iter_operations_maps_views_and_schemas -v`
Expected: FAIL `ImportError: cannot import name 'iter_operations'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/openapi.py`:

```python
_METHODS = ("get", "post", "put", "patch", "delete")


def _json_schema(spec: dict, holder) -> dict:
    """Extract the application/json schema from a requestBody/response holder (deref'd)."""
    holder = deref(spec, holder)
    if not isinstance(holder, dict):
        return None
    media = (holder.get("content") or {}).get("application/json") or {}
    return media.get("schema")


def _query_params(spec: dict, op: dict) -> list:
    out = []
    for p in op.get("parameters", []):
        p = deref(spec, p)
        if p.get("in") == "query":
            out.append(p["name"])
    return out


def iter_operations(spec: dict) -> list:
    """One unified op descriptor per HTTP operation, sorted by (view, path, method)."""
    ops = []
    for path, methods in spec.get("paths", {}).items():
        path_params = re.findall(r"\{(\w+)\}", path)
        for method, op in methods.items():
            if method not in _METHODS:
                continue
            tag = (op.get("tags") or ["Other"])[0]
            view = TAG_TO_VIEW.get(tag, "Other")
            req_schema = _json_schema(spec, op.get("requestBody")) \
                if op.get("requestBody") else None
            resp_schemas = {}
            for code, resp in (op.get("responses") or {}).items():
                resp_schemas[code] = _json_schema(spec, resp)   # may be None (e.g. 204)
            ops.append({
                "name": f"{method.upper()} {path}",
                "tag": tag,
                "view": view,
                "method": method.upper(),
                "path": path,
                "path_params": path_params,
                "query_params": _query_params(spec, op),
                "auth": "bearer",
                "request_schema": req_schema,
                "response_schemas": resp_schemas,
            })
    ops.sort(key=lambda o: (VIEW_ORDER.index(o["view"]), o["path"], o["method"]))
    return ops
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_iter_operations_maps_views_and_schemas -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/openapi.py tests/test_conformance.py
git commit -m "feat(conformance): iter_operations with view grouping + schema extraction"
```

---

### Task 5: Unified descriptors + openapi⊕fixture merge

**Files:**
- Modify: `great_sdd/conformance/collection.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_unified_descriptors_merge_openapi_and_fixtures():
    from great_sdd.conformance.collection import unified_descriptors
    descs = unified_descriptors()
    by_name = {d["name"]: d for d in descs}
    assert len(descs) == 43                       # all ops, deduped by name
    # project-lines GET comes from the FIXTURE oracle (rich scenarios incl 4xx)
    pl = by_name["GET /project-lines"]
    assert pl["source"] == "fixture"
    statuses = sorted({e["status"] for e in pl["examples"]})
    assert statuses == [200, 401, 403, 404]
    # a mutation comes from openapi with a synthesized body + per-code examples
    alloc = by_name["PUT /project-lines/{id}/allocation"]
    assert alloc["source"] == "openapi"
    assert alloc["request_body_example"] is not None
    assert any(e["status"] >= 400 for e in alloc["examples"])   # 4xx present
    assert alloc["view"] == "Allocation"
    # every descriptor carries the unified keys
    for d in descs:
        assert {"name", "view", "method", "path", "path_params", "query_params",
                "auth", "request_schema", "request_body_example", "response_schema",
                "examples", "source"} <= set(d)
        for e in d["examples"]:
            assert {"scenario", "status", "body", "authenticated", "query"} <= set(e)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_unified_descriptors_merge_openapi_and_fixtures -v`
Expected: FAIL `ImportError: cannot import name 'unified_descriptors'`

- [ ] **Step 3: Write minimal implementation** — add to `great_sdd/conformance/collection.py`.

First extend the imports near the top (after the existing `from great_sdd.conformance.endpoints import project_lines as _project_lines_ep`):

```python
from great_sdd.conformance import openapi as _openapi
```

Then append these functions (after `load_endpoints`):

```python
def _first_success(response_schemas: dict):
    """Schema of the first 2xx response code present (200/201/204...)."""
    for code in sorted(response_schemas):
        if code.startswith("2"):
            return response_schemas[code]
    return None


def _descriptors_from_openapi() -> dict:
    """name -> unified descriptor for every OpenAPI operation (synthesized examples)."""
    spec = _openapi.load_openapi()
    out = {}
    for op in _openapi.iter_operations(spec):
        examples = []
        for code in sorted(op["response_schemas"]):
            schema = op["response_schemas"][code]
            body = _openapi.synthesize_example(schema, spec) if schema else None
            examples.append({"scenario": code, "status": int(code),
                             "body": body, "authenticated": True, "query": {}})
        req_schema = op["request_schema"]
        out[op["name"]] = {
            "name": op["name"], "view": op["view"], "method": op["method"],
            "path": op["path"], "path_params": op["path_params"],
            "query_params": op["query_params"], "auth": op["auth"],
            "request_schema": req_schema,
            "request_body_example": (_openapi.synthesize_example(req_schema, spec)
                                     if req_schema else None),
            "response_schema": _first_success(op["response_schemas"]),
            "examples": examples, "source": "openapi",
        }
    return out


def _descriptors_from_fixtures() -> dict:
    """name -> unified descriptor for endpoints that have a conformance oracle fixture."""
    out = {}
    for ep in load_endpoints():
        binding = ep["module"].HTTP_BINDING
        method, path = ep["name"].split(" ", 1)
        examples = []
        for case in ep["fixture"]["cases"]:
            req = case["request"]
            examples.append({
                "scenario": _scenario_label(req, case["expected"]["status"]),
                "status": case["expected"]["status"],
                "body": case["expected"]["body"],
                "authenticated": req.get("role") is not None,
                "query": req.get("query") or {},
            })
        out[ep["name"]] = {
            "name": ep["name"],
            "view": _openapi.TAG_TO_VIEW.get("ProjectLines", "Other"),
            "method": method, "path": path,
            "path_params": [], "query_params": binding.get("query_params", []),
            "auth": binding.get("auth", "bearer"),
            "request_schema": ep["module"].REQUEST_SCHEMA,
            "request_body_example": None,
            "response_schema": ep["module"].RESPONSE_SCHEMA,
            "examples": examples, "source": "fixture",
        }
    return out


def unified_descriptors() -> list:
    """All endpoints as unified descriptors; fixture oracles override OpenAPI by name."""
    merged = _descriptors_from_openapi()
    merged.update(_descriptors_from_fixtures())     # fixture wins
    from great_sdd.conformance.openapi import VIEW_ORDER
    return sorted(merged.values(),
                  key=lambda d: (VIEW_ORDER.index(d["view"]), d["path"], d["method"]))
```

NOTE: `_descriptors_from_fixtures` currently maps every fixture endpoint's view via the `ProjectLines` tag. That is correct while project-lines is the only oracle; when sub-project 2 adds oracles for other views, give each oracle module a `VIEW` attribute and read it here. Leave a `# TODO(sub-project-2): read ep.module.VIEW` comment at that line.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_unified_descriptors_merge_openapi_and_fixtures -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): unified endpoint descriptors merging openapi + fixtures"
```

---

### Task 6: Postman builder → unified descriptors + 6 view folders

**Files:**
- Modify: `great_sdd/conformance/collection.py` (rewrite `build_postman`, adapt `_pm_url`/`_pm_headers` callers)
- Test: `tests/test_conformance.py` (replace `test_build_postman_collection_v21_shape` and `test_postman_examples_reflect_scenario_auth_and_query`)

- [ ] **Step 1: Replace the two existing Postman tests** in `tests/test_conformance.py` with:

```python
def test_build_postman_has_six_view_folders_and_all_ops():
    from great_sdd.conformance.collection import build_postman, unified_descriptors
    coll = build_postman(unified_descriptors())
    assert coll["info"]["schema"] == \
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    folders = coll["item"]
    assert [f["name"] for f in folders] == [
        "Pre-Estimation", "Estimation Review", "Allocation",
        "Final Review", "Management View", "Transversal"]
    total = sum(len(f["item"]) for f in folders)
    assert total == 43
    # find a mutation request inside the Allocation folder
    alloc = next(f for f in folders if f["name"] == "Allocation")
    put = next(r for r in alloc["item"] if r["name"] == "PUT /project-lines/{id}/allocation")
    assert put["request"]["method"] == "PUT"
    assert put["request"]["body"]["mode"] == "raw" and put["request"]["body"]["raw"].strip()
    assert "Request schema" in put["request"]["description"]
    # path param rendered as :id in the url
    assert ":id" in put["request"]["url"]["raw"]
    # a 4xx example is saved
    assert any(r["code"] >= 400 for r in put["response"])


def test_build_postman_project_lines_uses_fixture_examples():
    from great_sdd.conformance.collection import build_postman, unified_descriptors
    coll = build_postman(unified_descriptors())
    pe = next(f for f in coll["item"] if f["name"] == "Pre-Estimation")
    item = next(r for r in pe["item"] if r["name"] == "GET /project-lines")
    # the 401 example carries no auth header (rich fixture scenario, not synthesized)
    ex401 = next(r for r in item["response"] if r["code"] == 401)
    assert all(h["key"] != "Authorization" for h in ex401["originalRequest"]["header"])
```

(Delete the old `test_build_postman_collection_v21_shape` and `test_postman_examples_reflect_scenario_auth_and_query`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_conformance.py -k build_postman -v`
Expected: FAIL (`build_postman` still expects the old fixture-endpoint list; assertions about folders fail or it errors).

- [ ] **Step 3: Rewrite `build_postman`** in `great_sdd/conformance/collection.py`. Replace the existing `build_postman` function (and keep `_pm_url`/`_pm_headers`/`_markdown_docs` — but `_pm_url` is now called with a descriptor's `path`/`query_params`). First, update `_pm_url` to render path params as `:param`:

Replace `_pm_url` with:

```python
def _pm_url(desc: dict, query: dict = None, template: bool = False) -> dict:
    """Postman url object from a descriptor: {{baseUrl}} + path (with :params) + query."""
    query = query or {}
    qp = desc.get("query_params", [])
    if template:
        qitems = [{"key": k, "value": "", "disabled": True} for k in qp]
    else:
        qitems = [{"key": k, "value": str(query[k])}
                  for k in qp if query.get(k) is not None]
    sent = [q for q in qitems if not q.get("disabled")]
    # path params {id} -> :id (Postman path-variable syntax)
    path = re.sub(r"\{(\w+)\}", r":\1", desc["path"])
    raw = "{{baseUrl}}" + path
    if sent:
        raw += "?" + "&".join(f"{q['key']}={q['value']}" for q in sent)
    url = {"raw": raw, "host": ["{{baseUrl}}"],
           "path": [seg for seg in path.split("/") if seg], "query": qitems}
    if desc.get("path_params"):
        url["variable"] = [{"key": p, "value": ""} for p in desc["path_params"]]
    return url
```

Add `import re` to the top of `collection.py` if not already imported.

Now replace `build_postman` with:

```python
def _pm_request(desc: dict) -> dict:
    """The saved (template) request object for an endpoint descriptor."""
    req = {
        "method": desc["method"],
        "header": _pm_headers(desc),
        "url": _pm_url(desc, template=True),
        "description": _markdown_docs_desc(desc),
    }
    if desc.get("request_body_example") is not None:
        req["body"] = {"mode": "raw",
                       "raw": canonical_json(desc["request_body_example"]).rstrip(),
                       "options": {"raw": {"language": "json"}}}
    return req


def _pm_examples(desc: dict) -> list:
    out = []
    for e in desc["examples"]:
        has_body = e["body"] is not None
        out.append({
            "name": e["scenario"],
            "originalRequest": {
                "method": desc["method"],
                "header": _pm_headers(desc, authenticated=e.get("authenticated", True)),
                "url": _pm_url(desc, e.get("query") or {}),
            },
            "status": _PM_STATUS_TEXT.get(e["status"], ""),
            "code": e["status"],
            "_postman_previewlanguage": "json" if has_body else "text",
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": canonical_json(e["body"]).rstrip() if has_body else "",
        })
    return out


def build_postman(descriptors: list) -> dict:
    """Postman Collection v2.1 with one folder per SDD view (in VIEW_ORDER)."""
    from great_sdd.conformance.openapi import VIEW_ORDER
    by_view = {}
    for d in descriptors:
        by_view.setdefault(d["view"], []).append({
            "name": d["name"], "request": _pm_request(d), "response": _pm_examples(d)})
    folders = [{"name": v, "item": by_view[v]}
               for v in VIEW_ORDER if by_view.get(v)]
    return {
        "info": {
            "name": "GREAT API — conformance collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Generated from the vendored OpenAPI snapshot + conformance "
                           "fixtures. Set {{baseUrl}} and {{token}} before sending.",
        },
        "variable": [
            {"key": "baseUrl", "value": "/api/v1"},
            {"key": "token", "value": "<JWT>"},
        ],
        "item": folders,
    }
```

`_PM_STATUS_TEXT` already exists from the prior feature; extend it to cover the new codes. Replace its definition with:

```python
_PM_STATUS_TEXT = {200: "OK", 201: "Created", 204: "No Content", 400: "Bad Request",
                   401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
                   409: "Conflict", 502: "Bad Gateway"}
```

Add a descriptor-aware docs helper next to `_markdown_docs` (keep the old one if still referenced elsewhere; otherwise this replaces its use):

```python
def _markdown_docs_desc(desc: dict) -> str:
    """Markdown request description from a descriptor: request + response schema."""
    parts = [f"`{desc['method']} {{{{baseUrl}}}}{desc['path']}`\n", "Auth: Bearer `{{token}}`.\n"]
    if desc.get("request_schema") is not None:
        parts.append("## Request schema\n\n```json\n"
                     + canonical_json(desc["request_schema"]).rstrip() + "\n```\n")
    if desc.get("response_schema") is not None:
        parts.append("## Response schema\n\n```json\n"
                     + canonical_json(desc["response_schema"]).rstrip() + "\n```\n")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_conformance.py -k build_postman -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): Postman builder consumes unified descriptors, 6 view folders"
```

---

### Task 7: Bruno builder → view subfolders

**Files:**
- Modify: `great_sdd/conformance/collection.py` (rewrite `build_bruno`, `_bru_file`)
- Test: `tests/test_conformance.py` (replace `test_build_bruno_files`)

- [ ] **Step 1: Replace `test_build_bruno_files`** with:

```python
def test_build_bruno_view_subfolders():
    from great_sdd.conformance.collection import build_bruno, unified_descriptors
    files = build_bruno(unified_descriptors())
    assert "bruno.json" in files
    bru_paths = [k for k in files if k.endswith(".bru")]
    assert len(bru_paths) == 43
    # files live under view subfolders, e.g. bruno/Allocation/...
    assert any(k.startswith("Allocation/") for k in bru_paths)
    assert any(k.startswith("Pre-Estimation/") for k in bru_paths)
    # a mutation .bru has a json body block + docs, no bare } inside docs
    alloc = next(files[k] for k in bru_paths
                 if k.startswith("Allocation/") and "allocation" in k and "put" in k.lower())
    assert "body:json {" in alloc and "docs {" in alloc
    lines = alloc.split("\n")
    di = next(i for i, l in enumerate(lines) if l.startswith("docs {"))
    close = max(i for i, l in enumerate(lines) if l == "}")
    for l in lines[di + 1:close]:
        assert l != "}", f"bare }} closes Bruno docs early: {l!r}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_build_bruno_view_subfolders -v`
Expected: FAIL (old `build_bruno` returns flat slugs, no view subfolders / wrong count)

- [ ] **Step 3: Rewrite `_bru_file` and `build_bruno`** in `great_sdd/conformance/collection.py`. Replace both with:

```python
def _bru_slug(name: str) -> str:
    """Slug from an op name, e.g. 'PUT /project-lines/{id}/allocation' -> 'put_project-lines_id_allocation'."""
    method, path = name.split(" ", 1)
    body = re.sub(r"[{}]", "", path).strip("/").replace("/", "_")
    return f"{method.lower()}_{body}" or "endpoint"


def _bru_file(desc: dict, seq: int) -> str:
    """Native Bruno .bru content for one endpoint descriptor."""
    method = desc["method"].lower()
    path = re.sub(r"\{(\w+)\}", r":\1", desc["path"])
    url = "{{baseUrl}}" + path
    query_block = ""
    if desc.get("query_params"):
        lines = "\n".join(f"  {k}: " for k in desc["query_params"])
        query_block = f"\nparams:query {{\n{lines}\n}}\n"
    body_block = ""
    if desc.get("request_body_example") is not None:
        raw = _indent_docs(canonical_json(desc["request_body_example"]).rstrip())
        body_block = f"\nbody:json {{\n{raw}\n}}\n"
    scenarios = "\n".join(
        f"- {e['scenario']} -> {e['status']}" for e in desc["examples"])
    docs = (f"{desc['name']}\n\n## Scenarios\n{scenarios}\n\n"
            + _markdown_docs_desc(desc))
    return (
        f"meta {{\n  name: {desc['name']}\n  type: http\n  seq: {seq}\n}}\n\n"
        f"{method} {{\n  url: {url}\n  body: {'json' if body_block else 'none'}\n  auth: bearer\n}}\n"
        f"{query_block}{body_block}\n"
        f"headers {{\n  Authorization: Bearer {{{{token}}}}\n}}\n\n"
        f"auth:bearer {{\n  token: {{{{token}}}}\n}}\n\n"
        f"docs {{\n{_indent_docs(docs)}\n}}\n"
    )


def build_bruno(descriptors: list) -> dict:
    """Relative path -> content for a native Bruno collection, view subfolders."""
    files = {
        "bruno.json": canonical_json({
            "version": "1", "name": "GREAT API — conformance collection",
            "type": "collection",
        }).rstrip() + "\n",
    }
    for seq, d in enumerate(descriptors, start=1):
        files[f"{d['view']}/{_bru_slug(d['name'])}.bru"] = _bru_file(d, seq)
    return files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_build_bruno_view_subfolders -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): Bruno builder with view subfolders + request bodies"
```

---

### Task 8: examples.json (all codes) + regenerate committed artifacts

**Files:**
- Modify: `great_sdd/conformance/collection.py` (rewrite `build_examples`; `_artifact_blobs`/`write_collections`/CLI unchanged but now fed `unified_descriptors()`)
- Test: `tests/test_conformance.py` (replace `test_build_examples_has_all_cases_per_endpoint` and adapt `test_collection_generate_writes_and_is_byte_stable`)

- [ ] **Step 1: Replace `build_examples` usage.** The artifact builders currently call `build_postman(endpoints)` etc. with fixture `endpoints`. Update `_artifact_blobs` to use `unified_descriptors()`. Replace `_artifact_blobs` with:

```python
def _artifact_blobs(descriptors: list = None) -> dict:
    """Relative path -> content (str) for ALL collection artifacts."""
    descriptors = unified_descriptors() if descriptors is None else descriptors
    blobs = {
        "postman_collection.json": canonical_json(build_postman(descriptors)),
        "examples.json": canonical_json(build_examples(descriptors)),
    }
    for rel, content in build_bruno(descriptors).items():
        blobs[f"bruno/{rel}"] = content
    return blobs
```

And update `write_collections`/`check_collections` to call `_artifact_blobs()` with no args (they already do; confirm they pass no `endpoints`). If `_cmd_generate`/`_cmd_export` pass `load_endpoints(...)`, change them to call `_artifact_blobs()` / `build_zip_bytes()` with no descriptor arg so they use `unified_descriptors()`. Specifically, `build_zip_bytes` and `write_collections`/`check_collections` should no longer take an `endpoints` parameter — make them parameterless (internally `_artifact_blobs()`), and `_cmd_generate`/`_cmd_export` drop the `load_endpoints(...)` call:

```python
def write_collections(out_dir: Path) -> list:
    out_dir = Path(out_dir)
    written = []
    for rel, content in _artifact_blobs().items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return sorted(written)


def check_collections(out_dir: Path) -> list:
    out_dir = Path(out_dir)
    drift = []
    for rel, content in _artifact_blobs().items():
        path = out_dir / rel
        on_disk = path.read_text(encoding="utf-8") if path.exists() else ""
        if on_disk != content:
            drift.append(rel)
    return sorted(drift)


def build_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, content in sorted(_artifact_blobs().items()):
            info = zipfile.ZipInfo(filename=rel, date_time=_ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content.encode("utf-8"))
    return buf.getvalue()
```

Update `_cmd_generate` to use `write_collections(out_dir)` / `check_collections(out_dir)` (drop the `--fixtures-dir`/endpoints arg to these; keep `--fixtures-dir` on the parser but it now only affects the oracle fixtures via `load_endpoints` inside `_descriptors_from_fixtures` — for simplicity in this sub-project, `--fixtures-dir` is no longer wired into descriptor building; remove the `--fixtures-dir` option from both subparsers to avoid a dead flag). Update `_cmd_export` to `out.write_bytes(build_zip_bytes())`.

- [ ] **Step 2: Rewrite `build_examples`** — replace with:

```python
def build_examples(descriptors: list) -> dict:
    """name -> {view, examples:[{scenario, status, body}]} for every response code."""
    out = {}
    for d in descriptors:
        out[d["name"]] = {
            "view": d["view"],
            "examples": [{"scenario": e["scenario"], "status": e["status"],
                          "body": e["body"]} for e in d["examples"]],
        }
    return out
```

- [ ] **Step 3: Replace the examples + generate tests** in `tests/test_conformance.py`. Replace `test_build_examples_has_all_cases_per_endpoint` and `test_collection_generate_writes_and_is_byte_stable` and `test_collection_export_zip_is_deterministic` with:

```python
def test_build_examples_covers_all_endpoints_and_codes():
    from great_sdd.conformance.collection import build_examples, unified_descriptors
    ex = build_examples(unified_descriptors())
    assert len(ex) == 43
    # project-lines keeps its 4 scenario examples
    assert {e["status"] for e in ex["GET /project-lines"]["examples"]} == {200, 401, 403, 404}
    # a mutation exposes 4xx examples
    alloc = ex["PUT /project-lines/{id}/allocation"]
    assert alloc["view"] == "Allocation"
    assert any(e["status"] >= 400 for e in alloc["examples"])


def test_collection_generate_writes_and_is_byte_stable():
    from great_sdd.conformance.collection import write_collections, DEFAULT_OUT
    write_collections(DEFAULT_OUT)
    base = str(DEFAULT_OUT)
    pm = os.path.join(base, "postman_collection.json")
    ex = os.path.join(base, "examples.json")
    assert os.path.exists(pm) and os.path.exists(ex)
    assert len(json.loads(open(ex, encoding="utf-8").read())) == 43
    before = open(pm, encoding="utf-8").read()
    write_collections(DEFAULT_OUT)
    assert open(pm, encoding="utf-8").read() == before


def test_collection_export_zip_is_deterministic():
    import io as _io, zipfile
    from great_sdd.conformance.collection import build_zip_bytes
    b1 = build_zip_bytes()
    assert b1 == build_zip_bytes()
    names = set(zipfile.ZipFile(_io.BytesIO(b1)).namelist())
    assert "postman_collection.json" in names and "examples.json" in names
    assert any(n.startswith("bruno/") and n.endswith(".bru") for n in names)
```

- [ ] **Step 4: Regenerate committed artifacts + run the tests**

Run: `python3 -m great_sdd.conformance.collection generate`
Expected: writes the full-API collection (43 ops, 6 folders) under `fixtures/endpoints/collections/`.

Run: `python3 -m pytest tests/test_conformance.py -k "build_examples or collection_generate or collection_export" -v`
Expected: PASS

Run: `python3 -m great_sdd.conformance.collection generate --check ; echo "exit=$?"`
Expected: exit=0, no drift.

- [ ] **Step 5: Commit (code + regenerated artifacts)**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py great_sdd/conformance/fixtures/endpoints/collections/
git commit -m "feat(conformance): full-API examples.json + regenerate committed collections (43 ops)"
```

---

### Task 9: Docs + full verification

**Files:**
- Modify: `great_sdd/conformance/README.md`
- Test: full suite + CLIs

- [ ] **Step 1: Update `great_sdd/conformance/README.md`.** In the "Exporting Bruno / Postman collections" subsection, replace the first paragraph with one noting full-API coverage, and append a coverage note. Add after the existing fenced command block:

```markdown
The collection now covers the **whole API** (43 operations) grouped into the 6 SDD
view folders, generated from the vendored OpenAPI snapshot
(`contracts/pev-openapi.json` — refresh with `scripts/refresh_openapi_snapshot.py`).
Endpoints with a conformance oracle (e.g. `GET /project-lines`) use their richer
per-scenario examples; the rest use deterministic examples synthesized from the
schema, with one saved example per response code (incl. 4xx). Mutations carry a
synthesized request body.
```

- [ ] **Step 2: Full verification — run each:**

```bash
python3 -m great_sdd.conformance.collection generate --check ; echo "collection_check=$?"
python3 -m great_sdd.conformance.generate --check ; echo "fixtures_check=$?"
python3 -m great_sdd.conformance.runner ; echo "runner=$?"
python3 -m pytest tests/ -q
```

Expected: `collection_check=0`, `fixtures_check=0`, runner exit 0 with `Endpoint GET /project-lines: 7/7 cases passed.`, full suite green (0 failures). If any fails, STOP and report BLOCKED.

- [ ] **Step 3: Byte-stability + import sanity**

```bash
python3 -m great_sdd.conformance.collection generate && python3 -m great_sdd.conformance.collection generate
git status --porcelain great_sdd/conformance/fixtures/endpoints/collections/
python3 -c "import json;c=json.load(open('great_sdd/conformance/fixtures/endpoints/collections/postman_collection.json'));print([f['name'] for f in c['item']], sum(len(f['item']) for f in c['item']))"
```

Expected: empty `git status` (byte-stable); the print shows the 6 view folder names and `43`.

- [ ] **Step 4: Commit**

```bash
git add great_sdd/conformance/README.md
git commit -m "docs(conformance): document full-API collection coverage from OpenAPI snapshot"
```

---

## Self-Review

**Spec coverage:**
- Vendored JSON snapshot + refresh script → Task 1. ✓
- `openapi.py` loader/deref/synthesize/iter_operations/TAG_TO_VIEW → Tasks 2-4. ✓
- Synthesized examples for all response codes incl 4xx → Task 5 `_descriptors_from_openapi` (iterates all codes) + Task 8 `build_examples`. ✓
- 6 view folders grouping affine tags → Task 4 `TAG_TO_VIEW`/`VIEW_ORDER`, Task 6 Postman folders, Task 7 Bruno subfolders. ✓
- Unified descriptor + merge (fixture wins) → Task 5. ✓
- Mutations carry request body sample + schema in docs → Task 6 `_pm_request` body, Task 7 `body:json`. ✓
- project-lines keeps rich fixture examples → Task 5 merge + Task 6/8 tests assert it. ✓
- Deterministic + byte-stable + zip → Tasks 6-8 (canonical_json, sorted, fixed examples, fixed zip date_time) + Task 9 byte-stability check. ✓
- Bruno docs brace-safety preserved → Task 7 reuses `_indent_docs`, test asserts no bare `}`. ✓
- README + refresh docs → Tasks 1, 9. ✓
- No census change → collection.py/openapi.py never touch rule fixtures/inventory; `generate --check` (fixtures) stays green (Task 9). ✓

**Placeholder scan:** No TBD/TODO except an intentional, labeled `# TODO(sub-project-2)` marker at the one forward-looking line (the per-oracle VIEW attribute) — documented as deliberate, not a gap for this sub-project.

**Type consistency:** unified descriptor keys (`name, view, method, path, path_params, query_params, auth, request_schema, request_body_example, response_schema, examples, source`) and example keys (`scenario, status, body, authenticated, query`) are defined in Task 5 and consumed identically in Tasks 6-8. `build_postman`/`build_bruno`/`build_examples` all take `descriptors` (the unified list). `write_collections(out_dir)`/`check_collections(out_dir)`/`build_zip_bytes()` are parameterless re inputs (use `unified_descriptors()` via `_artifact_blobs()`), and `_cmd_generate`/`_cmd_export` updated to match (Task 8) — the `--fixtures-dir` flag is removed to avoid a dead option. `_pm_url`/`_bru_file` take a descriptor (not a binding) consistently. `_PM_STATUS_TEXT` extended once (Task 6) and reused. `_markdown_docs_desc` defined in Task 6 and reused in Task 7.

> **Note on test churn:** Tasks 6-8 intentionally REPLACE five tests written for the single-endpoint collection (`test_build_postman_collection_v21_shape`, `test_postman_examples_reflect_scenario_auth_and_query`, `test_build_bruno_files`, `test_build_examples_has_all_cases_per_endpoint`, `test_collection_generate_writes_and_is_byte_stable`, `test_collection_export_zip_is_deterministic`) because the builder signatures and outputs change (fixture-list → unified descriptors; flat → 6 folders). Each replacement is given in full.
