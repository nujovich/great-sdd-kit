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
        if name not in _ENDPOINT_MODULES:
            raise ValueError(
                f"No oracle module registered for endpoint {name!r}; "
                f"add it to _ENDPOINT_MODULES in collection.py.")
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


def _pm_url(binding: dict, query: dict = None, template: bool = False) -> dict:
    """Postman url object: {{baseUrl}} + path + query params.

    template=True (the saved request) lists every optional param as disabled —
    shown for discoverability but NOT sent. Otherwise (a concrete example) include
    only the params actually present in `query`, with their values.
    """
    query = query or {}
    qp = binding.get("query_params", [])
    if template:
        qitems = [{"key": k, "value": "", "disabled": True} for k in qp]
    else:
        qitems = [{"key": k, "value": str(query[k])}
                  for k in qp if query.get(k) is not None]
    sent = [q for q in qitems if not q.get("disabled")]
    raw = "{{baseUrl}}" + binding["path"]
    if sent:
        raw += "?" + "&".join(f"{q['key']}={q['value']}" for q in sent)
    return {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": [seg for seg in binding["path"].split("/") if seg],
        "query": qitems,
    }


def _pm_headers(binding: dict, authenticated: bool = True) -> list:
    """Bearer auth header; empty for an unauthenticated example (authenticated=False)."""
    if authenticated and binding.get("auth") == "bearer":
        return [{"key": "Authorization", "value": "Bearer {{token}}"}]
    return []


_PM_STATUS_TEXT = {200: "OK", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found"}


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
            req = case["request"]
            status = case["expected"]["status"]
            body = case["expected"]["body"]
            has_body = body is not None
            responses.append({
                "name": _scenario_label(req, status),
                "originalRequest": {
                    "method": binding["method"],
                    "header": _pm_headers(binding, authenticated=req.get("role") is not None),
                    "url": _pm_url(binding, (req.get("query") or {})),
                },
                "status": _PM_STATUS_TEXT.get(status, ""),
                "code": status,
                "_postman_previewlanguage": "json" if has_body else "text",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": canonical_json(body).rstrip() if has_body else "",
            })
        items.append({
            "name": ep["name"],
            "request": {"method": binding["method"], "header": headers,
                        "url": _pm_url(binding, template=True), "description": desc},
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


def _bru_slug(name: str) -> str:
    """Filename slug from an endpoint name, e.g. 'GET /project-lines' -> 'project-lines'."""
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
