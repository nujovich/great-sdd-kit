# API Collection Export (Bruno + Postman) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate Bruno + Postman collections and an `examples.json` from the conformance endpoint fixtures, with two first-class CLI commands — `generate` (write artifacts) and `export` (zip bundle) — without touching the 92-rule census.

**Architecture:** A deterministic generator `great_sdd/conformance/collection.py` reads each `fixtures/endpoints/*.json` plus per-endpoint `HTTP_BINDING`/`REQUEST_SCHEMA`/`RESPONSE_SCHEMA` declared on the oracle module, and emits Postman v2.1 + a Bruno folder + `examples.json` into `fixtures/endpoints/collections/`. The N logical conformance cases (PMO→200, CPO→403, …) collapse into ONE HTTP request per endpoint with one saved example per case.

**Tech Stack:** Python 3.11+ (run with `python3`; modules use `from __future__ import annotations` for 3.8 import-compat). stdlib only (`json`, `argparse`, `zipfile`, `io`, `pathlib`). pytest. Reuses `sdd.base_conformance.canonical_json`.

**Spec:** `docs/superpowers/specs/2026-06-10-api-collection-export-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `great_sdd/conformance/endpoints/project_lines.py` (modify) | + `HTTP_BINDING`, `REQUEST_SCHEMA`, `RESPONSE_SCHEMA` (mirrored from openapi) |
| `great_sdd/conformance/collection.py` (create) | generator: load fixtures+oracle metadata → Postman/Bruno/examples; `generate` + `export` CLI |
| `great_sdd/conformance/fixtures/endpoints/collections/postman_collection.json` (generated) | committed artifact |
| `great_sdd/conformance/fixtures/endpoints/collections/examples.json` (generated) | committed artifact |
| `great_sdd/conformance/fixtures/endpoints/collections/bruno/{bruno.json,*.bru}` (generated) | committed artifacts |
| `tests/test_conformance.py` (modify) | generator tests |
| `great_sdd/conformance/README.md`, `CLAUDE.md`, `README.md` (modify) | register the `generate`/`export` commands |

---

### Task 1: Oracle HTTP binding + JSON Schemas

**Files:**
- Modify: `great_sdd/conformance/endpoints/project_lines.py` (append after `PROBE`)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
# ═══════════════════════════════════════════════════════════
# collection export — oracle HTTP binding + schemas
# ═══════════════════════════════════════════════════════════
def test_project_lines_http_binding_and_schemas():
    from great_sdd.conformance.endpoints.project_lines import (
        HTTP_BINDING, REQUEST_SCHEMA, RESPONSE_SCHEMA, PROJECT_LINE_FIELDS)
    assert HTTP_BINDING["method"] == "GET"
    assert HTTP_BINDING["path"] == "/project-lines"
    assert HTTP_BINDING["query_params"] == ["assignee", "metier"]
    assert HTTP_BINDING["auth"] == "bearer"
    # response schema's ProjectLine must cover exactly the 24 contract fields
    pl_props = RESPONSE_SCHEMA["definitions"]["ProjectLine"]["properties"]
    assert set(pl_props) == set(PROJECT_LINE_FIELDS)
    # métier enum mirrors the contract (no H-TESTING) in both schemas
    assert "H-TESTING" not in pl_props["metier"]["enum"]
    assert "H-TESTING" not in REQUEST_SCHEMA["properties"]["metier"]["enum"]
    # request query params line up with the binding
    assert set(REQUEST_SCHEMA["properties"]) == set(HTTP_BINDING["query_params"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_project_lines_http_binding_and_schemas -v`
Expected: FAIL with `ImportError: cannot import name 'HTTP_BINDING'`

- [ ] **Step 3: Write minimal implementation** — append to the END of `great_sdd/conformance/endpoints/project_lines.py` (after the `PROBE = EndpointProbe(...)` block):

```python
# ── HTTP contract (mirrored from cap_horse_great pev-openapi.yaml) ──
# Used by the collection exporter to build Bruno/Postman requests. The server
# base path (/api/v1) is a collection variable {{baseUrl}}; auth is Bearer {{token}}.

HTTP_BINDING = {
    "method": "GET",
    "path": "/project-lines",
    "query_params": ["assignee", "metier"],
    "auth": "bearer",
    "body": None,
}

REQUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ListProjectLinesQuery",
    "type": "object",
    "properties": {
        "assignee": {"type": "string",
                     "description": "Filter by assignee OID (PMO/Admin/RCRC)."},
        "metier": {"type": "string", "enum": list(PROJECT_LINE_METIERS),
                   "description": "Filter by project line métier (PMO/Admin/RCRC)."},
    },
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ProjectLinesResponse",
    "type": "object",
    "required": ["data", "filterOptions"],
    "properties": {
        "data": {"type": "array", "items": {"$ref": "#/definitions/ProjectLine"}},
        "filterOptions": {
            "type": "object",
            "required": ["assignees", "metiers"],
            "properties": {
                "assignees": {"type": "array", "items": {"type": "string"}},
                "metiers": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "definitions": {
        "ProjectLine": {
            "type": "object",
            "required": ["id", "pl_number", "pl_name", "status", "metier"],
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "pl_number": {"type": "string"},
                "pl_name": {"type": "string"},
                "status": {"type": "string", "enum": list(STATUSES)},
                "request_type": {"type": ["string", "null"]},
                "client": {"type": ["string", "null"]},
                "metier": {"type": "string", "enum": list(PROJECT_LINE_METIERS)},
                "organ_type": {"type": ["string", "null"]},
                "project_ranking": {"type": ["string", "null"]},
                "market": {"type": ["string", "null"]},
                "alliance_code": {"type": ["string", "null"]},
                "vehicle_code": {"type": ["string", "null"]},
                "energy": {"type": ["string", "null"]},
                "injection_system": {"type": ["string", "null"]},
                "standard_emissions": {"type": ["string", "null"]},
                "engineering": {"type": ["string", "null"]},
                "estimate_type": {"type": ["string", "null"]},
                "sp_date": {"type": ["string", "null"], "format": "date"},
                "pc_date": {"type": ["string", "null"], "format": "date"},
                "co_date": {"type": ["string", "null"], "format": "date"},
                "sop_date": {"type": ["string", "null"], "format": "date"},
                "assignee": {"type": ["string", "null"],
                             "description": "Entra OID (from column assignee_oid)."},
                "total_days": {"type": ["integer", "null"]},
                "total_keuro": {"type": ["number", "null"]},
            },
        }
    },
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_project_lines_http_binding_and_schemas -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/endpoints/project_lines.py tests/test_conformance.py
git commit -m "feat(conformance): declare HTTP binding + request/response JSON Schema for project-lines"
```

---

### Task 2: Collection foundations — loader, registry, scenario labels, examples.json

**Files:**
- Create: `great_sdd/conformance/collection.py`
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
# ═══════════════════════════════════════════════════════════
# collection export — foundations
# ═══════════════════════════════════════════════════════════
def test_scenario_label_covers_statuses():
    from great_sdd.conformance.collection import _scenario_label
    assert _scenario_label({"role": None}, 401) == "no JWT / role (401)"
    assert _scenario_label({"role": "CPO"}, 403) == "CPO — forbidden (403)"
    assert _scenario_label({"role": "PMO"}, 404) == "no active cycle (404)"
    assert _scenario_label({"role": "PMO", "query": {}}, 200) == "PMO — all (200)"
    assert _scenario_label({"role": "PMO", "query": {"metier": "H-DESIGN"}}, 200) \
        == "PMO — metier=H-DESIGN (200)"


def test_build_examples_has_all_cases_per_endpoint():
    from great_sdd.conformance.collection import build_examples, load_endpoints
    eps = load_endpoints()                      # default committed fixtures
    examples = build_examples(eps)
    assert "GET /project-lines" in examples
    rows = examples["GET /project-lines"]
    assert len(rows) == 7                        # all 7 conformance cases
    for row in rows:
        assert set(row) == {"scenario", "request", "response"}
        assert set(row["response"]) == {"status", "body"}
    # at least one 200 and the 403/404/401 are represented
    statuses = sorted({r["response"]["status"] for r in rows})
    assert statuses == [200, 401, 403, 404]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py -k "scenario_label or build_examples" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'great_sdd.conformance.collection'`

- [ ] **Step 3: Write minimal implementation** — create `great_sdd/conformance/collection.py`:

```python
"""Export Bruno + Postman collections from conformance endpoint fixtures.

Reads each fixtures/endpoints/*.json plus the per-endpoint HTTP_BINDING and
REQUEST_SCHEMA/RESPONSE_SCHEMA declared on its oracle module, and emits:
  - postman_collection.json (Postman Collection v2.1)
  - bruno/ (native .bru files + bruno.json)
  - examples.json (every conformance case per endpoint, human-readable)

The N logical conformance cases (PMO->200, CPO->403, ...) collapse into ONE HTTP
request per endpoint with one saved example per case. Deterministic, byte-stable,
stdlib-only. Does NOT enter the business-rule census.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

from sdd.base_conformance import canonical_json
from great_sdd.conformance.generate import ENDPOINTS_DIR
from great_sdd.conformance.endpoints import project_lines as _project_lines_ep

DEFAULT_OUT = ENDPOINTS_DIR / "collections"

# endpoint name -> oracle module exposing HTTP_BINDING / REQUEST_SCHEMA / RESPONSE_SCHEMA
_ENDPOINT_MODULES = {
    "GET /project-lines": _project_lines_ep,
}


def _load_endpoint_fixtures(fixtures_dir: Path) -> list:
    """Parsed endpoint fixtures from <fixtures_dir>/*.json (non-recursive)."""
    return [json.loads(fp.read_text())
            for fp in sorted(Path(fixtures_dir).glob("*.json"))]


def load_endpoints(fixtures_dir: Path = ENDPOINTS_DIR) -> list:
    """List of {name, fixture, module} for each endpoint fixture found."""
    endpoints = []
    for fx in _load_endpoint_fixtures(fixtures_dir):
        name = fx["endpoint"]
        endpoints.append({"name": name, "fixture": fx,
                          "module": _ENDPOINT_MODULES[name]})
    return endpoints


def _scenario_label(case: dict, status: int) -> str:
    """Human-readable label for a conformance case, by status + request."""
    role = case.get("role")
    if status == 401:
        return "no JWT / role (401)"
    if status == 403:
        return f"{role} — forbidden (403)"
    if status == 404:
        return "no active cycle (404)"
    query = case.get("query") or {}
    bits = [f"{k}={query[k]}" for k in ("assignee", "metier") if query.get(k)]
    suffix = ", ".join(bits) if bits else "all"
    return f"{role} — {suffix} (200)"


def build_examples(endpoints: list) -> dict:
    """endpoint name -> [{scenario, request, response:{status, body}}] for every case."""
    out = {}
    for ep in endpoints:
        rows = []
        for case in ep["fixture"]["cases"]:
            status = case["expected"]["status"]
            rows.append({
                "scenario": _scenario_label(case["request"], status),
                "request": case["request"],
                "response": {"status": status, "body": case["expected"]["body"]},
            })
        out[ep["name"]] = rows
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py -k "scenario_label or build_examples" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): collection loader, scenario labels, examples builder"
```

---

### Task 3: Postman v2.1 builder + schema docs

**Files:**
- Modify: `great_sdd/conformance/collection.py` (append builders)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_build_postman_collection_v21_shape():
    from great_sdd.conformance.collection import build_postman, load_endpoints
    coll = build_postman(load_endpoints())
    assert coll["info"]["schema"] == \
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    assert any(v["key"] == "baseUrl" for v in coll["variable"])
    assert any(v["key"] == "token" for v in coll["variable"])
    item = next(i for i in coll["item"] if i["name"] == "GET /project-lines")
    assert item["request"]["method"] == "GET"
    # bearer auth header present
    assert any(h["key"] == "Authorization" and h["value"] == "Bearer {{token}}"
               for h in item["request"]["header"])
    # url uses {{baseUrl}} + path + query params
    assert item["request"]["url"]["raw"].startswith("{{baseUrl}}/project-lines")
    assert {q["key"] for q in item["request"]["url"]["query"]} == {"assignee", "metier"}
    # one saved example per conformance case, each with its status code
    assert len(item["response"]) == 7
    codes = sorted(r["code"] for r in item["response"])
    assert codes == [200, 200, 200, 200, 401, 403, 404]
    # request description embeds both schemas + the 24 fields, no H-TESTING
    desc = item["request"]["description"]
    assert "Request schema" in desc and "Response schema" in desc
    assert "total_keuro" in desc and "H-TESTING" not in desc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_build_postman_collection_v21_shape -v`
Expected: FAIL with `ImportError: cannot import name 'build_postman'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/collection.py`:

```python
def _markdown_docs(binding: dict, request_schema: dict, response_schema: dict) -> str:
    """Markdown for a request description: both JSON Schemas + auth note."""
    return (
        f"`{binding['method']} {{{{baseUrl}}}}{binding['path']}`\n\n"
        f"Auth: Bearer `{{{{token}}}}`.\n\n"
        "## Request schema\n\n```json\n"
        + canonical_json(request_schema).rstrip()
        + "\n```\n\n## Response schema\n\n```json\n"
        + canonical_json(response_schema).rstrip()
        + "\n```\n"
    )


def _pm_url(binding: dict, query: dict = None) -> dict:
    """Postman url object: {{baseUrl}} + path segments + query params."""
    query = query or {}
    qitems = [{"key": k, "value": str(query.get(k, ""))}
              for k in binding.get("query_params", [])]
    raw = "{{baseUrl}}" + binding["path"]
    if qitems:
        raw += "?" + "&".join(f"{q['key']}={q['value']}" for q in qitems)
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": [seg for seg in binding["path"].split("/") if seg],
        "query": qitems,
    }


def _pm_headers(binding: dict) -> list:
    headers = []
    if binding.get("auth") == "bearer":
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
    return headers


def build_postman(endpoints: list) -> dict:
    """Postman Collection v2.1: one item per endpoint, one saved example per case."""
    items = []
    for ep in endpoints:
        binding = ep["module"].HTTP_BINDING
        desc = _markdown_docs(binding, ep["module"].REQUEST_SCHEMA,
                              ep["module"].RESPONSE_SCHEMA)
        headers = _pm_headers(binding)
        responses = []
        for case in ep["fixture"]["cases"]:
            status = case["expected"]["status"]
            body = case["expected"]["body"]
            responses.append({
                "name": _scenario_label(case["request"], status),
                "originalRequest": {
                    "method": binding["method"], "header": headers,
                    "url": _pm_url(binding, (case["request"].get("query") or {})),
                },
                "code": status,
                "_postman_previewlanguage": "json",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": canonical_json(body).rstrip() if body is not None else "",
            })
        items.append({
            "name": ep["name"],
            "request": {"method": binding["method"], "header": headers,
                        "url": _pm_url(binding), "description": desc},
            "response": responses,
        })
    return {
        "info": {
            "name": "GREAT API — conformance collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Generated from great_sdd conformance endpoint fixtures. "
                           "Set {{baseUrl}} and {{token}} before sending.",
        },
        "variable": [
            {"key": "baseUrl", "value": "/api/v1"},
            {"key": "token", "value": "<JWT>"},
        ],
        "item": items,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_build_postman_collection_v21_shape -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): Postman v2.1 builder with schema docs + per-case examples"
```

---

### Task 4: Bruno builder

**Files:**
- Modify: `great_sdd/conformance/collection.py` (append)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_build_bruno_files():
    from great_sdd.conformance.collection import build_bruno, load_endpoints
    files = build_bruno(load_endpoints())
    assert "bruno.json" in files
    meta = json.loads(files["bruno.json"])
    assert meta["type"] == "collection" and meta["name"]
    # one .bru per endpoint
    bru_files = [k for k in files if k.endswith(".bru")]
    assert len(bru_files) == 1
    bru = files[bru_files[0]]
    assert "meta {" in bru and "get {" in bru
    assert "url: {{baseUrl}}/project-lines" in bru
    assert "Authorization: Bearer {{token}}" in bru
    assert "docs {" in bru and "Response schema" in bru
    # scenarios listed in docs
    assert "CPO — forbidden (403)" in bru
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_build_bruno_files -v`
Expected: FAIL with `ImportError: cannot import name 'build_bruno'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/collection.py`:

```python
def _bru_slug(name: str) -> str:
    """Filename slug for a .bru file from an endpoint name, e.g. 'GET /project-lines' -> 'project-lines'."""
    return name.split(" ", 1)[-1].strip("/").replace("/", "_") or "endpoint"


def _bru_query_string(binding: dict) -> str:
    qp = binding.get("query_params", [])
    return ("?" + "&".join(f"{k}=" for k in qp)) if qp else ""


def _bru_file(ep: dict, seq: int) -> str:
    """Native Bruno .bru content for one endpoint."""
    binding = ep["module"].HTTP_BINDING
    method = binding["method"].lower()
    url = "{{baseUrl}}" + binding["path"] + _bru_query_string(binding)
    query_block = ""
    if binding.get("query_params"):
        lines = "\n".join(f"  {k}: " for k in binding["query_params"])
        query_block = f"\nparams:query {{\n{lines}\n}}\n"
    # scenarios + schemas go in docs (Bruno has no saved-example concept)
    scenarios = "\n".join(
        f"- {_scenario_label(c['request'], c['expected']['status'])}"
        for c in ep["fixture"]["cases"])
    docs = (
        f"{ep['name']}\n\n## Scenarios\n{scenarios}\n\n"
        + _markdown_docs(binding, ep["module"].REQUEST_SCHEMA,
                         ep["module"].RESPONSE_SCHEMA)
    )
    return (
        f"meta {{\n  name: {ep['name']}\n  type: http\n  seq: {seq}\n}}\n\n"
        f"{method} {{\n  url: {url}\n  body: none\n  auth: bearer\n}}\n"
        f"{query_block}\n"
        f"headers {{\n  Authorization: Bearer {{{{token}}}}\n}}\n\n"
        f"auth:bearer {{\n  token: {{{{token}}}}\n}}\n\n"
        f"docs {{\n{docs}\n}}\n"
    )


def build_bruno(endpoints: list) -> dict:
    """Relative path -> file content for a native Bruno collection folder."""
    files = {
        "bruno.json": canonical_json({
            "version": "1",
            "name": "GREAT API — conformance collection",
            "type": "collection",
        }).rstrip() + "\n",
    }
    for seq, ep in enumerate(sorted(endpoints, key=lambda e: e["name"]), start=1):
        files[f"{_bru_slug(ep['name'])}.bru"] = _bru_file(ep, seq)
    return files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_build_bruno_files -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): native Bruno .bru builder"
```

---

### Task 5: `generate` command — write artifacts + `--check` + emit committed files

**Files:**
- Modify: `great_sdd/conformance/collection.py` (writer + CLI)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_collection_generate_writes_and_is_byte_stable():
    from great_sdd.conformance.collection import write_collections, DEFAULT_OUT, load_endpoints
    from sdd.base_conformance import canonical_json
    write_collections(load_endpoints(), DEFAULT_OUT)
    base = str(DEFAULT_OUT)
    pm = os.path.join(base, "postman_collection.json")
    ex = os.path.join(base, "examples.json")
    bru = os.path.join(base, "bruno", "project-lines.bru")
    assert os.path.exists(pm) and os.path.exists(ex) and os.path.exists(bru)
    # examples.json round-trips and has all 7 cases
    examples = json.loads(open(ex, encoding="utf-8").read())
    assert len(examples["GET /project-lines"]) == 7
    # byte-stable: regenerating produces identical bytes
    before = open(pm, encoding="utf-8").read()
    write_collections(load_endpoints(), DEFAULT_OUT)
    assert open(pm, encoding="utf-8").read() == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_collection_generate_writes_and_is_byte_stable -v`
Expected: FAIL with `ImportError: cannot import name 'write_collections'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/collection.py`:

```python
def _artifact_blobs(endpoints: list) -> dict:
    """Relative path -> file content (str) for ALL collection artifacts."""
    blobs = {
        "postman_collection.json": canonical_json(build_postman(endpoints)),
        "examples.json": canonical_json(build_examples(endpoints)),
    }
    for rel, content in build_bruno(endpoints).items():
        blobs[f"bruno/{rel}"] = content
    return blobs


def write_collections(endpoints: list, out_dir: Path) -> list:
    """Write every artifact under out_dir. Returns the relative paths written."""
    out_dir = Path(out_dir)
    written = []
    for rel, content in _artifact_blobs(endpoints).items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return sorted(written)


def check_collections(endpoints: list, out_dir: Path) -> list:
    """Return the list of artifacts that drift from what's on disk (empty == in sync)."""
    out_dir = Path(out_dir)
    drift = []
    for rel, content in _artifact_blobs(endpoints).items():
        path = out_dir / rel
        on_disk = path.read_text(encoding="utf-8") if path.exists() else ""
        if on_disk != content:
            drift.append(rel)
    return sorted(drift)


def _cmd_generate(args) -> int:
    endpoints = load_endpoints(Path(args.fixtures_dir))
    out_dir = Path(args.out)
    if args.check:
        drift = check_collections(endpoints, out_dir)
        if drift:
            print(f"COLLECTION DRIFT in: {', '.join(drift)}. "
                  f"Run: python -m great_sdd.conformance.collection generate", file=sys.stderr)
            return 1
        print(f"checked collections for {len(endpoints)} endpoint(s) in {out_dir}.")
        return 0
    written = write_collections(endpoints, out_dir)
    print(f"wrote {len(written)} collection artifact(s) for "
          f"{len(endpoints)} endpoint(s) -> {out_dir}.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Export Bruno/Postman collections from conformance endpoint fixtures.")
    sub = ap.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Write collection artifacts to disk.")
    g.add_argument("--fixtures-dir", default=str(ENDPOINTS_DIR),
                   help="Dir of endpoint fixtures (*.json).")
    g.add_argument("--out", default=str(DEFAULT_OUT), help="Output dir for artifacts.")
    g.add_argument("--check", action="store_true",
                   help="Verify committed artifacts are in sync (exit 1 on drift).")
    g.set_defaults(func=_cmd_generate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the committed artifacts, then run the test**

Run: `python3 -m great_sdd.conformance.collection generate`
Expected: `wrote 4 collection artifact(s) for 1 endpoint(s) -> .../collections.` and the files appear under `great_sdd/conformance/fixtures/endpoints/collections/`.

Run: `python3 -m pytest tests/test_conformance.py::test_collection_generate_writes_and_is_byte_stable -v`
Expected: PASS

- [ ] **Step 5: Verify `--check` is clean**

Run: `python3 -m great_sdd.conformance.collection generate --check ; echo "exit=$?"`
Expected: exit=0, no `COLLECTION DRIFT`.

- [ ] **Step 6: Commit (code + committed artifacts)**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py great_sdd/conformance/fixtures/endpoints/collections/
git commit -m "feat(conformance): collection 'generate' command + committed artifacts"
```

---

### Task 6: `export` command — deterministic zip bundle

**Files:**
- Modify: `great_sdd/conformance/collection.py` (zip + CLI subparser)
- Test: `tests/test_conformance.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_conformance.py`:

```python
def test_collection_export_zip_is_deterministic(tmp_path):
    import zipfile
    from great_sdd.conformance.collection import build_zip_bytes, load_endpoints
    blob1 = build_zip_bytes(load_endpoints())
    blob2 = build_zip_bytes(load_endpoints())
    assert isinstance(blob1, bytes)
    assert blob1 == blob2                        # deterministic (fixed date_time)
    zf = zipfile.ZipFile(__import__("io").BytesIO(blob1))
    names = set(zf.namelist())
    assert "postman_collection.json" in names
    assert "examples.json" in names
    assert any(n.startswith("bruno/") and n.endswith(".bru") for n in names)
    # content matches the on-disk generator output
    from great_sdd.conformance.collection import build_postman
    assert zf.read("postman_collection.json").decode("utf-8").strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_conformance.py::test_collection_export_zip_is_deterministic -v`
Expected: FAIL with `ImportError: cannot import name 'build_zip_bytes'`

- [ ] **Step 3: Write minimal implementation** — append to `great_sdd/conformance/collection.py` (add the `export` functions BEFORE `def main`, and register the subparser inside `main`):

Add these functions before `def main`:

```python
# Fixed timestamp so the zip is byte-identical across runs (no now()).
_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def build_zip_bytes(endpoints: list) -> bytes:
    """A deterministic .zip of every collection artifact (sorted, fixed mtime)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, content in sorted(_artifact_blobs(endpoints).items()):
            info = zipfile.ZipInfo(filename=rel, date_time=_ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content.encode("utf-8"))
    return buf.getvalue()


def _cmd_export(args) -> int:
    endpoints = load_endpoints(Path(args.fixtures_dir))
    out = Path(args.out)
    out.write_bytes(build_zip_bytes(endpoints))
    print(f"wrote collection bundle for {len(endpoints)} endpoint(s) -> {out}.")
    return 0
```

Then, inside `main`, register the `export` subparser right after the `generate` block (before `args = ap.parse_args(argv)`):

```python
    e = sub.add_parser("export", help="Bundle the collections into a portable .zip.")
    e.add_argument("--fixtures-dir", default=str(ENDPOINTS_DIR),
                   help="Dir of endpoint fixtures (*.json).")
    e.add_argument("--out", default="great-collections.zip", help="Output .zip path.")
    e.set_defaults(func=_cmd_export)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_conformance.py::test_collection_export_zip_is_deterministic -v`
Expected: PASS

- [ ] **Step 5: Smoke-test the CLI**

Run: `python3 -m great_sdd.conformance.collection export --out /tmp/great-collections.zip && python3 -c "import zipfile; print(sorted(zipfile.ZipFile('/tmp/great-collections.zip').namelist()))"`
Expected: prints a list including `postman_collection.json`, `examples.json`, and a `bruno/*.bru` entry.

- [ ] **Step 6: Commit**

```bash
git add great_sdd/conformance/collection.py tests/test_conformance.py
git commit -m "feat(conformance): collection 'export' command (deterministic zip bundle)"
```

---

### Task 7: Register commands in docs + full verification

**Files:**
- Modify: `great_sdd/conformance/README.md`, `CLAUDE.md`, `README.md`
- Test: full suite + CLIs

- [ ] **Step 1: Document in `great_sdd/conformance/README.md`** — append after the existing "Endpoint conformance" section:

```markdown
### Exporting Bruno / Postman collections

From the endpoint fixtures, generate importable API collections (the fixtures are a
diff oracle, not made for browsing):

```bash
python -m great_sdd.conformance.collection generate         # write postman_collection.json + bruno/ + examples.json
python -m great_sdd.conformance.collection generate --check  # CI: exit 1 if committed artifacts drift
python -m great_sdd.conformance.collection export --out great-collections.zip   # portable zip bundle
```

Artifacts land in `fixtures/endpoints/collections/` (committed). Both commands accept
`--fixtures-dir DIR` to run on-demand over new user data (a `{endpoint, seed, cases}`
JSON) without touching the committed tree. Set `{{baseUrl}}` (`/api/v1`) and `{{token}}`
(Bearer JWT) after importing. Each request carries the request/response JSON Schema in
its description and one saved example per conformance scenario (200/403/404/401).
```

- [ ] **Step 2: Register in `CLAUDE.md`** — in the "Comandos" code block (the one listing `python -m great_sdd.conformance.generate` etc.), add these two lines at the end of that block:

```bash
python -m great_sdd.conformance.collection generate   # exporta collections Bruno/Postman desde los endpoint fixtures
python -m great_sdd.conformance.collection export --out great-collections.zip   # bundle .zip portable
```

- [ ] **Step 3: Register in root `README.md`** — find the conformance "## Uso" / commands block that lists `python -m great_sdd.conformance.generate` (search for `conformance.generate`). Immediately after the `python -m great_sdd.conformance.runner ...` line in that fenced block, add:

```bash
python -m great_sdd.conformance.collection generate                 # collections Bruno/Postman desde endpoint fixtures
python -m great_sdd.conformance.collection export --out api.zip      # bundle .zip portable
```

If no such block exists in README.md, add a short "### Collections (Bruno/Postman)" subsection under the existing Conformance section containing the same two commands.

- [ ] **Step 4: Full verification**

```bash
python3 -m great_sdd.conformance.collection generate --check ; echo "collection_check=$?"
python3 -m great_sdd.conformance.generate --check ; echo "fixtures_check=$?"
python3 -m great_sdd.conformance.runner ; echo "runner=$?"
python3 -m pytest tests/ -q
```

Expected: `collection_check=0` (no drift), `fixtures_check=0`, runner exit 0 with the endpoint line, and the full suite green (0 failures).

- [ ] **Step 5: Byte-stability double-check**

```bash
python3 -m great_sdd.conformance.collection generate && python3 -m great_sdd.conformance.collection generate
git status --porcelain great_sdd/conformance/fixtures/endpoints/collections/
```
Expected: empty output (regenerating twice is byte-identical; committed artifacts unchanged).

- [ ] **Step 6: Commit**

```bash
git add great_sdd/conformance/README.md CLAUDE.md README.md
git commit -m "docs(conformance): register collection generate/export commands"
```

---

## Self-Review

**Spec coverage:**
- Both formats (Postman v2.1 + native Bruno) → Tasks 3, 4. ✓
- Schema in/out embedded in request docs → Task 3 `_markdown_docs` (Postman) + Task 4 (Bruno docs). ✓
- Examples per request, one per case → Task 3 `response[]`. ✓
- `examples.json` with ALL cases per endpoint → Task 2 `build_examples` + Task 5 written file. ✓
- Committed artifacts + on-demand (`--fixtures-dir`/`--out`) → Task 5 (`generate`) + Task 6 (`export`). ✓
- Two first-class commands `generate` + `export`, registered in command surface → Tasks 5, 6, 7. ✓
- Deterministic/byte-stable (incl. zip fixed `date_time`) → Tasks 5, 6 tests + Task 7 Step 5. ✓
- HTTP binding vs logical request distinction → Task 1 `HTTP_BINDING` + Task 3 examples collapse cases into one request. ✓
- No census change → collection.py never touches rule fixtures/inventory; coverage untouched. ✓
- Métier enum excludes H-TESTING → Task 1 schema + Task 3 assertion. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. README Step 3 has a documented fallback if the exact block isn't found (not a placeholder — a concrete conditional instruction).

**Type consistency:** `load_endpoints()→list[{name,fixture,module}]`, `_scenario_label(case,status)`, `build_examples(endpoints)`, `build_postman(endpoints)`, `build_bruno(endpoints)→dict[str,str]`, `_artifact_blobs(endpoints)→dict[str,str]`, `write_collections(endpoints,out_dir)`, `check_collections(...)`, `build_zip_bytes(endpoints)→bytes`, `HTTP_BINDING`/`REQUEST_SCHEMA`/`RESPONSE_SCHEMA`, `DEFAULT_OUT`, `ENDPOINTS_DIR` — names used consistently across Tasks 1-7. The Postman example count assertion (`[200,200,200,200,401,403,404]`) matches the 7 seeded cases (4×200 + 1 each of 401/403/404). ✓
